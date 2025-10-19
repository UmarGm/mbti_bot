# app/bot.py — финальная версия
# aiogram 3.10+
# плавная подмена сообщений, запрет тестов в группах, рабочие команды, кнопка «Вернуться в меню»

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mbti_bot_v3")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN не задан. Экспортни: export BOT_TOKEN='XXXX:YYYY'")

# --- Пути
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
TESTS_DIR = DATA_DIR / "tests"

# --- FSM ключи
ACTIVE_MSG_KEY = "active_msg_id"     # текущее «экранное» сообщение
AUX_MSG_KEY    = "aux_msg_id"        # служебное (CTA / help)
ACTIVE_KIND_KEY = "active_msg_kind"  # "text" | "photo"

# --- Эмодзи/названия
EMOJI: Dict[str, str] = {
    "mbti": "🧭", "attachment": "🧷", "burnout": "🔥", "chronotype": "⏰",
    "communication_energy": "🔋", "iq_lite": "🧮", "love_lang": "💞",
    "psych_age": "🎂", "team_role": "👥", "thinking_style": "🧠",
}
TITLE_ALIAS: Dict[str, str] = {
    "mbti": "Тип личности (MBTI)", "attachment": "Привязанность",
    "burnout": "Выгорание", "chronotype": "Хронотип",
    "communication_energy": "Энергообщение", "iq_lite": "IQ-lite",
    "love_lang": "Язык любви", "psych_age": "Психологический возраст",
    "team_role": "Роль в команде", "thinking_style": "Стиль мышления",
}

START_CTA = (
    "🤖 Бот работает и в чатах — добавьте его и попробуйте команды:\n"
    "/ice /quiz /whoami /daily /compat /meme\n"
    "Уникально: /aura /souls /reflect"
)
BOT_LINK: str = ""  # заполняется в main()

# ===================== Загрузка тестов =====================

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
            "questions": questions,
            "results": rdata,
            "dir": slug_path
        }
    log.info("Loaded %d tests from %s", len(tests), TESTS_DIR)
    return tests

TESTS: Dict[str, Dict[str, Any]] = load_tests()

# ===================== Утилиты UI =====================

def is_private(chat_type: str) -> bool:
    return chat_type == "private"

def find_brand_image(kind: str) -> Optional[str]:
    roots = [DATA_DIR / "branding", DATA_DIR / "images" / "branding"]
    for root in roots:
        for ext in ("png", "jpg", "jpeg", "webp"):
            p = root / f"{kind}.{ext}"
            if p.exists():
                return str(p)
    return None

async def _store_msg_id(state: FSMContext, key: str, msg_id: Optional[int]):
    data = await state.get_data()
    data[key] = msg_id
    await state.update_data(**data)

async def _get_msg_id(state: FSMContext, key: str) -> Optional[int]:
    data = await state.get_data()
    return data.get(key)

async def replace_message(
    bot: Bot, chat_id: int, state: FSMContext,
    text: Optional[str] = None,
    photo: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None
):
    """
    Мягкая подмена «экрана»:
    1) пробуем редактировать (text/caption/media) в текущем сообщении
    2) если нельзя — отправляем новое, затем удаляем старое (без разрыва)
    Сохраняем тип активного сообщения, чтобы не трогать media без нужды.
    """
    data = await state.get_data()
    msg_id = data.get(ACTIVE_MSG_KEY)
    current_kind = data.get(ACTIVE_KIND_KEY)  # "text" | "photo" | None
    target_kind = "photo" if photo else "text"

    # 1) редактирование
    if msg_id:
        try:
            if target_kind == "text":
                if current_kind == "photo":
                    await bot.edit_message_caption(
                        chat_id=chat_id, message_id=msg_id,
                        caption=text or "", reply_markup=reply_markup
                    )
                else:
                    await bot.edit_message_text(
                        text or "", chat_id, msg_id,
                        reply_markup=reply_markup, disable_web_page_preview=True
                    )
                await state.update_data(**{ACTIVE_KIND_KEY: "text"})
                return
            else:
                if current_kind == "photo":
                    media = InputMediaPhoto(media=FSInputFile(photo), caption=text or "")
                    await bot.edit_message_media(
                        chat_id=chat_id, message_id=msg_id,
                        media=media, reply_markup=reply_markup
                    )
                    await state.update_data(**{ACTIVE_KIND_KEY: "photo"})
                    return
                else:
                    media = InputMediaPhoto(media=FSInputFile(photo), caption=text or "")
                    await bot.edit_message_media(
                        chat_id=chat_id, message_id=msg_id,
                        media=media, reply_markup=reply_markup
                    )
                    await state.update_data(**{ACTIVE_KIND_KEY: "photo"})
                    return
        except Exception:
            # пойдём на отправку нового
            pass

    # 2) отправка нового → удаление старого
    try:
        if target_kind == "photo":
            m = await bot.send_photo(chat_id, FSInputFile(photo), caption=text or "", reply_markup=reply_markup)
            await state.update_data(**{ACTIVE_KIND_KEY: "photo"})
        else:
            m = await bot.send_message(chat_id, text or "", reply_markup=reply_markup, disable_web_page_preview=True)
            await state.update_data(**{ACTIVE_KIND_KEY: "text"})
        if msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        await state.update_data(**{ACTIVE_MSG_KEY: m.message_id})
    except Exception:
        # не падаем в поллинге
        pass

