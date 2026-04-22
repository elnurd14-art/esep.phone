from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict


def kb_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Последние тендеры", callback_data="tenders:0")],
        [
            InlineKeyboardButton(text="📋 Мои подписки",   callback_data="subs"),
            InlineKeyboardButton(text="⭐ Избранное",       callback_data="favs:0"),
        ],
        [
            InlineKeyboardButton(text="🔔 Уведомления",    callback_data="notify_menu"),
            InlineKeyboardButton(text="❓ Помощь",          callback_data="help"),
        ],
    ])


def kb_subs(subs: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for s in subs:
        city = s.get("city","") or "все города"
        amt  = f" · от {s['min_amount']:,.0f}₸" if s.get("min_amount") else ""
        label = f"🔑 {s['keyword']} · 📍{city}{amt}"
        buttons.append([
            InlineKeyboardButton(text=label,      callback_data=f"sub_info:{s['id']}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить подписку", callback_data="add_sub"),
        InlineKeyboardButton(text="🏠 Меню",              callback_data="menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_sub_detail(sub_id: int, keyword: str, city: str) -> InlineKeyboardMarkup:
    city_str = city or "все города"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔍 Найти тендеры: «{keyword}» в «{city_str}»",
            callback_data=f"search_sub:{sub_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Удалить подписку",
            callback_data=f"del_sub:{sub_id}"
        )],
        [InlineKeyboardButton(text="◀ Назад", callback_data="subs")],
    ])


def kb_city_select(current: str = "") -> InlineKeyboardMarkup:
    """City picker — two columns."""
    from goszakup import CITIES
    buttons = []
    items = list(CITIES.items())
    for i in range(0, len(items), 2):
        row = []
        for key, info in items[i:i+2]:
            check = "✅ " if key == current else ""
            row.append(InlineKeyboardButton(
                text=check + info["label"],
                callback_data=f"pick_city:{key}"
            ))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_amount_choice() -> InlineKeyboardMarkup:
    """Quick amount picker."""
    options = [
        ("Любая сумма",   "0"),
        ("от 1 млн ₸",    "1000000"),
        ("от 5 млн ₸",    "5000000"),
        ("от 10 млн ₸",   "10000000"),
        ("от 50 млн ₸",   "50000000"),
        ("от 100 млн ₸",  "100000000"),
        ("Ввести вручную","manual"),
    ]
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"pick_amt:{v}")]
               for t, v in options]
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="add_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_tender(tid: str, url: str, is_fav: bool) -> InlineKeyboardMarkup:
    fav_t  = "⭐ Убрать" if is_fav else "⭐ Сохранить"
    fav_cb = f"unfav:{tid}" if is_fav else f"fav_add:{tid}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Открыть на goszakup.gov.kz", url=url)],
        [InlineKeyboardButton(text=fav_t, callback_data=fav_cb)],
        [InlineKeyboardButton(text="◀ К списку", callback_data="tenders:0")],
    ])


def kb_tenders_nav(page: int, total: int, per_page: int) -> InlineKeyboardMarkup:
    pages = max(1, (total + per_page - 1) // per_page)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"tenders:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="noop"))
    if (page+1)*per_page < total:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"tenders:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"tenders:{page}"),
            InlineKeyboardButton(text="🏠 Меню",     callback_data="menu"),
        ],
    ])


def kb_favs_nav(page: int, total: int, per_page: int) -> InlineKeyboardMarkup:
    pages = max(1, (total + per_page - 1) // per_page)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"favs:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="noop"))
    if (page+1)*per_page < total:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"favs:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")],
    ])


def kb_notify(enabled: bool) -> InlineKeyboardMarkup:
    s = "✅ Включены" if enabled else "🔕 Выключены"
    t = "🔕 Выключить" if enabled else "✅ Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Статус: {s}", callback_data="noop")],
        [InlineKeyboardButton(text=t,              callback_data="notify_toggle")],
        [InlineKeyboardButton(text="🏠 Меню",      callback_data="menu")],
    ])


def kb_back(cb="menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Назад", callback_data=cb)]
    ])


def kb_notify_tender(tid: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Открыть тендер",        url=url)],
        [InlineKeyboardButton(text="⭐ Сохранить в избранное", callback_data=f"fav_add:{tid}")],
    ])
