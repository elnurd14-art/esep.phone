import logging
from aiogram import Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from config import Config
from database import Database
from goszakup import GoszakupClient, CITIES
from formatter import tender_card, notify_card, subs_list, favs_list
from keyboards import (
    kb_menu, kb_subs, kb_sub_detail, kb_city_select,
    kb_amount_choice, kb_tender, kb_tenders_nav,
    kb_favs_nav, kb_notify, kb_back, kb_notify_tender,
)

logger = logging.getLogger(__name__)
cfg = Config()


# ── FSM ───────────────────────────────────────────────────────────────────────
class AddSub(StatesGroup):
    keyword    = State()   # шаг 1: ввод ключевого слова
    city       = State()   # шаг 2: выбор города (inline)
    amount     = State()   # шаг 3: выбор мин. суммы (inline/ввод)
    manual_amt = State()   # шаг 3b: ручной ввод суммы

class SearchState(StatesGroup):
    waiting = State()


# ── Helpers ───────────────────────────────────────────────────────────────────
async def safe_edit(cb: CallbackQuery, text: str, **kwargs):
    try:
        await cb.message.edit_text(text, **kwargs)
    except TelegramBadRequest:
        await cb.message.answer(text, **kwargs)


def register_handlers(dp: Dispatcher, db: Database, client: GoszakupClient):

    # ══ /start ════════════════════════════════════════════════════════════
    @dp.message(CommandStart())
    async def start(msg: Message):
        db.upsert_user(msg.from_user.id,
                       msg.from_user.username or "",
                       msg.from_user.full_name or "")
        await msg.answer(
            f"👋 <b>Привет, {msg.from_user.first_name}!</b>\n\n"
            "Я слежу за тендерами на <b>goszakup.gov.kz</b>.\n\n"
            "📋 Создай подписку — укажи <b>ключевое слово</b> и <b>город</b>,\n"
            "и я буду уведомлять тебя о новых тендерах каждые 30 минут.\n",
            reply_markup=kb_menu()
        )

    @dp.callback_query(F.data == "menu")
    async def cb_menu(cb: CallbackQuery):
        await cb.answer()
        await safe_edit(cb, "🏠 <b>Главное меню</b>",
                        parse_mode="HTML", reply_markup=kb_menu())

    # ══ /help ════════════════════════════════════════════════════════════
    @dp.message(Command("help"))
    @dp.callback_query(F.data == "help")
    async def help_cmd(event):
        text = (
            "📖 <b>Как пользоваться ботом</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>1. Создай подписку</b>\n"
            "   Нажми «📋 Мои подписки» → «➕ Добавить подписку»\n"
            "   Укажи: ключевое слово + город + мин. сумма\n\n"
            "<b>2. Получай уведомления</b>\n"
            "   Бот проверяет новые тендеры каждые 30 минут\n"
            "   и присылает уведомление если нашёл совпадение\n\n"
            "<b>3. Ищи вручную</b>\n"
            "   /tenders — последние тендеры (с твоими фильтрами)\n"
            "   /search — поиск по слову\n\n"
            "<b>4. Сохраняй в избранное</b>\n"
            "   Нажми ⭐ под любым тендером\n\n"
            "<b>Команды:</b>\n"
            "/tenders — последние тендеры\n"
            "/search — поиск\n"
            "/subs — мои подписки\n"
            "/favorites — избранное\n"
            "/notify — уведомления"
        )
        if isinstance(event, CallbackQuery):
            await event.answer()
            await safe_edit(event, text, parse_mode="HTML", reply_markup=kb_back())
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=kb_back())

    # ══ Тендеры ════════════════════════════════════════════════════════════
    @dp.message(Command("tenders"))
    async def cmd_tenders(msg: Message):
        db.upsert_user(msg.from_user.id)
        await _show_tenders(msg, msg.from_user.id, page=0, edit=False)

    @dp.callback_query(F.data.startswith("tenders:"))
    async def cb_tenders(cb: CallbackQuery):
        await cb.answer()
        page = int(cb.data.split(":")[1])
        await _show_tenders(cb.message, cb.from_user.id, page=page, edit=True)

    async def _show_tenders(target, uid: int, page: int, edit: bool):
        placeholder = "⏳ Загружаю тендеры…"
        if edit:
            try: await target.edit_text(placeholder)
            except Exception: pass
        else:
            await target.answer(placeholder)

        # Собираем фильтры из подписок пользователя
        subs = db.get_subs(uid)
        # Берём первый город из первой подписки (если есть)
        city = subs[0]["city"] if subs else ""
        min_a = min((s["min_amount"] for s in subs if s.get("min_amount")), default=0)

        tenders = await client.get_latest(limit=80, city=city, min_amount=min_a)
        total   = len(tenders)
        chunk   = tenders[page * cfg.PER_PAGE: (page + 1) * cfg.PER_PAGE]

        if not chunk:
            text = (
                "😔 Тендеры не найдены.\n\n"
                "Возможно, фильтры слишком строгие.\n"
                "Создай новую подписку без города: /subs"
            )
            kb = kb_back()
        else:
            filter_info = ""
            if city:
                filter_info += f"  📍 {city}"
            if min_a:
                filter_info += f"  💰 от {min_a:,.0f} ₸"
            if filter_info:
                filter_info = f"\n<i>Фильтр:{filter_info}</i>"

            cards = []
            for i, t in enumerate(chunk, start=page * cfg.PER_PAGE + 1):
                cards.append(tender_card(t, idx=i, is_fav=db.is_fav(uid, t["id"])))
            text = filter_info + "\n\n" + "\n\n".join(cards) if filter_info else "\n\n".join(cards)
            kb   = kb_tenders_nav(page, total, cfg.PER_PAGE)

        try:
            await target.edit_text(text[:4096], parse_mode="HTML",
                                   reply_markup=kb, disable_web_page_preview=True)
        except TelegramBadRequest:
            await target.answer(text[:4096], parse_mode="HTML",
                                reply_markup=kb, disable_web_page_preview=True)

    # ══ Поиск ══════════════════════════════════════════════════════════════
    @dp.message(Command("search"))
    async def cmd_search(msg: Message, state: FSMContext):
        parts = msg.text.split(maxsplit=1)
        if len(parts) > 1:
            await _do_search(msg, msg.from_user.id, parts[1])
        else:
            await msg.answer("🔍 Введи поисковый запрос:")
            await state.set_state(SearchState.waiting)

    @dp.message(SearchState.waiting)
    async def process_search(msg: Message, state: FSMContext):
        await state.clear()
        await _do_search(msg, msg.from_user.id, msg.text.strip())

    @dp.callback_query(F.data.startswith("search_sub:"))
    async def cb_search_sub(cb: CallbackQuery):
        await cb.answer()
        sub_id = int(cb.data.split(":")[1])
        subs = db.get_subs(cb.from_user.id)
        sub  = next((s for s in subs if s["id"] == sub_id), None)
        if not sub:
            await cb.answer("Подписка не найдена", show_alert=True)
            return
        wait = await cb.message.answer(
            f"🔍 Ищу «{sub['keyword']}» в «{sub.get('city') or 'всех городах'}»…"
        )
        await _do_search(wait, cb.from_user.id, sub["keyword"],
                         city=sub.get("city",""),
                         min_amount=sub.get("min_amount",0),
                         edit=True)

    async def _do_search(target, uid: int, query: str,
                         city="", min_amount=0.0, edit=False):
        tenders = await client.search(query, limit=20,
                                      city=city, min_amount=min_amount)
        if not tenders:
            hint = ""
            if city: hint = f" в «{city}»"
            text = f"😔 По запросу «{query}»{hint} ничего не найдено."
            if edit:
                try: await target.edit_text(text, reply_markup=kb_back())
                except Exception: await target.answer(text, reply_markup=kb_back())
            else:
                await target.answer(text, reply_markup=kb_back())
            return

        cards = [tender_card(t, idx=i, is_fav=db.is_fav(uid, t["id"]))
                 for i, t in enumerate(tenders[:5], 1)]
        city_tag = f" · 📍{city}" if city else ""
        text = (
            f"🔍 <b>«{query}»{city_tag}</b> — найдено {len(tenders)}\n\n"
            + "\n\n".join(cards)
        )
        try:
            if edit:
                await target.edit_text(text[:4096], parse_mode="HTML",
                                       reply_markup=kb_back(), disable_web_page_preview=True)
            else:
                await target.answer(text[:4096], parse_mode="HTML",
                                    reply_markup=kb_back(), disable_web_page_preview=True)
        except TelegramBadRequest:
            await target.answer(text[:4096], parse_mode="HTML",
                                reply_markup=kb_back(), disable_web_page_preview=True)

    # ══ Подписки ═══════════════════════════════════════════════════════════
    @dp.message(Command("subs"))
    @dp.callback_query(F.data == "subs")
    async def cmd_subs(event):
        if isinstance(event, CallbackQuery):
            await event.answer()
            uid = event.from_user.id
        else:
            uid = event.from_user.id
        subs = db.get_subs(uid)
        text = subs_list(subs, len(subs), cfg.MAX_SUBS)
        kb   = kb_subs(subs)
        if isinstance(event, CallbackQuery):
            await safe_edit(event, text, parse_mode="HTML", reply_markup=kb)
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=kb)

    @dp.callback_query(F.data.startswith("sub_info:"))
    async def cb_sub_info(cb: CallbackQuery):
        await cb.answer()
        sub_id = int(cb.data.split(":")[1])
        subs   = db.get_subs(cb.from_user.id)
        sub    = next((s for s in subs if s["id"] == sub_id), None)
        if not sub:
            await cb.answer("Не найдено", show_alert=True)
            return
        city   = sub.get("city","") or "все города"
        amt    = f"{sub['min_amount']:,.0f} ₸" if sub.get("min_amount") else "любая"
        text   = (
            f"🔑 <b>Подписка</b>\n\n"
            f"Слово:  <b>{sub['keyword']}</b>\n"
            f"Город:  📍 <b>{city}</b>\n"
            f"Мин. сумма:  💰 <b>{amt}</b>\n\n"
            f"<i>Нажми «Найти» чтобы посмотреть тендеры прямо сейчас,\n"
            f"или «Удалить» чтобы отписаться.</i>"
        )
        await safe_edit(event=cb, text=text, parse_mode="HTML",
                        reply_markup=kb_sub_detail(sub_id, sub["keyword"], sub.get("city","")))

    @dp.callback_query(F.data.startswith("del_sub:"))
    async def cb_del_sub(cb: CallbackQuery):
        sub_id = int(cb.data.split(":")[1])
        db.remove_sub(sub_id, cb.from_user.id)
        await cb.answer("✅ Подписка удалена")
        subs = db.get_subs(cb.from_user.id)
        await safe_edit(cb, subs_list(subs, len(subs), cfg.MAX_SUBS),
                        parse_mode="HTML", reply_markup=kb_subs(subs))

    # ══ Создание подписки (3-шаговый визард) ══════════════════════════════
    #
    #   Шаг 1: ввод ключевого слова (текст)
    #   Шаг 2: выбор города (inline-кнопки)
    #   Шаг 3: выбор мин. суммы (inline-кнопки или ручной ввод)
    #
    @dp.callback_query(F.data == "add_sub")
    async def cb_add_sub(cb: CallbackQuery, state: FSMContext):
        await cb.answer()
        await safe_edit(
            cb,
            "➕ <b>Новая подписка — шаг 1/3</b>\n\n"
            "✏️ Введи <b>ключевое слово</b> для поиска тендеров.\n\n"
            "<i>Примеры: ИТ, строительство, охрана, медицинское оборудование</i>",
            parse_mode="HTML", reply_markup=kb_back("subs")
        )
        await state.set_state(AddSub.keyword)

    @dp.message(AddSub.keyword)
    async def step1_keyword(msg: Message, state: FSMContext):
        kw = msg.text.strip()
        if len(kw) < 2:
            await msg.answer("❌ Минимум 2 символа. Попробуй снова:")
            return
        if len(kw) > 60:
            await msg.answer("❌ Максимум 60 символов. Попробуй снова:")
            return
        if db.count_subs(msg.from_user.id) >= cfg.MAX_SUBS:
            await msg.answer(
                f"❌ Максимум {cfg.MAX_SUBS} подписок. Удали старые через /subs",
                reply_markup=kb_back("subs")
            )
            await state.clear()
            return
        await state.update_data(keyword=kw)
        await msg.answer(
            f"✅ Слово: <b>{kw}</b>\n\n"
            f"📍 <b>Шаг 2/3</b> — выбери <b>город</b>:",
            parse_mode="HTML",
            reply_markup=kb_city_select()
        )
        await state.set_state(AddSub.city)

    @dp.callback_query(AddSub.city, F.data.startswith("pick_city:"))
    async def step2_city(cb: CallbackQuery, state: FSMContext):
        await cb.answer()
        city = cb.data.split(":", 1)[1]
        await state.update_data(city=city)
        city_label = CITIES.get(city, {}).get("label", city or "Все города")
        data = await state.get_data()
        await safe_edit(
            cb,
            f"✅ Слово: <b>{data['keyword']}</b>\n"
            f"✅ Город: <b>{city_label}</b>\n\n"
            f"💰 <b>Шаг 3/3</b> — выбери <b>минимальную сумму</b>:",
            parse_mode="HTML",
            reply_markup=kb_amount_choice()
        )
        await state.set_state(AddSub.amount)

    @dp.callback_query(AddSub.amount, F.data.startswith("pick_amt:"))
    async def step3_amount(cb: CallbackQuery, state: FSMContext):
        val_str = cb.data.split(":", 1)[1]

        if val_str == "manual":
            await cb.answer()
            await safe_edit(
                cb,
                "✏️ Введи минимальную сумму в тенге:\n"
                "<i>Например: 5000000 (5 млн)</i>",
                parse_mode="HTML"
            )
            await state.set_state(AddSub.manual_amt)
            return

        await cb.answer()
        amt = float(val_str)
        await _finish_sub(cb.message, cb.from_user.id, state, amt, edit=True)

    @dp.message(AddSub.manual_amt)
    async def step3_manual(msg: Message, state: FSMContext):
        try:
            amt = float(msg.text.strip().replace(" ","").replace(",","."))
        except ValueError:
            await msg.answer("❌ Неверный формат. Введи число:")
            return
        await _finish_sub(msg, msg.from_user.id, state, amt, edit=False)

    async def _finish_sub(target, uid: int, state: FSMContext,
                           amt: float, edit: bool):
        data    = await state.get_data()
        keyword = data.get("keyword","")
        city    = data.get("city","")
        await state.clear()

        ok = db.add_sub(uid, keyword, city, amt)
        if not ok:
            text = "❌ Не удалось создать подписку. Попробуй снова."
            await target.answer(text, reply_markup=kb_back("subs"))
            return

        city_label  = CITIES.get(city, {}).get("label", "Все города") if city else "🌍 Все города"
        amt_str     = f"{amt:,.0f} ₸" if amt > 0 else "любая"

        text = (
            f"🎉 <b>Подписка создана!</b>\n\n"
            f"🔑 Слово:       <b>{keyword}</b>\n"
            f"📍 Город:       <b>{city_label}</b>\n"
            f"💰 Мин. сумма: <b>{amt_str}</b>\n\n"
            f"<i>Бот будет уведомлять тебя о новых тендерах каждые 30 минут.\n"
            f"Тендеры с таким фильтром также появятся в /tenders</i>"
        )
        try:
            if edit:
                await target.edit_text(text, parse_mode="HTML", reply_markup=kb_back("subs"))
            else:
                await target.answer(text, parse_mode="HTML", reply_markup=kb_back("subs"))
        except TelegramBadRequest:
            await target.answer(text, parse_mode="HTML", reply_markup=kb_back("subs"))

    # ══ Избранное ══════════════════════════════════════════════════════════
    @dp.message(Command("favorites"))
    @dp.callback_query(F.data.startswith("favs:"))
    async def cmd_favs(event):
        if isinstance(event, CallbackQuery):
            await event.answer()
            uid  = event.from_user.id
            page = int(event.data.split(":")[1])
            edit = True
            target = event.message
        else:
            uid  = event.from_user.id
            page = 0
            edit = False
            target = event

        total = db.count_favs(uid)
        items = db.get_favs(uid, offset=page * cfg.PER_PAGE, limit=cfg.PER_PAGE)
        text  = favs_list(items, page + 1, total, cfg.PER_PAGE)
        kb    = kb_favs_nav(page, total, cfg.PER_PAGE)
        try:
            if edit:
                await target.edit_text(text, parse_mode="HTML",
                                       reply_markup=kb, disable_web_page_preview=True)
            else:
                await target.answer(text, parse_mode="HTML",
                                    reply_markup=kb, disable_web_page_preview=True)
        except TelegramBadRequest:
            await target.answer(text, parse_mode="HTML",
                                reply_markup=kb, disable_web_page_preview=True)

    @dp.callback_query(F.data.startswith("fav_add:"))
    async def cb_fav_add(cb: CallbackQuery):
        tid = cb.data.split(":",1)[1]
        if db.count_favs(cb.from_user.id) >= cfg.MAX_FAVS:
            await cb.answer(f"Максимум {cfg.MAX_FAVS} избранных", show_alert=True)
            return
        # Get tender from fresh data
        tenders = await client.get_latest(limit=80)
        t = next((x for x in tenders if x["id"] == tid), None)
        if not t:
            await cb.answer("⚠️ Тендер не найден", show_alert=True)
            return
        db.add_fav(cb.from_user.id, t)
        await cb.answer("⭐ Сохранено в избранное!")

    @dp.callback_query(F.data.startswith("unfav:"))
    async def cb_unfav(cb: CallbackQuery):
        tid = cb.data.split(":",1)[1]
        db.remove_fav(cb.from_user.id, tid)
        await cb.answer("🗑 Удалено из избранного")

    # ══ Уведомления ════════════════════════════════════════════════════════
    @dp.message(Command("notify"))
    @dp.callback_query(F.data == "notify_menu")
    async def cmd_notify(event):
        if isinstance(event, CallbackQuery):
            await event.answer()
            uid = event.from_user.id
        else:
            uid = event.from_user.id
        user    = db.get_user(uid)
        enabled = bool((user or {}).get("notify", 1))
        subs    = db.get_subs(uid)
        text    = (
            f"🔔 <b>Уведомления</b>\n\n"
            f"Статус: {'✅ включены' if enabled else '🔕 выключены'}\n"
            f"Подписок: {len(subs)}\n\n"
            f"<i>Бот проверяет тендеры каждые 30 минут.\n"
            f"Управляй подписками через /subs</i>"
        )
        if isinstance(event, CallbackQuery):
            await safe_edit(event, text, parse_mode="HTML", reply_markup=kb_notify(enabled))
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=kb_notify(enabled))

    @dp.callback_query(F.data == "notify_toggle")
    async def cb_notify_toggle(cb: CallbackQuery):
        user    = db.get_user(cb.from_user.id)
        cur     = bool((user or {}).get("notify", 1))
        new     = not cur
        db.set_notify(cb.from_user.id, new)
        await cb.answer("✅ Включены" if new else "🔕 Выключены")
        subs = db.get_subs(cb.from_user.id)
        text = (
            f"🔔 <b>Уведомления</b>\n\n"
            f"Статус: {'✅ включены' if new else '🔕 выключены'}\n"
            f"Подписок: {len(subs)}"
        )
        await safe_edit(cb, text, parse_mode="HTML", reply_markup=kb_notify(new))

    # ══ Noop / fallback ════════════════════════════════════════════════════
    @dp.callback_query(F.data == "noop")
    async def cb_noop(cb: CallbackQuery):
        await cb.answer()

    @dp.message()
    async def fallback(msg: Message, state: FSMContext):
        if await state.get_state():
            return
        await msg.answer("Используй меню ниже или /help", reply_markup=kb_menu())
