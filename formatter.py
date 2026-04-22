from typing import Dict, List, Optional
from datetime import datetime

URGENCY = {
    "critical": ("🔴🔴🔴🔴🔴", "СРОЧНО"),
    "high":     ("🟠🟠🟠🟠⚪", "скоро"),
    "medium":   ("🟡🟡🟡⚪⚪", ""),
    "low":      ("🟢🟢⚪⚪⚪", ""),
    "unknown":  ("⚪⚪⚪⚪⚪", ""),
}

def _urgency_key(deadline: str) -> str:
    if not deadline or deadline == "—": return "unknown"
    try:
        dt   = datetime.strptime(deadline[:10], "%d.%m.%Y")
        days = (dt - datetime.now()).days
        if days < 0:    return "critical"
        if days <= 3:   return "critical"
        if days <= 7:   return "high"
        if days <= 14:  return "medium"
        return "low"
    except Exception:   return "unknown"

def _days_left(deadline: str) -> str:
    if not deadline or deadline == "—": return ""
    try:
        dt   = datetime.strptime(deadline[:10], "%d.%m.%Y")
        days = (dt - datetime.now()).days
        if days < 0:   return "⛔ просрочен"
        if days == 0:  return "⚡ сегодня!"
        if days == 1:  return "⚡ завтра!"
        return f"{days} дн."
    except Exception:  return ""


def tender_card(t: dict, idx: Optional[int] = None, is_fav: bool = False) -> str:
    uk   = _urgency_key(t.get("deadline",""))
    bar, tag = URGENCY[uk]
    days = _days_left(t.get("deadline",""))

    name = (t.get("name") or "Без названия")[:130]
    cust = (t.get("customer") or "—")[:80]
    loc  = t.get("locality","")

    deadline_str = t.get("deadline","—")
    if days:
        deadline_str += f"  <i>({days})</i>"
    if tag:
        deadline_str = f"<b>{tag}</b> · " + deadline_str

    idx_str = f"<b>#{idx}</b>  " if idx else ""
    fav_str = "  ⭐" if is_fav else ""

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{idx_str}📋 <b>{name}</b>{fav_str}",
        "",
        f"🏢  {cust}" + (f"  <i>({loc})</i>" if loc else ""),
        f"💰  <b>{t.get('amount_str','—')}</b>",
        f"📅  {deadline_str}",
        f"📆  Опубликован: {t.get('publish_date','—')}",
    ]
    if t.get("buy_way"):
        lines.append(f"⚖️  {t['buy_way']}")
    if t.get("lots"):
        lines.append(f"📦  {t['lots'][:100]}")
    lines += [
        f"🔢  № {t.get('number','—')}",
        f"⏱  {bar}",
    ]
    return "\n".join(lines)


def notify_card(t: dict, sub: dict) -> str:
    kw   = sub.get("keyword","")
    city = sub.get("city","")
    days = _days_left(t.get("deadline",""))
    dl   = t.get("deadline","—") + (f" ({days})" if days else "")
    name = (t.get("name") or "—")[:120]
    cust = (t.get("customer") or "—")[:80]
    loc  = t.get("locality","")

    tag = f"<code>{kw}</code>"
    if city:
        tag += f" · 📍<code>{city}</code>"

    return (
        f"🔔 <b>Новый тендер</b> — {tag}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>{name}</b>\n\n"
        f"🏢 {cust}" + (f" <i>({loc})</i>" if loc else "") + "\n"
        f"💰 <b>{t.get('amount_str','—')}</b>\n"
        f"📅 {dl}\n"
        f"🔢 № {t.get('number','—')}"
    )


def subs_list(subs: List[dict], total: int, max_subs: int) -> str:
    if not subs:
        return (
            "📋 <b>Мои подписки</b>\n\n"
            "У тебя пока нет подписок.\n\n"
            "Нажми <b>➕ Добавить</b> — укажи ключевое слово и город, "
            "и бот будет уведомлять тебя о новых тендерах."
        )
    lines = [f"📋 <b>Мои подписки</b> ({total}/{max_subs})\n"]
    for s in subs:
        city_str = f"  📍 {s['city']}" if s.get("city") else "  🌍 Все города"
        amt_str  = f"  💰 от {s['min_amount']:,.0f} ₸" if s.get("min_amount") else ""
        lines.append(
            f"🔑 <b>{s['keyword']}</b>\n"
            f"{city_str}{amt_str}"
        )
    lines.append("\n<i>Нажми на подписку чтобы удалить или найти тендеры</i>")
    return "\n".join(lines)


def favs_list(favs: List[dict], page: int, total: int, per_page: int) -> str:
    if not favs:
        return "⭐ <b>Избранное</b>\n\nСписок пуст.\nНажми ⭐ под тендером чтобы сохранить."
    total_pages = max(1, (total + per_page - 1) // per_page)
    lines = [f"⭐ <b>Избранное</b>  стр. {page}/{total_pages} · всего {total}\n━━━━━━━━━━━━━━━━━━━━━━━━"]
    for i, t in enumerate(favs, start=(page-1)*per_page+1):
        name = (t.get("name") or "—")[:80]
        lines.append(
            f"\n<b>{i}.</b> {name}\n"
            f"   💰 {t.get('amount_str','—')}  |  📅 {t.get('deadline','—')}\n"
            f"   🏢 {(t.get('customer') or '—')[:60]}"
        )
    return "\n".join(lines)