def build_main_menu_kb() -> InlineKeyboardMarkup:
    middle = ["attachment","burnout","chronotype","communication_energy",
              "iq_lite","love_lang","psych_age","team_role"]
    rows: List[List[InlineKeyboardButton]] = []

    if "mbti" in TESTS:
        rows.append([InlineKeyboardButton(
            text=f"{EMOJI.get('mbti','🧭')} {TITLE_ALIAS.get('mbti','MBTI')}",
            callback_data="start:mbti"
        )])

    pair: List[InlineKeyboardButton] = []
    for slug in middle:
        if slug not in TESTS:
            continue
        pair.append(InlineKeyboardButton(
            text=f"{EMOJI.get(slug,'📝')} {TITLE_ALIAS.get(slug, TESTS[slug]['title'])}",
            callback_data=f"start:{slug}"
        ))
        if len(pair) == 2:
            rows.append(pair); pair = []
    if pair: rows.append(pair)

    if "thinking_style" in TESTS:
        rows.append([InlineKeyboardButton(
            text=f"{EMOJI.get('thinking_style','🧠')} {TITLE_ALIAS.get('thinking_style','Стиль мышления')}",
            callback_data="start:thinking_style"
        )])

    return InlineKeyboardMarkup(inline_keyboard=rows)

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Вернуться в меню", callback_data="back:menu")]]
    )

# ===================== Подсчёт/ресурсы =====================

def image_path(slug: str, fname: str) -> Optional[str]:
    p = TESTS[slug]["dir"] / "images" / fname
    return str(p) if p.exists() else None

def score_to_mbti(score: Dict[str, int]) -> str:
    e = "E" if score.get("E",0) >= score.get("I",0) else "I"
    s = "S" if score.get("S",0) >= score.get("N",0) else "N"
    t = "T" if score.get("T",0) >= score.get("F",0) else "F"
    j = "J" if score.get("J",0) >= score.get("P",0) else "P"
    return f"{e}{s}{t}{j}"

async def compute_result(slug: str, state: FSMContext) -> str:
    data = await state.get_data()
    stash: Dict[str, str] = data.get("stash", {})
    score: Dict[str, int] = {}
    for trait in stash.values():
        if not trait: continue
        score[trait] = score.get(trait, 0) + 1
    if slug == "mbti":
        typ = score_to_mbti(score)
        desc = TESTS[slug]["results"].get(typ, "Описание недоступно.")
        return f"🏁 Твой тип: <b>{typ}</b>\n{desc}"
    top = sorted(score.items(), key=lambda x: -x[1])[:3]
    top_str = ", ".join([f"{k}:{v}" for k,v in top]) if top else "нет данных"
    return f"🏁 Результат «{TESTS[slug]['title']}»:\n<b>{top_str}</b>"

# ===================== Router =====================

router = Router()

def make_q_kb(slug: str, idx: int, q: Dict[str, Any]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for opt in q.get("options", []):
        btn_text = opt.get("text", "—")
        trait = opt.get("trait", "")
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"ans:{slug}:{idx}:{trait}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
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
        result_text = await compute_result(slug, state)
        img = find_brand_image("full")
        await replace_message(bot, chat_id, state, text=result_text, photo=img, reply_markup=back_to_menu_kb())
        return

    q = qs[idx]
    head = f"#{idx+1}/{total}\n\n"
    text = head + q.get("text", "Вопрос")
    img = image_path(slug, q.get("image","")) if q.get("image") else None
    kb = make_q_kb(slug, idx, q)
    await replace_message(bot, chat_id, state, text=text, photo=img, reply_markup=kb)

# --- Команды

@router.message(Command("start"))
async def on_start(m: Message, state: FSMContext, bot: Bot):
    if not is_private(m.chat.type):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Открыть бота в ЛС", url=BOT_LINK or "https://t.me")]
        ])
        await m.answer("🛑 Тесты доступны только в личных сообщениях.", reply_markup=kb, disable_web_page_preview=True)
        return

    kb = build_main_menu_kb()
    img = find_brand_image("start")
    await replace_message(bot, m.chat.id, state, text="👋 Выбери тест ниже:", photo=img, reply_markup=kb)

    # CTA отдельным сообщением (но без спама)
    aux_id = await _get_msg_id(state, AUX_MSG_KEY)
    if aux_id:
        try:
            await bot.edit_message_text(START_CTA, m.chat.id, aux_id, disable_web_page_preview=True)
            return
        except Exception:
            try: await bot.delete_message(m.chat.id, aux_id)
            except Exception: pass
    cta = await m.answer(START_CTA, disable_web_page_preview=True)
    await _store_msg_id(state, AUX_MSG_KEY, cta.message_id)

