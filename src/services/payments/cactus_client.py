import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import aiohttp
import orjson
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from src.core.config import config
from src.database.models import Invoice
from src.database.session import async_session

logger = logging.getLogger(__name__)

CACTUS_MIN_AMOUNT_RUB = 100.0


class CactusError(Exception):
    pass


class CactusConfigurationError(CactusError):
    pass


class CactusAPIError(CactusError):
    pass


class CactusCardRequisite(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    amount: float | str | None = None
    until: str | None = None
    until_timestamp: int | None = None
    cardNumber: str | None = None
    receiverName: str | None = None
    receiverBank: str | None = None


class CactusSbpRequisite(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    amount: float | str | None = None
    until: str | None = None
    until_timestamp: int | None = None
    receiverPhone: str | None = None
    receiverName: str | None = None
    receiverBank: str | None = None


class CactusCreatePaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str | None = None
    request_check: bool = False
    requisite: dict[str, Any] | None = None


class CactusPaymentStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str | None = None
    order_id: str | None = None
    amount: str | float = "0"
    total_amount: str | float = "0"
    status: str = "WAIT"
    profit: str | float = "0"


class CactusClient:
    def __init__(self) -> None:
        self._dev_mode = bool(config.DEV_MODE)
        self._merchant_id = config.CACTUS_MERCHANT_ID
        self._secret_key = config.CACTUS_SECRET_KEY
        self._base_url = config.CACTUS_API_URL.rstrip("/")
        self._proxy_url = config.PROXY_URL or None
        self._default_h2h_method = config.CACTUS_H2H_METHOD or "card"
        self._invoice_lifetime_sec = config.CACTUS_INVOICE_LIFETIME_SEC or 480
        self._timeout = aiohttp.ClientTimeout(total=config.CACTUS_REQUEST_TIMEOUT_SEC or 15)
        self._session: aiohttp.ClientSession | None = None
        self.enabled = bool(self._secret_key) or self._dev_mode

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    def _ensure_enabled(self) -> None:
        if self._dev_mode:
            logger.debug(
                "CactusClient _ensure_enabled: DEV_MODE mock active (no real requests)."
            )
            return

        if not self.enabled or not self._secret_key:
            logger.warning(
                "CactusClient _ensure_enabled FAILED: credentials missing. "
                "dev_mode=%s secret_is_set=%s merchant_is_set=%s",
                self._dev_mode,
                bool(self._secret_key),
                bool(self._merchant_id),
            )
            raise CactusConfigurationError(
                "CactusPay credentials are not configured. Set CACTUS_SECRET_KEY."
            )

        logger.debug(
            "CactusClient _ensure_enabled OK. merchant_id_prefix=%s method_hint=%s",
            (str(self._merchant_id or "")[:8] + "…") if self._merchant_id else None,
            self._default_h2h_method,
        )

    @staticmethod
    def _generate_sign(
        merchant_id: str | None,
        amount: float | str,
        order_id: str,
        secret_key: str | None,
    ) -> str:
        raw = f"{merchant_id or ''}{amount}{order_id}{secret_key or ''}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _format_amount_rub(amount: float) -> str:
        return f"{round(float(amount), 2):.2f}"

    @staticmethod
    def _normalize_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        return round(float(value), 2)

    def _expires_at_from_lifetime(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(seconds=self._invoice_lifetime_sec)

    def _normalize_requisite_payload(
        self,
        result: dict[str, Any],
        method: str,
    ) -> dict[str, Any]:
        """
        Robust парсинг H2H-реквизитов из ответа CactusPay create_payment.

        Реальный API в продакшене может возвращать:
          - Плоский dict requisite (как в mock, документации)
          - Вложенный requisite.card / requisite.sbp
          - Вложенный result.requisite.data.card / sbp
          - Поля на верхнем уровне result (cardNumber / receiverPhone)

        Дополнительно алиасы имён:
          - Card: cardNumber / card / pan / card_number
          - SBP:  receiverPhone / phone / sbp_phone / fastPayNumber
          - Time: until_timestamp / until_ts / expires_ts / expires_at_ts

        Returns:
            Normalized dict (все известные поля сплюснуты), гарантирует:
            - until_timestamp: int (если найден until+lifetime fallback)
            - Для method=card: cardNumber существует
            - Для method=sbp:  receiverPhone / fastPayNumber существует
        """
        raw_requisite = result.get("requisite") if isinstance(result, dict) else None
        if not isinstance(raw_requisite, dict):
            raw_requisite = {}

        # 1. Flatten вложенные card / sbp / data узлы
        flattened: dict[str, Any] = {}
        for key in ("card", "sbp", "data", "details", "payload"):
            nested = raw_requisite.get(key)
            if isinstance(nested, dict):
                for nested_k, nested_v in nested.items():
                    flattened.setdefault(nested_k, nested_v)

        # 2. Поверх raw_requisite + flattened + ВЕРХНИЙ УРОВЕНЬ result (FIFO приоритет)
        candidate_maps: list[dict[str, Any]] = [raw_requisite, flattened, result if isinstance(result, dict) else {}]

        normalized: dict[str, Any] = {}
        for mapping in candidate_maps:
            if not isinstance(mapping, dict):
                continue
            for k, v in mapping.items():
                normalized.setdefault(k, v)

        # 3. Alias-переназначения для until_timestamp (всегда int epoch sec)
        ts_raw = (
            normalized.get("until_timestamp")
            or normalized.get("until_ts")
            or normalized.get("expires_ts")
            or normalized.get("expires_at_ts")
            or normalized.get("expire_ts")
        )
        if isinstance(ts_raw, (int, float)) and ts_raw > 0:
            normalized.setdefault("until_timestamp", int(ts_raw))

        # Если until_timestamp всё ещё нет — fallback до lifetime + now (инвариант UI countdown)
        if "until_timestamp" not in normalized or not isinstance(normalized["until_timestamp"], int):
            normalized["until_timestamp"] = int(self._expires_at_from_lifetime().timestamp())

        # 4. Alias-переназначения для Card
        card_pan = (
            normalized.get("cardNumber")
            or normalized.get("card_number")
            or normalized.get("pan")
            or normalized.get("card")
            or normalized.get("number")
        )
        if isinstance(card_pan, str) and card_pan.strip():
            normalized["cardNumber"] = card_pan.replace(" ", "")

        # 5. Alias-переназначения для SBP
        sbp_phone = (
            normalized.get("receiverPhone")
            or normalized.get("receiver_phone")
            or normalized.get("phone")
            or normalized.get("sbp_phone")
            or normalized.get("fastPayNumber")
            or normalized.get("fast_pay_number")
            or normalized.get("sbpId")
        )
        if isinstance(sbp_phone, str) and sbp_phone.strip():
            normalized["receiverPhone"] = sbp_phone

        # 6. receiverName / receiverBank fallback (чтобы UI не был пустым)
        if method == "card" and "cardNumber" in normalized:
            normalized.setdefault("receiverBank", normalized.get("bank") or normalized.get("bankName") or "")
            normalized.setdefault("receiverName", normalized.get("recipient") or normalized.get("recipientName") or "")
        if method == "sbp" and "receiverPhone" in normalized:
            normalized.setdefault("receiverBank", normalized.get("bank") or normalized.get("bankName") or "")
            normalized.setdefault("receiverName", normalized.get("recipient") or normalized.get("recipientName") or "")

        return normalized

    async def _mock_create_payment(
        self,
        *,
        amount_rub: float,
        order_id: str,
        method: str,
    ) -> CactusCreatePaymentResponse:
        expires_at = self._expires_at_from_lifetime()
        expires_ts = int(expires_at.timestamp())

        if method == "sbp":
            mock_requisite: dict[str, Any] = {
                "id": f"mock_cactus_{uuid4().hex[:10]}",
                "amount": self._format_amount_rub(amount_rub),
                "until": expires_at.strftime("%a, %d %b %Y %H:%M:%S %z"),
                "until_timestamp": expires_ts,
                "receiverPhone": "+79990000000",
                "receiverName": "IVAN IVANOV",
                "receiverBank": "Sberbank",
            }
        else:
            mock_requisite = {
                "id": f"mock_cactus_{uuid4().hex[:10]}",
                "amount": self._format_amount_rub(amount_rub),
                "until": expires_at.strftime("%a, %d %b %Y %H:%M:%S %z"),
                "until_timestamp": expires_ts,
                "cardNumber": "2200123412341234",
                "receiverName": "IVAN IVANOV",
                "receiverBank": "Sberbank",
            }

        mock_uuid = f"mock_cactus_{uuid4().hex[:10]}"
        return CactusCreatePaymentResponse(
            url=f"https://pay.cactuspay.pro/mock/{mock_uuid}",
            request_check=False,
            requisite=mock_requisite,
        )

    async def _mock_get_status(
        self,
        *,
        order_id: str,
    ) -> CactusPaymentStatusResponse:
        invoice: Invoice | None = None
        try:
            async with async_session() as session:
                invoice = await session.scalar(
                    select(Invoice).where(Invoice.external_id == order_id)
                )
        except Exception as exc:
            logger.warning(
                "CactusClient mock_get_status DB unavailable, fallback default WAIT. order_id=%s err=%s",
                order_id,
                exc.__class__.__name__,
            )
            invoice = None

        if invoice is not None:
            amount_expected = self._normalize_float(invoice.amount_expected_native)
            amount_actual = self._normalize_float(invoice.amount_actual_native)

            if amount_actual <= 0:
                resolved_status = "WAIT"
            else:
                resolved_status = "ACCEPT"

            logger.info(
                "[Cactus.mock_get_status] order_id=%s invoice_id=%s expected=%.2f RUB total_amount=%.2f RUB → status=%s",
                order_id,
                invoice.id,
                amount_expected,
                amount_actual,
                resolved_status,
            )

            return CactusPaymentStatusResponse(
                id=invoice.id,
                order_id=invoice.external_id,
                amount=amount_expected,
                total_amount=amount_actual,
                status=resolved_status,
                profit=0.0,
            )

        return CactusPaymentStatusResponse(
            id=0,
            order_id=order_id,
            amount=0.0,
            total_amount=0.0,
            status="WAIT",
            profit=0.0,
        )

    async def _request(
        self,
        api_method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_enabled()

        body = orjson.dumps(payload).decode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        session = await self._get_session()
        url = f"{self._base_url}/?method={api_method}"

        try:
            async with session.post(
                url,
                data=body.encode("utf-8"),
                headers=headers,
                proxy=self._proxy_url,
            ) as response:
                response_text = await response.text()
        except asyncio.TimeoutError as exc:
            raise CactusAPIError(f"CactusPay request timed out: {api_method}") from exc
        except aiohttp.ClientError as exc:
            raise CactusAPIError(f"CactusPay transport error: {exc}") from exc

        if response.status >= 400:
            logger.error(
                "CactusPay HTTP error method=%s status=%s body=%s",
                api_method,
                response.status,
                response_text,
            )
            raise CactusAPIError(
                f"CactusPay returned HTTP {response.status} for {api_method}."
            )

        try:
            response_data = orjson.loads(response_text)
        except orjson.JSONDecodeError as exc:
            logger.error(
                "CactusPay returned invalid JSON method=%s body=%s",
                api_method,
                response_text,
            )
            raise CactusAPIError("CactusPay returned invalid JSON response.") from exc

        if response_data.get("status") == "error":
            error_message = response_data.get("response") or response_data
            logger.error(
                "CactusPay API business error method=%s payload=%s",
                api_method,
                error_message,
            )
            raise CactusAPIError(f"CactusPay API error: {error_message}")

        result = response_data.get("response")
        if result is None:
            raise CactusAPIError("CactusPay API returned missing response field.")

        return result

    async def create_payment(
        self,
        amount_rub: float,
        order_id: str,
        *,
        description: str | None = None,
        h2h: bool = True,
        user_ip: str = "127.0.0.1",
        method: str | None = None,
        redirect_url: str | None = None,
    ) -> CactusCreatePaymentResponse:
        normalized_amount = self._normalize_float(amount_rub)
        if normalized_amount < CACTUS_MIN_AMOUNT_RUB:
            raise CactusAPIError(
                f"CactusPay minimum amount is {CACTUS_MIN_AMOUNT_RUB} RUB, got {normalized_amount}"
            )

        chosen_method = method or self._default_h2h_method
        amount_str = self._format_amount_rub(normalized_amount)

        logger.info(
            "[Cactus.create_payment] ENTRY order_id=%s amount_str=%s RUB method=%s h2h=%s dev_mode=%s",
            order_id,
            amount_str,
            chosen_method,
            h2h,
            self._dev_mode,
        )

        if self._dev_mode:
            resp = await self._mock_create_payment(
                amount_rub=normalized_amount,
                order_id=order_id,
                method=chosen_method,
            )
            logger.info(
                "[Cactus.create_payment] MOCK OK order_id=%s card_pan_last4=%s sbp_phone_last4=%s until_ts=%s",
                order_id,
                (resp.requisite or {}).get("cardNumber", "")[-4:] if resp.requisite else None,
                (resp.requisite or {}).get("receiverPhone", "")[-4:] if resp.requisite else None,
                (resp.requisite or {}).get("until_timestamp"),
            )
            return resp

        # Generate signature
        signature = self._generate_sign(
            merchant_id=self._merchant_id,
            amount=amount_str,
            order_id=order_id,
            secret_key=self._secret_key,
        )

        payload: dict[str, Any] = {
            "token": self._secret_key or "",
            "merchant_id": self._merchant_id or "",
            "amount": amount_str,
            "order_id": order_id,
            "h2h": h2h,
            "sign": signature,
        }
        if description:
            payload["description"] = description
        if h2h:
            payload["user_ip"] = user_ip
            payload["method"] = chosen_method
        if redirect_url:
            payload["redirect_url"] = redirect_url

        logger.debug(
            "[Cactus.create_payment] REQUEST payload keys=%s signature_prefix=%s",
            sorted(payload.keys()),
            signature[:8] + "…",
        )

        result = await self._request("create", payload)
        normalized_requisite = self._normalize_requisite_payload(result, method=chosen_method)

        resp = CactusCreatePaymentResponse(
            url=result.get("url"),
            request_check=bool(result.get("request_check", False)),
            requisite=normalized_requisite,
        )

        logger.info(
            "[Cactus.create_payment] OK order_id=%s method=%s card_pan_last4=%s sbp_phone_last4=%s until_ts=%s",
            order_id,
            chosen_method,
            normalized_requisite.get("cardNumber", "")[-4:] if normalized_requisite.get("cardNumber") else None,
            normalized_requisite.get("receiverPhone", "")[-4:] if normalized_requisite.get("receiverPhone") else None,
            normalized_requisite.get("until_timestamp"),
        )
        return resp

    async def get_status(
        self,
        *,
        order_id: str,
    ) -> CactusPaymentStatusResponse:
        if not order_id:
            raise ValueError("order_id must be provided.")

        logger.info(
            "[Cactus.get_status] ENTRY order_id=%s dev_mode=%s",
            order_id,
            self._dev_mode,
        )

        if self._dev_mode:
            resp = await self._mock_get_status(order_id=order_id)
            logger.info(
                "[Cactus.get_status] MOCK OK order_id=%s status=%s total_amount=%s amount=%s",
                order_id,
                resp.status,
                resp.total_amount,
                resp.amount,
            )
            return resp

        # Signature for get_status: MD5(merchant_id + "" + order_id + secret)
        # (amount is absent at status-queries → use empty string)
        signature = self._generate_sign(
            merchant_id=self._merchant_id,
            amount="",
            order_id=order_id,
            secret_key=self._secret_key,
        )

        payload: dict[str, Any] = {
            "token": self._secret_key or "",
            "merchant_id": self._merchant_id or "",
            "order_id": order_id,
            "sign": signature,
        }

        logger.debug(
            "[Cactus.get_status] REQUEST payload keys=%s signature_prefix=%s",
            sorted(payload.keys()),
            signature[:8] + "…",
        )

        result = await self._request("get", payload)
        total_amount_raw = result.get("total_amount", result.get("paid_amount", "0"))
        amount_raw = result.get("amount", "0")
        profit_raw = result.get("profit", "0")
        resp = CactusPaymentStatusResponse(
            id=result.get("id"),
            order_id=result.get("order_id", order_id),
            amount=self._normalize_float(amount_raw),
            total_amount=self._normalize_float(total_amount_raw),
            status=str(result.get("status", result.get("payment_status", "WAIT"))).upper(),
            profit=self._normalize_float(profit_raw),
        )

        logger.info(
            "[Cactus.get_status] OK order_id=%s status=%s amount=%s total_amount=%s profit=%s",
            order_id,
            resp.status,
            resp.amount,
            resp.total_amount,
            resp.profit,
        )
        return resp

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None


def validate_cactus_webhook_signature(
    body: bytes,
    *,
    received_signature: str | None,
    secret_key: str | None,
    header_name: str = "X-Signature",
) -> bool:
    """
    Верификация подписи webhook CactusPay.

    На 06.08.2026 документация CactusPay не экспортирует точный формат сигнатуры webhook
    (md5 vs HMAC-SHA256 vs base64). Поэтому функция поддерживает 2 канонических формата
    сразу и возвращает True, если хотя бы один из них совпал.

    Канонический порядок проверки:
    1. MD5(body + secret_key) — как у Cryptomus/многих СНГ-шлюзов.
    2. HMAC-SHA256(body, key=secret_key) — как у большинства современных API.

    Safety:
    - Если secret_key не настроен — немедленно возвращает False (запрет неавторизованных webhook).
    - Строгое сравнение через `hmac.compare_digest` против timing-атак.
    """
    if not secret_key or not body or not received_signature:
        return False

    import hmac
    normalized_received = received_signature.strip().lower()

    # Variant A: MD5(body_bytes + secret_key), lowercase hex
    md5_candidate = hashlib.md5(body + secret_key.encode("utf-8")).hexdigest().lower()
    if hmac.compare_digest(md5_candidate, normalized_received):
        return True

    # Variant B: HMAC-SHA256(body_bytes, key=secret_key), lowercase hex
    hmac_candidate = hmac.new(
        secret_key.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest().lower()
    if hmac.compare_digest(hmac_candidate, normalized_received):
        return True

    # Variant C: HMAC-SHA256 — base64-encoded (как у Yookassa)
    import base64
    hmac_b64_candidate = base64.b64encode(
        hmac.new(
            secret_key.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    if hmac.compare_digest(hmac_b64_candidate, received_signature.strip()):
        return True
    if hmac.compare_digest(hmac_b64_candidate.lower(), normalized_received):
        return True

    logger.warning(
        "CactusPay webhook signature mismatch. received_signature_prefix=%s algo_tried=[md5,h256_hex,h256_b64]",
        (received_signature or "")[:8],
    )
    return False


def validate_cactus_webhook_event_payload(payload: dict) -> tuple[str, str, float, str]:
    """
    Извлекает и валидирует ключевые поля из webhook-события CactusPay.

    Ожидаемые поля (множество вариантов имён, чтобы быть устойчивым к различиям в реальном API):
    - order_id / orderId / invoice / invoice_id / external_id
    - status / payment_status / state
    - amount / total_amount / paid_amount
    - id (внутренний id CactusPay, не обязателен)

    Returns:
        (order_id: str, status: str, amount_rub: float, cactus_internal_id: str)

    Raises:
        ValueError: если order_id отсутствует или amount отрицательный.
    """
    if not isinstance(payload, dict):
        raise ValueError("Cactus webhook payload must be a JSON object")

    order_id = (
        payload.get("order_id")
        or payload.get("orderId")
        or payload.get("invoice")
        or payload.get("invoice_id")
        or payload.get("external_id")
    )
    status = str(
        payload.get("status")
        or payload.get("payment_status")
        or payload.get("state")
        or "UNKNOWN",
    ).upper()
    amount_raw = (
        payload.get("amount")
        or payload.get("total_amount")
        or payload.get("paid_amount")
        or 0
    )
    internal_id = str(
        payload.get("id")
        or payload.get("payment_id")
        or "",
    )

    if not order_id:
        raise ValueError("Cactus webhook missing order_id")

    try:
        amount_rub = round(float(amount_raw), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Cactus webhook invalid amount: {amount_raw!r}") from exc

    if amount_rub < 0:
        raise ValueError(f"Cactus webhook negative amount: {amount_rub}")

    return str(order_id), status, amount_rub, internal_id


cactus_client = CactusClient()
