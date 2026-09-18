import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ImagePaths, config
from src.core.redis_bus import LockResult, redis_bus
from src.database.models import Base, SystemMetadata
from src.database.session import engine

logger = logging.getLogger(__name__)

PLACEHOLDER_MSG_ID_KEY = "placeholder_msg_id"
PLACEHOLDER_MSG_ID_REDIS_KEY = "csl:sys:placeholder_msg_id"
ASSET_INIT_LOCK_KEY = "csl:lock:asset_init"


class AssetManager:
    @staticmethod
    async def ensure_metadata_table() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[SystemMetadata.__table__],
            )

    @staticmethod
    async def _get_metadata(session: AsyncSession, key: str) -> SystemMetadata | None:
        return await session.get(SystemMetadata, key)

    @classmethod
    async def _get_metadata_value(
        cls,
        session: AsyncSession,
        key: str,
    ) -> str | None:
        row = await cls._get_metadata(session, key)
        return row.value if row is not None else None

    @classmethod
    async def get_metadata_value(
        cls,
        session: AsyncSession,
        key: str,
    ) -> str | None:
        await cls.ensure_metadata_table()
        return await cls._get_metadata_value(session, key)

    @classmethod
    async def get_placeholder_metadata(
        cls,
        session: AsyncSession,
    ) -> str | None:
        return await cls.get_metadata_value(session, PLACEHOLDER_MSG_ID_KEY)

    @staticmethod
    async def _upsert_metadata(
        session: AsyncSession,
        key: str,
        value: str,
    ) -> None:
        row = await session.get(SystemMetadata, key)
        if row is None:
            session.add(SystemMetadata(key=key, value=value))
            return
        row.value = value

    @classmethod
    async def upsert_metadata_value(
        cls,
        session: AsyncSession,
        key: str,
        value: str,
    ) -> None:
        await cls.ensure_metadata_table()
        await cls._upsert_metadata(session, key, value)

    @staticmethod
    async def _sync_placeholder_to_redis(message_id: str) -> None:
        await redis_bus.set_key(PLACEHOLDER_MSG_ID_REDIS_KEY, message_id)

    @classmethod
    async def _message_exists(cls, bot: Bot, message_id: int) -> bool:
        if config.LOG_CHANNEL_ID is None:
            return False

        tmp_msg = None
        try:
            tmp_msg = await bot.forward_message(
                chat_id=int(config.LOG_CHANNEL_ID),
                from_chat_id=int(config.LOG_CHANNEL_ID),
                message_id=message_id,
                disable_notification=True,
            )
            return True
        except TelegramBadRequest:
            logger.error("Placeholder message_id=%s не найден в LOG_CHANNEL_ID.", message_id)
            return False
        except Exception:
            logger.exception("Placeholder message_id=%s не найден в LOG_CHANNEL_ID.", message_id)
            return False
        finally:
            if tmp_msg is not None:
                try:
                    await bot.delete_message(int(config.LOG_CHANNEL_ID), tmp_msg.message_id)
                except Exception:
                    logger.warning("Не удалось удалить временное placeholder-сообщение %s.", tmp_msg.message_id)

    @classmethod
    async def ensure_placeholder(
        cls,
        bot: Bot,
        session: AsyncSession,
    ) -> int | None:
        if config.LOG_CHANNEL_ID is None:
            logger.info("LOG_CHANNEL_ID не задан. Placeholder asset отключен.")
            return None

        await cls.ensure_metadata_table()
        message_id = await cls.get_placeholder_metadata(session)
        original_message_id = message_id
        if message_id is not None and await cls._message_exists(bot, int(message_id)):
            await cls._sync_placeholder_to_redis(message_id)
            return int(message_id)

        backoff_seconds = 2.0
        while True:
            lock_result, lock_token = await redis_bus.acquire_lock(ASSET_INIT_LOCK_KEY, ttl=10)
            if lock_result is LockResult.ERROR:
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 10.0)
                continue
            break

        if lock_result is LockResult.BUSY:
            logger.info("AssetManager init lock уже занят. Ожидаю существующий placeholder.")
            for _ in range(20):
                await asyncio.sleep(0.5)
                message_id = await cls.get_placeholder_metadata(session)
                if (
                    message_id is not None
                    and message_id != original_message_id
                    and await cls._message_exists(bot, int(message_id))
                ):
                    await cls._sync_placeholder_to_redis(message_id)
                    return int(message_id)
            logger.warning("Placeholder не появился после ожидания asset_init lock.")
            return None

        try:
            message_id = await cls.get_placeholder_metadata(session)
            if message_id is not None and await cls._message_exists(bot, int(message_id)):
                await cls._sync_placeholder_to_redis(message_id)
                return int(message_id)

            if not Path(ImagePaths.PLACEHOLDER).exists():
                logger.error("Placeholder image не найден: %s", ImagePaths.PLACEHOLDER)
                return None

            sent_msg = await bot.send_photo(
                chat_id=int(config.LOG_CHANNEL_ID),
                photo=FSInputFile(ImagePaths.PLACEHOLDER),
                caption="System placeholder anchor",
                disable_notification=True,
            )
            new_message_id = str(sent_msg.message_id)

            await cls._upsert_metadata(session, PLACEHOLDER_MSG_ID_KEY, new_message_id)
            await session.commit()
            await cls._sync_placeholder_to_redis(new_message_id)
            return int(new_message_id)
        finally:
            if lock_token is not None:
                await redis_bus.release_lock(ASSET_INIT_LOCK_KEY, lock_token)
