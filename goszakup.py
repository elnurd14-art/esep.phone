import aiohttp, asyncio, logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://goszakup.gov.kz/v3/graphql"

# Города/регионы Казахстана с вариантами написания для фильтрации
CITIES: Dict[str, Dict] = {
    "":                       {"label": "🌍 Все города",               "aliases": []},
    "Астана":                 {"label": "🏛 Астана",                   "aliases": ["нур-султан", "нурсултан", "astana"]},
    "Алматы":                 {"label": "🌆 Алматы",                   "aliases": ["алма-ата", "almaty"]},
    "Шымкент":                {"label": "🌇 Шымкент",                  "aliases": ["chimkent"]},
    "Алматинская":            {"label": "📍 Алматинская обл.",         "aliases": ["алматинской"]},
    "Акмолинская":            {"label": "📍 Акмолинская обл.",         "aliases": ["акмолинской"]},
    "Актюбинская":            {"label": "📍 Актюбинская обл.",         "aliases": ["актюбинской", "актобе"]},
    "Атырауская":             {"label": "📍 Атырауская обл.",          "aliases": ["атырауской"]},
    "Восточно-Казахстанская": {"label": "📍 Восточно-Казахстанская обл.", "aliases": ["вко", "усть-каменогорск"]},
    "Жамбылская":             {"label": "📍 Жамбылская обл.",          "aliases": ["жамбылской", "тараз"]},
    "Западно-Казахстанская":  {"label": "📍 Западно-Казахстанская обл.","aliases": ["зко", "уральск"]},
    "Карагандинская":         {"label": "📍 Карагандинская обл.",      "aliases": ["карагандинской", "караганда"]},
    "Костанайская":           {"label": "📍 Костанайская обл.",        "aliases": ["костанайской", "костанай"]},
    "Кызылординская":         {"label": "📍 Кызылординская обл.",      "aliases": ["кызылординской"]},
    "Мангистауская":          {"label": "📍 Мангистауская обл.",       "aliases": ["мангистауской", "актау"]},
    "Павлодарская":           {"label": "📍 Павлодарская обл.",        "aliases": ["павлодарской", "павлодар"]},
    "Северо-Казахстанская":   {"label": "📍 Северо-Казахстанская обл.","aliases": ["ско", "петропавловск"]},
    "Туркестанская":          {"label": "📍 Туркестанская обл.",       "aliases": ["туркестанской"]},
}

QUERY_LATEST = """
query Latest($limit: Int!, $offset: Int!) {
  Announcements(limit: $limit, offset: $offset) {
    id nameRu numberAnno totalSum publishDate endDate
    refBuyWay { nameRu }
    customer { nameRu bin locality { nameRu } }
    lots { nameRu amount }
  }
}
"""

QUERY_SEARCH = """
query Search($name: String, $limit: Int!) {
  Announcements(limit: $limit, filter: { nameRu: $name }) {
    id nameRu numberAnno totalSum publishDate endDate
    refBuyWay { nameRu }
    customer { nameRu bin locality { nameRu } }
    lots { nameRu amount }
  }
}
"""


def _fmt_amount(val) -> str:
    try:
        n = float(val or 0)
        if n == 0:       return "не указана"
        if n >= 1e9:     return f"{n/1e9:.1f} млрд ₸"
        if n >= 1e6:     return f"{n/1e6:.1f} млн ₸"
        return f"{n:,.0f} ₸"
    except Exception:    return "не указана"

def _fmt_date(raw: str) -> str:
    if not raw: return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return raw[:10] if len(raw) >= 10 else raw

def _parse(ann: dict) -> dict:
    try:    amount = float(ann.get("totalSum") or 0)
    except: amount = 0.0

    customer = ann.get("customer") or {}
    locality = (customer.get("locality") or {}).get("nameRu", "")
    lots     = ann.get("lots") or []
    lot_names = "; ".join(l.get("nameRu","") for l in lots[:2] if l.get("nameRu"))

    return {
        "id":           str(ann.get("id","")),
        "name":         ann.get("nameRu") or "Без названия",
        "number":       ann.get("numberAnno","—"),
        "amount":       amount,
        "amount_str":   _fmt_amount(amount),
        "deadline":     _fmt_date(ann.get("endDate","")),
        "publish_date": _fmt_date(ann.get("publishDate","")),
        "customer":     customer.get("nameRu","не указан"),
        "customer_bin": customer.get("bin",""),
        "locality":     locality,   # город/регион заказчика
        "buy_way":      (ann.get("refBuyWay") or {}).get("nameRu",""),
        "lots":         lot_names,
        "url":          f"https://goszakup.gov.kz/ru/announce/index/{ann.get('id','')}",
    }


def city_matches(tender: dict, city: str) -> bool:
    """Проверяет совпадение города тендера с фильтром."""
    if not city:
        return True   # нет фильтра — всё подходит
    locality = (tender.get("locality") or "").lower()
    name     = (tender.get("name") or "").lower()
    customer = (tender.get("customer") or "").lower()

    city_lower = city.lower()
    info       = CITIES.get(city, {})
    aliases    = [a.lower() for a in info.get("aliases", [])]

    targets = [city_lower] + aliases
    haystack = f"{locality} {name} {customer}"
    return any(t in haystack for t in targets)


class GoszakupClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _sess(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json",
                         "User-Agent": "TenderBotKZ/3.0"},
                timeout=aiohttp.ClientTimeout(total=20),
            )
        return self._session

    async def _gql(self, query: str, variables: dict) -> Optional[dict]:
        sess = await self._sess()
        try:
            async with sess.post(GRAPHQL_URL,
                                 json={"query": query, "variables": variables}) as r:
                if r.status != 200:
                    logger.warning(f"GraphQL HTTP {r.status}")
                    return None
                data = await r.json(content_type=None)
                if "errors" in data:
                    logger.warning(f"GraphQL errors: {data['errors']}")
                return data.get("data")
        except asyncio.TimeoutError:
            logger.error("GraphQL timeout")
        except Exception as e:
            logger.error(f"GraphQL error: {e}")
        return None

    async def get_latest(self, limit=50, offset=0,
                         city="", min_amount=0.0) -> List[dict]:
        data = await self._gql(QUERY_LATEST, {"limit": limit, "offset": offset})
        if not data:
            return []
        tenders = [_parse(a) for a in (data.get("Announcements") or [])]
        return self._apply_filters(tenders, city=city, min_amount=min_amount)

    async def search(self, keyword: str, limit=30,
                     city="", min_amount=0.0) -> List[dict]:
        data = await self._gql(QUERY_SEARCH, {"name": keyword, "limit": limit})
        if not data:
            return []
        tenders = [_parse(a) for a in (data.get("Announcements") or [])]
        return self._apply_filters(tenders, city=city, min_amount=min_amount)

    def _apply_filters(self, tenders: List[dict],
                       city="", min_amount=0.0) -> List[dict]:
        result = []
        for t in tenders:
            if city and not city_matches(t, city):
                continue
            if min_amount > 0 and t["amount"] < min_amount:
                continue
            result.append(t)
        return result

    async def get_new_for_sub(self, sub: dict, is_seen_fn) -> List[dict]:
        """Fetch new unseen tenders for a subscription profile."""
        keyword    = sub["keyword"]
        city       = sub.get("city", "")
        min_amount = sub.get("min_amount", 0) or 0

        tenders = await self.search(keyword, limit=50,
                                    city=city, min_amount=min_amount)
        return [t for t in tenders if not is_seen_fn(t["id"])]

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
