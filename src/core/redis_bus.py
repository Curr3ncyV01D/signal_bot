import asyncio
import logging

import orjson
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from src.core.config import config
from src.core.dto import SignalDTO

logger = logging.getLogger(__name__)


class RedisBus:
    _connection: Redis | None = None
    _connection_lock = asyncio.Lock()

    @staticmethod
    def _decode_message_id(message_id: bytes | str) -> str:
        return message_id.decode("utf-8") if isinstance(message_id, bytes) else message_id

    @classmethod
    def _parse_stream_entries(
        cls,
        entries: list[tuple[bytes | str, dict[bytes | str, bytes | str]]],
    ) -> list[tuple[str, SignalDTO]]:
        parsed_entries: list[tuple[str, SignalDTO]] = []
        for message_id, fields in entries:
            payload = fields.get("payload") or fields.get(b"payload")
            if payload is None:
                continue

            if isinstance(payload, str):
                payload_bytes = payload.encode("utf-8")
            else:
                payload_bytes = payload

            dto = orjson.loads(payload_bytes)
            parsed_entries.append((cls._decode_message_id(message_id), dto))
        return parsed_entries

    @classmethod
    async def get_redis_connection(cls) -> Redis:
        if cls._connection is not None:
            return cls._connection

        async with cls._connection_lock:
            if cls._connection is None:
                cls._connection = Redis.from_url(
                    config.REDIS_URL,
                    decode_responses=False,
                    socket_connect_timeout=5.0,
                    socket_timeout=5.0,
                )
        return cls._connection

    @classmethod
    async def publish_signal(cls, dto: SignalDTO) -> bytes | str | None:
        return await cls.publish_signal_to_stream(dto, config.REDIS_RAW_STREAM_NAME)

    @classmethod
    async def publish_signal_to_stream(
        cls,
        dto: SignalDTO,
        stream_name: str,
    ) -> bytes | str | None:
        try:
            redis = await cls.get_redis_connection()
            payload = orjson.dumps(dto)
            return await redis.xadd(
                name=stream_name,
                fields={"payload": payload},
                maxlen=config.REDIS_STREAM_MAXLEN,
                approximate=True,
            )
        except Exception:
            logger.exception("Не удалось опубликовать сигнал в Redis Stream.")
            return None

    @classmethod
    async def create_consumer_group(cls) -> None:
        await cls.create_consumer_group_for_stream(
            stream_name=config.REDIS_READY_STREAM_NAME,
            group_name=config.REDIS_MESSENGER_CONSUMER_GROUP,
        )

    @classmethod
    async def create_consumer_group_for_stream(
        cls,
        stream_name: str,
        group_name: str,
    ) -> None:
        try:
            redis = await cls.get_redis_connection()
            await redis.xgroup_create(
                name=stream_name,
                groupname=group_name,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                logger.exception("Не удалось создать consumer group Redis.")
        except Exception:
            logger.exception("Не удалось создать consumer group Redis.")

    @classmethod
    async def get_signals(
        cls,
        consumer_name: str,
        count: int = 10,
    ) -> list[tuple[str, SignalDTO]]:
        return await cls.get_signals_from_stream(
            consumer_name=consumer_name,
            stream_name=config.REDIS_READY_STREAM_NAME,
            group_name=config.REDIS_MESSENGER_CONSUMER_GROUP,
            count=count,
        )

    @classmethod
    async def get_signals_from_stream(
        cls,
        consumer_name: str,
        stream_name: str,
        group_name: str,
        count: int = 10,
    ) -> list[tuple[str, SignalDTO]]:
        redis = await cls.get_redis_connection()

        try:
            pending_entries = await redis.xpending_range(
                name=stream_name,
                groupname=group_name,
                min="-",
                max="+",
                count=count,
                idle=config.REDIS_PENDING_IDLE_MS,
            )
            pending_ids = [
                cls._decode_message_id(entry["message_id"])
                for entry in pending_entries
                if entry.get("message_id") is not None
            ]
            if pending_ids:
                claimed_entries = await redis.xclaim(
                    name=stream_name,
                    groupname=group_name,
                    consumername=consumer_name,
                    min_idle_time=config.REDIS_PENDING_IDLE_MS,
                    message_ids=pending_ids,
                )
                claimed_signals = cls._parse_stream_entries(claimed_entries)
                if claimed_signals:
                    return claimed_signals

            own_pending = await redis.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream_name: "0"},
                count=count,
            )
            if own_pending:
                _, entries = own_pending[0]
                parsed_pending = cls._parse_stream_entries(entries)
                if parsed_pending:
                    return parsed_pending

            new_messages = await redis.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream_name: ">"},
                count=count,
                block=500,
            )
            if not new_messages:
                return []

            _, entries = new_messages[0]
            return cls._parse_stream_entries(entries)
        except Exception:
            logger.exception("Не удалось прочитать сигналы из Redis Stream.")
            return []

    @classmethod
    async def ack_signal(cls, message_id: str) -> int:
        return await cls.ack_signal_for_stream(
            message_id=message_id,
            stream_name=config.REDIS_READY_STREAM_NAME,
            group_name=config.REDIS_MESSENGER_CONSUMER_GROUP,
        )

    @classmethod
    async def ack_signal_for_stream(
        cls,
        message_id: str,
        stream_name: str,
        group_name: str,
    ) -> int:
        try:
            redis = await cls.get_redis_connection()
            return await redis.xack(
                stream_name,
                group_name,
                message_id,
            )
        except Exception:
            logger.exception("Не удалось подтвердить обработку сообщения Redis Stream.")
            return 0

    @classmethod
    async def get_key(cls, key: str) -> bytes | str | None:
        try:
            redis = await cls.get_redis_connection()
            return await redis.get(key)
        except Exception:
            logger.exception("Не удалось получить значение из Redis.")
            return None

    @classmethod
    async def set_key(cls, key: str, value: str, expire_seconds: int) -> bool:
        try:
            redis = await cls.get_redis_connection()
            return bool(await redis.set(key, value, ex=expire_seconds))
        except Exception:
            logger.exception("Не удалось сохранить значение в Redis.")
            return False

    @classmethod
    async def publish_cache_invalidation(cls, payload: str) -> int:
        try:
            redis = await cls.get_redis_connection()
            return await redis.publish(config.REDIS_CACHE_INVALIDATION_CHANNEL, payload)
        except Exception:
            logger.exception("Не удалось отправить cache invalidation в Redis Pub/Sub.")
            return 0


redis_bus = RedisBus()
