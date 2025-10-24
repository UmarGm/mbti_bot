# app/bot.py — оригинальный UI из ZIP + фиксы результатов (MBTI + sum bands)

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    FSInputFile, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mbti_bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN не задан в окружении")

# Пути
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
TESTS_DIR = DATA_DIR / "tests"

# Алиасы названий (смайлы — как в ZIP)
TITLE_ALIAS: Dict[str, str] = {
    "attachment": "💘 Тест привязанности",
    "thinking_style": "🧩 Стиль мышления",
    "communication_energy": "💬 Энергия общения",
    "chronotype": "⏰ Тест хронотипа",
    "love_lang": "❤️ Язык любви",
    "mbti": "🧠 Тип личности (MBTI)",
    "burnout": "🔥 Проверка на выгорание",
    "iq_lite": "🧮 IQ Lite",
    "psych_age": "🎂 Психологический возраст",
    "team_role": "👥 Командная роль",
}

# FSM keys
ACTIVE_MSG_KEY = "active_msg_id"

# ===== Картинки/ресурсы =====

def find_brand_image(kind: str) -> Optional[str]:
    """ Ищем обложки: data/branding/menu.(png/jpg/webp), full.(...) """
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = DATA_DIR / "branding" / f"{kind}.{ext}"
        if p.exists():
            return str(p)
    return None

def question_image(test_dir: Path, idx: int) -> Optional[str]:
    """ Ищем изображения вопросов: 1.jpg|png, 2.jpg|png, ... """
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = test_dir / f"{idx}.{ext}"
        if p.exists():
            return str(p)
    return None

# ===== Загрузка тестов (как в ZIP) + учитываем meta.type =====

