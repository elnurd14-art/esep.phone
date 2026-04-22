import asyncio, logging, os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database import Database
from goszakup import GoszakupClient
from handlers import register_handlers
from scheduler import Scheduler

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    cfg    = Config()
    db     = Database(cfg.DB_PATH)
    client = GoszakupClient()
    bot    = Bot(token=cfg.BOT_TOKEN, parse_mode="HTML")
    dp     = Dispatcher(storage=MemoryStorage())

    register_handlers(dp, db, client)
    asyncio.create_task(Scheduler(bot, db, client).run())

    logger.info("🚀 TenderBot KZ v3 started!")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
