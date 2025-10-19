# app/keyboards.py
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)

def kb_main_private() -> ReplyKeyboardMarkup:
    """
    Reply-клавиатура в личке: одна большая кнопка,
    если вдруг инлайн не отрисовался.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Выбрать тест")]],
        resize_keyboard=True
    )

def kb_open_tests() -> InlineKeyboardMarkup:
    """
    Инлайн-кнопка под приветственным сообщением / фото.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Выбрать тест", callback_data="open_tests")]
        ]
    )

def kb_for_question(options: list[str]) -> InlineKeyboardMarkup:
    """
    Две кнопки-ответа для любого вопроса.
    options: [text0, text1]
    """
    rows = [
        [InlineKeyboardButton(text=f"① {options[0]}", callback_data="opt_0")],
        [InlineKeyboardButton(text=f"② {options[1]}", callback_data="opt_1")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_tests_list(items: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """
    Сетка кнопок тестов по 2 в ряд.
    items: [(id, title), ...]
    Внизу — кнопка обновления списка.
    """
    rows = []
    row: list[InlineKeyboardButton] = []
    for tid, title in items:
        row.append(InlineKeyboardButton(text=title, callback_data=f"pick:{tid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(text="🔁 Обновить список", callback_data="open_tests")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
