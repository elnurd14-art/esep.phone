import sqlite3, json, logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, path="tenders.db"):
        self.path = path
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id   INTEGER PRIMARY KEY,
                    username  TEXT DEFAULT '',
                    fullname  TEXT DEFAULT '',
                    notify    INTEGER DEFAULT 1,
                    created   TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_seen TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Каждая подписка = ключевое слово + город + мин.сумма
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    keyword    TEXT NOT NULL,
                    city       TEXT NOT NULL DEFAULT '',
                    min_amount REAL NOT NULL DEFAULT 0,
                    created    TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, keyword, city)
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    tender_id   TEXT NOT NULL,
                    tender_json TEXT NOT NULL,
                    saved       TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, tender_id)
                );

                CREATE TABLE IF NOT EXISTS seen_tenders (
                    tender_id TEXT PRIMARY KEY,
                    seen_at   TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id);
            """)
            c.commit()

    # ── Users ─────────────────────────────────────────────────────────────
    def upsert_user(self, uid: int, username="", fullname=""):
        with self._conn() as c:
            c.execute("""
                INSERT INTO users(user_id, username, fullname)
                VALUES(?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    fullname=excluded.fullname,
                    last_seen=CURRENT_TIMESTAMP
            """, (uid, username, fullname))
            c.commit()

    def get_user(self, uid: int) -> Optional[Dict]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        return dict(r) if r else None

    def set_notify(self, uid: int, val: bool):
        with self._conn() as c:
            c.execute("UPDATE users SET notify=? WHERE user_id=?", (int(val), uid))
            c.commit()

    def get_notify_users(self) -> List[int]:
        with self._conn() as c:
            return [r[0] for r in c.execute(
                "SELECT user_id FROM users WHERE notify=1").fetchall()]

    def count_users(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def count_notify_users(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM users WHERE notify=1").fetchone()[0]

    # ── Subscriptions ─────────────────────────────────────────────────────
    def add_sub(self, uid: int, keyword: str, city: str, min_amount: float = 0) -> bool:
        try:
            with self._conn() as c:
                c.execute("""
                    INSERT OR REPLACE INTO subscriptions(user_id, keyword, city, min_amount)
                    VALUES(?,?,?,?)
                """, (uid, keyword.strip(), city.strip(), min_amount))
                c.commit()
            return True
        except Exception as e:
            logger.error(f"add_sub: {e}")
            return False

    def remove_sub(self, sub_id: int, uid: int):
        with self._conn() as c:
            c.execute("DELETE FROM subscriptions WHERE id=? AND user_id=?", (sub_id, uid))
            c.commit()

    def get_subs(self, uid: int) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT id, keyword, city, min_amount, created
                FROM subscriptions WHERE user_id=?
                ORDER BY created DESC
            """, (uid,)).fetchall()
        return [dict(r) for r in rows]

    def count_subs(self, uid: int) -> int:
        with self._conn() as c:
            return c.execute(
                "SELECT COUNT(*) FROM subscriptions WHERE user_id=?", (uid,)
            ).fetchone()[0]

    def get_all_subs_for_notify(self) -> List[Dict]:
        """All active subscriptions for users with notify=1."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT s.id, s.user_id, s.keyword, s.city, s.min_amount
                FROM subscriptions s
                JOIN users u ON u.user_id = s.user_id
                WHERE u.notify = 1
            """).fetchall()
        return [dict(r) for r in rows]

    # ── Favorites ─────────────────────────────────────────────────────────
    def add_fav(self, uid: int, tender: Dict) -> bool:
        try:
            with self._conn() as c:
                c.execute("""
                    INSERT OR IGNORE INTO favorites(user_id, tender_id, tender_json)
                    VALUES(?,?,?)
                """, (uid, str(tender["id"]), json.dumps(tender, ensure_ascii=False)))
                c.commit()
            return True
        except Exception as e:
            logger.error(f"add_fav: {e}")
            return False

    def remove_fav(self, uid: int, tid: str):
        with self._conn() as c:
            c.execute("DELETE FROM favorites WHERE user_id=? AND tender_id=?", (uid, tid))
            c.commit()

    def is_fav(self, uid: int, tid: str) -> bool:
        with self._conn() as c:
            return bool(c.execute(
                "SELECT 1 FROM favorites WHERE user_id=? AND tender_id=?", (uid, tid)
            ).fetchone())

    def get_favs(self, uid: int, offset=0, limit=5) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT tender_json FROM favorites WHERE user_id=?
                ORDER BY saved DESC LIMIT ? OFFSET ?
            """, (uid, limit, offset)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def count_favs(self, uid: int) -> int:
        with self._conn() as c:
            return c.execute(
                "SELECT COUNT(*) FROM favorites WHERE user_id=?", (uid,)
            ).fetchone()[0]

    # ── Seen ──────────────────────────────────────────────────────────────
    def is_seen(self, tid: str) -> bool:
        with self._conn() as c:
            return bool(c.execute(
                "SELECT 1 FROM seen_tenders WHERE tender_id=?", (tid,)
            ).fetchone())

    def mark_seen(self, tid: str):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO seen_tenders(tender_id) VALUES(?)", (tid,))
            c.commit()

    def cleanup(self, days=45):
        with self._conn() as c:
            c.execute("DELETE FROM seen_tenders WHERE seen_at < datetime('now',?)",
                      (f"-{days} days",))
            c.commit()