@router.message(Command("help"))
async def on_help(m: Message):
    await m.answer(
        "🧰 Команды:\n"
        "/ice /quiz /whoami /daily /compat /meme\n"
        "Уникально: /aura /souls /reflect",
        disable_web_page_preview=True
    )

# простые рабочие команды (и в группах тоже)
@router.message(Command("ice"))
async def cmd_ice(m: Message):   await m.answer("🧊 Ледокол: спроси соседа справа о его самом странном хобби.")
@router.message(Command("quiz"))
async def cmd_quiz(m: Message):  await m.answer("❓ Вопрос дня: «Что тебя заряжает по утрам?»")
@router.message(Command("whoami"))
async def cmd_whoami(m: Message): await m.answer("👤 Ты — человек контекста.")
@router.message(Command("daily"))
async def cmd_daily(m: Message): await m.answer("🗓️ Задание дня: 10 минут без телефона.")
@router.message(Command("compat"))
async def cmd_compat(m: Message): await m.answer("💞 Совместимость: ищи тех, кто разделяет твой темп.")
@router.message(Command("meme"))
async def cmd_meme(m: Message):   await m.answer("😂 Мем: «Мне надо подумать» — девиз интроверта.")
@router.message(Command("aura"))
async def cmd_aura(m: Message):   await m.answer("✨ Аура дня: спокойствие и ясность.")
@router.message(Command("souls"))
async def cmd_souls(m: Message):  await m.answer("📈 Настроение чата: ровное.")
@router.message(Command("reflect"))
async def cmd_reflect(m: Message):await m.answer("🪞 Рефлексия: что сегодня удалось лучше всего?")

# --- Прохождение тестов

@router.callback_query(F.data.startswith("start:"))
async def cb_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_private(call.message.chat.type):
        await call.answer("Тесты доступны только в ЛС.", show_alert=True)
        return
    slug = call.data.split(":", 1)[1]
    if slug not in TESTS:
        await call.answer("Тест временно недоступен", show_alert=True)
        return
    await state.update_data(slug=slug, index=0, stash={})
    await render_question(call.message.chat.id, state, bot)
    await call.answer()

@router.callback_query(F.data.startswith("ans:"))
async def cb_ans(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_private(call.message.chat.type):
        await call.answer("Тесты доступны только в ЛС.", show_alert=True)
        return
    try:
        _, slug, idx_str, trait = call.data.split(":", 3)
        idx = int(idx_str)
    except Exception:
        await call.answer()
        return
    data = await state.get_data()
    stash: Dict[str, str] = data.get("stash", {})
    stash[str(idx)] = trait
    await state.update_data(stash=stash, index=idx+1)
    await render_question(call.message.chat.id, state, bot)
    await call.answer()

@router.callback_query(F.data == "back:menu")
async def cb_back_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_private(call.message.chat.type):
        await call.answer("Меню тестов — только в ЛС.", show_alert=True)
        return
    kb = build_main_menu_kb()
    img = find_brand_image("start")
    await replace_message(bot, call.message.chat.id, state, text="📋 Выбери тест ниже:", photo=img, reply_markup=kb)
    # обновим/создадим CTA единично
    aux_id = await _get_msg_id(state, AUX_MSG_KEY)
    if aux_id:
        try:
            await bot.edit_message_text(START_CTA, call.message.chat.id, aux_id, disable_web_page_preview=True)
            await call.answer()
            return
        except Exception:
            try: await bot.delete_message(call.message.chat.id, aux_id)
            except Exception: pass
    m = await bot.send_message(call.message.chat.id, START_CTA, disable_web_page_preview=True)
    await _store_msg_id(state, AUX_MSG_KEY, m.message_id)
    await call.answer()

# ===================== Main =====================

async def main():
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass

    global TESTS
    TESTS = load_tests()

    # имя бота для deep-link
    try:
        me = await bot.get_me()
        username = me.username or ""
        global BOT_LINK
        if username:
            BOT_LINK = f"https://t.me/{username}?start=go"
    except Exception:
        pass

    log.info("Ready. %d tests loaded.", len(TESTS))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