def load_tests() -> Dict[str, Dict[str, Any]]:
    tests: Dict[str, Dict[str, Any]] = {}
    if not TESTS_DIR.exists():
        log.warning("tests dir not found: %s", TESTS_DIR)
        return tests
    for slug_path in TESTS_DIR.iterdir():
        if not slug_path.is_dir():
            continue
        slug = slug_path.name
        qf = slug_path / "questions.json"
        rf = slug_path / "results.json"
        if not qf.exists() or not rf.exists():
            log.warning("skip test (missing files): %s", slug)
            continue
        try:
            qdata = json.loads(qf.read_text(encoding="utf-8"))
            rdata = json.loads(rf.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("skip test %s: %s", slug, e)
            continue

        questions = qdata.get("questions", [])
        if not isinstance(questions, list) or not questions:
            log.warning("skip test (empty/bad questions): %s", slug)
            continue

        tests[slug] = {
            "title": qdata.get("meta", {}).get("title", TITLE_ALIAS.get(slug, slug)),
            # 💡 критично: читаем тип теста для расчёта результатов
            "type": qdata.get("meta", {}).get("type", "traits"),
            "questions": questions,
            "results": rdata,
            "dir": slug_path,
        }
    log.info("Загружено тестов: %d", len(tests))
    return tests

TESTS = load_tests()

# ===== Базовые утилиты сообщений =====

async def _store_msg_id(state: FSMContext, key: str, msg_id: Optional[int]):
    data = await state.get_data()
    data[key] = msg_id
    await state.update_data(**data)

async def _get_msg_id(state: FSMContext, key: str) -> Optional[int]:
    data = await state.get_data()
    return data.get(key)

async def replace_message(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: Optional[str] = None,
    photo: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    """ «Мягкая» подмена: редачим старое сообщение, если можно, иначе шлём новое. """
    try:
        msg_id = await _get_msg_id(state, ACTIVE_MSG_KEY)
        if msg_id and photo:
            media = InputMediaPhoto(media=FSInputFile(photo), caption=text)
            await bot.edit_message_media(media=media, chat_id=chat_id, message_id=msg_id, reply_markup=reply_markup)
        elif msg_id and text is not None:
            await bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup)
        else:
            raise RuntimeError("no active message")
    except Exception:
        if photo:
            msg = await bot.send_photo(chat_id, FSInputFile(photo), caption=text, reply_markup=reply_markup)
        else:
            msg = await bot.send_message(chat_id, text or "—", reply_markup=reply_markup)
        await _store_msg_id(state, ACTIVE_MSG_KEY, msg.message_id)

# ===== Подсчёт результатов (фикс) =====

def score_to_mbti(score: Dict[str, int]) -> str:
    e = "E" if score.get("E", 0) >= score.get("I", 0) else "I"
    s = "S" if score.get("S", 0) >= score.get("N", 0) else "N"
    t = "T" if score.get("T", 0) >= score.get("F", 0) else "F"
    j = "J" if score.get("J", 0) >= score.get("P", 0) else "P"
    return f"{e}{s}{t}{j}"

async def compute_result(slug: str, state: FSMContext) -> str:
    data = await state.get_data()
    stash: Dict[str, str] = data.get("stash", {})
    test = TESTS.get(slug, {})
    ttype = test.get("type", "traits")

    # собираем и трейты, и суммы баллов
    trait_score: Dict[str, int] = {}
    total_score = 0
    for raw in stash.values():
        if not raw:
            continue
        if raw.startswith("t:"):
            trait = raw[2:]
            if not trait:
                continue
            trait_score[trait] = trait_score.get(trait, 0) + 1
        elif raw.startswith("s:"):
            try:
                total_score += int(raw[2:])
            except Exception:
                pass

    # MBTI — классическая сборка по осям
    if slug == "mbti" or ttype == "mbti":
        typ = score_to_mbti(trait_score)
        desc = test.get("results", {}).get(typ, "Описание недоступно.")
        return f"🏁 Твой тип: <b>{typ}</b>\n{desc}"

    # Суммовые тесты: bands + format
    if ttype == "sum":
        rdata = test.get("results", {})
        bands = rdata.get("bands", [])
        fmt = rdata.get("format", "<b>{title}</b>\n\n{text}")
        picked = None
        for b in bands:
            try:
                if int(b.get("min", -10**9)) <= total_score <= int(b.get("max", 10**9)):
                    picked = b
                    break
            except Exception:
                continue
        if not picked and bands:
            bands_sorted = sorted(bands, key=lambda x: (x.get("min", 0)))
            picked = bands_sorted[0] if total_score < bands_sorted[0].get("min", 0) else bands_sorted[-1]
        if picked:
            return fmt.format(title=picked.get("title", "—"), text=picked.get("text", ""))
        return "🏁 Результат: нет данных"

    # Fallback (если вдруг другой тип теста)
    top = sorted(trait_score.items(), key=lambda x: -x[1])[:3]
    top_str = ", ".join([f"{k}:{v}" for k, v in top]) if top else "нет данных"
    return f"🏁 Результат «{TESTS[slug]['title']}»:\n<b>{top_str}</b>"

# ===== Интерфейс (как в ZIP): смайлы, вертикальное меню, фото на вопросах =====

router = Router()

def make_q_kb(slug: str, idx: int, q: Dict[str, Any]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for opt in q.get("options", []):
        btn_text = opt.get("text", "—")
        # Внешний вид не меняем — только payload т/с
        if "trait" in opt and opt.get("trait"):
            val = f"t:{opt.get('trait')}"
        elif "score" in opt:
            val = f"s:{opt.get('score')}"
        else:
            val = "t:"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"ans:{slug}:{idx}:{val}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Вернуться в меню", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def render_question(chat_id: int, state: FSMContext, bot: Bot):
    data = await state.get_data()
    slug = data.get("slug")
    idx = int(data.get("index", 0))
    test = TESTS.get(slug)
    if not test:
        await replace_message(bot, chat_id, state, text="Тест недоступен.")
        return
    qs = test["questions"]
    total = len(qs)

    if idx >= total:
        # Конец теста — показываем результат (с фирменной обложкой, если есть)
        result_text = await compute_result(slug, state)
        img = find_brand_image("full")
        await replace_message(bot, chat_id, state, text=result_text, photo=img)
        return

    q = qs[idx]
    text = f"<b>{q.get('text', '')}</b>\n\n({idx + 1}/{total})"
    kb = make_q_kb(slug, idx, q)

    # Фото вопроса: 1.jpg/png/...
    p = question_image(test["dir"], idx + 1)
    await replace_message(bot, chat_id, state, text=text, photo=p, reply_markup=kb)

# Главное меню: смайлы + обложка "menu"
@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext, bot: Bot):
    rows = []
    # Порядок — как в TITLE_ALIAS (как было в ZIP)
    for slug, pretty in TITLE_ALIAS.items():
        if slug in TESTS:
            rows.append([InlineKeyboardButton(text=pretty, callback_data=f"start:{slug}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    photo = find_brand_image("menu")
    caption = "👋 Выбери тест ниже:"
    if photo:
        m = await msg.answer_photo(FSInputFile(photo), caption=caption, reply_markup=kb)
    else:
        m = await msg.answer(caption, reply_markup=kb)
    await _store_msg_id(state, ACTIVE_MSG_KEY, m.message_id)

@router.callback_query(F.data.startswith("start:"))
async def cb_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    slug = call.data.split(":", 1)[1]
    if slug not in TESTS:
        await call.answer("Тест временно недоступен", show_alert=True)
        return
    await state.update_data(slug=slug, index=0, stash={})
    await render_question(call.message.chat.id, state, bot)
    await call.answer()

@router.callback_query(F.data.startswith("ans:"))
async def cb_ans(call: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        _, slug, idx_str, val = call.data.split(":", 3)
        idx = int(idx_str)
    except Exception:
        await call.answer()
        return
    data = await state.get_data()
    stash: Dict[str, str] = data.get("stash", {})
    stash[str(idx)] = val
    await state.update_data(stash=stash, index=idx + 1)
    await render_question(call.message.chat.id, state, bot)
    await call.answer()

# ===== MAIN =====

async def main():
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    try:
        # сбросим вебхук (на всякий), используем long polling
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass

    log.info("✅ MBTI бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
