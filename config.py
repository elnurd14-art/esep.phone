import os

class Config:
    BOT_TOKEN: str     = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    DB_PATH: str       = os.getenv("DB_PATH", "tenders.db")
    CHECK_INTERVAL:int = int(os.getenv("CHECK_INTERVAL", "1800"))  # 30 min
    MAX_SUBS: int      = 20    # max subscriptions per user
    MAX_FAVS: int      = 200
    PER_PAGE: int      = 5
