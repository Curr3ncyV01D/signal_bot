import asyncio
import logging
from enum import Enum
from uuid import uuid4

import orjson
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from src.core.config import config
from src.core.dto import SignalDTO

logger = logging.getLogger(__name__)


class LockResult(Enum):
    ACQUIRED = "acquired"
    BUSY = "busy"
    ERROR = "error"


class RedisBus:
    _connection: Redis | None = None
    _connection_lock = asyncio.Lock()
    _RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

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
    async def _reset_connection(cls) -> None:
        connection = cls._connection
        cls._connection = None
        if connection is not None:
            try:
                await connection.aclose()
            except Exception:
                logger.debug("Не удалось корректно закрыть Redis connection при reset.", exc_info=True)

    @classmethod
    async def _handle_redis_error(cls, message: str) -> None:
        await cls._reset_connection()
        logger.exception(message)

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
            await cls._handle_redis_error("Не удалось опубликовать сигнал в Redis Stream.")
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
                await cls._handle_redis_error("Не удалось создать consumer group Redis.")
        except Exception:
            await cls._handle_redis_error("Не удалось создать consumer group Redis.")

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
            await cls._handle_redis_error("Не удалось прочитать сигналы из Redis Stream.")
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
            await cls._handle_redis_error("Не удалось подтвердить обработку сообщения Redis Stream.")
            return 0

    @classmethod
    async def get_key(cls, key: str) -> bytes | str | None:
        try:
            redis = await cls.get_redis_connection()
            return await redis.get(key)
        except Exception:
            await cls._handle_redis_error("Не удалось получить значение из Redis.")
            return None

    @classmethod
    async def set_key(
        cls,
        key: str,
        value: str,
        expire_seconds: int | None = None,
        only_if_not_exists: bool = False,
    ) -> bool:
        try:
            redis = await cls.get_redis_connection()
            kwargs = {"ex": expire_seconds} if expire_seconds is not None else {}
            if only_if_not_exists:
                kwargs["nx"] = True
            return bool(await redis.set(key, value, **kwargs))
        except Exception:
            await cls._handle_redis_error("Не удалось сохранить значение в Redis.")
            return False

    @classmethod
    async def delete_key(cls, key: str) -> int:
        try:
            redis = await cls.get_redis_connection()
            return int(await redis.delete(key))
        except Exception:
            await cls._handle_redis_error("Не удалось удалить значение из Redis.")
            return 0

    @classmethod
    async def acquire_lock(
        cls,
        key: str,
        ttl: int = 10,
    ) -> tuple[LockResult, str | None]:
        token = uuid4().hex
        try:
            redis = await cls.get_redis_connection()
            acquired = await redis.set(key, token, ex=ttl, nx=True)
            if acquired:
                return LockResult.ACQUIRED, token
            return LockResult.BUSY, None
        except Exception:
            await cls._handle_redis_error("Не удалось захватить Redis lock.")
            return LockResult.ERROR, None

    @classmethod
    async def release_lock(
        cls,
        key: str,
        token: str,
    ) -> int:
        try:
            redis = await cls.get_redis_connection()
            return int(await redis.eval(cls._RELEASE_LOCK_SCRIPT, 1, key, token))
        except Exception:
            await cls._handle_redis_error("Не удалось освободить Redis lock.")
            return 0

    @classmethod
    async def publish_cache_invalidation(cls, payload: str) -> int:
        try:
            redis = await cls.get_redis_connection()
            return await redis.publish(config.REDIS_CACHE_INVALIDATION_CHANNEL, payload)
        except Exception:
            await cls._handle_redis_error("Не удалось отправить cache invalidation в Redis Pub/Sub.")
            return 0

    @staticmethod
    def _gate_key(user_id: int) -> str:
        return f"csl:gate:{user_id}"

    @classmethod
    async def set_gate_status(
        cls,
        user_id: int,
        is_allowed: bool,
        ttl: int | None = None,
    ) -> bool:
        """
        Записывает статус допуска к сигналам Gatekeeper.
        Ключ: csl:gate:{user_id}, значение "1" или "0".
        TTL по умолчанию берётся из config.GATE_CACHE_TTL_SEC.
        """
        resolved_ttl = config.GATE_CACHE_TTL_SEC if ttl is None else int(ttl)
        value = "1" if bool(is_allowed) else "0"
        return await cls.set_key(
            key=cls._gate_key(user_id),
            value=value,
            expire_seconds=resolved_ttl,
        )

    @classmethod
    async def get_gate_status(cls, user_id: int) -> bool | None:
        """
        Читает статус допуска к сигналам Gatekeeper.
        Возвращает True для "1", False для "0", None если ключ отсутствует
        или Redis недоступен.
        """
        raw = await cls.get_key(cls._gate_key(user_id))
        if raw is None:
            return None

        if isinstance(raw, bytes):
            decoded = raw.decode("utf-8")
        else:
            decoded = str(raw)

        normalized = decoded.strip()
        if normalized == "1":
            return True
        if normalized == "0":
            return False
        return None


redis_bus = RedisBus()
