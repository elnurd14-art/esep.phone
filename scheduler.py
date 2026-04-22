import asyncio, logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import Config
from database import Database
from goszakup import GoszakupClient
from formatter import notify_card
from keyboards import kb_notify_tender

logger = logging.getLogger(__name__)
cfg    = Config()


class Scheduler:
    def __init__(self, bot: Bot, db: Database, client: GoszakupClient):
        self.bot    = bot
        self.db     = db
        self.client = client

    async def run(self):
        logger.info(f"⏰ Scheduler started. Interval: {cfg.CHECK_INTERVAL}s")
        await asyncio.sleep(60)   # дать боту стартовать
        while True:
            try:    await self._tick()
            except Exception as e: logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(cfg.CHECK_INTERVAL)

    async def _tick(self):
        subs = self.db.get_all_subs_for_notify()
        if not subs:
            return
        logger.info(f"🔍 Checking {len(subs)} subscriptions…")

        for sub in subs:
            try:
                new_tenders = await self.client.get_new_for_sub(sub, self.db.is_seen)
                for t in new_tenders:
                    self.db.mark_seen(t["id"])
                    await self._send(sub["user_id"], t, sub)
                    await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Sub {sub['id']} error: {e}")

        self.db.cleanup(days=45)
        logger.info("✅ Tick done")

    async def _send(self, uid: int, tender: dict, sub: dict):
        text = notify_card(tender, sub)
        kb   = kb_notify_tender(tender["id"], tender["url"])
        try:
            await self.bot.send_message(uid, text, parse_mode="HTML",
                                        reply_markup=kb, disable_web_page_preview=True)
        except TelegramForbiddenError:
            logger.warning(f"User {uid} blocked bot — disabling notify")
            self.db.set_notify(uid, False)
        except TelegramBadRequest as e:
            logger.error(f"BadRequest uid={uid}: {e}")
        except Exception as e:
            logger.error(f"Send error uid={uid}: {e}")
