import asyncio
import base64
import hashlib
import logging
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


class CryptomusError(Exception):
    """Base exception for Cryptomus integration."""


class CryptomusConfigurationError(CryptomusError):
    """Raised when Cryptomus credentials are missing."""


class CryptomusAPIError(CryptomusError):
    """Raised when Cryptomus API returns an error response."""


class CryptomusCreatePaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uuid: str
    order_id: str
    amount: float
    currency: str
    network: str | None = None
    address: str | None = None
    url: str | None = None
    payment_status: str | None = None
    status: str | None = None
    is_final: bool | None = None


class CryptomusPaymentStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uuid: str
    order_id: str | None = None
    amount: float
    payment_amount: float
    currency: str | None = None
    network: str | None = None
    address: str | None = None
    status: str
    payment_status: str | None = None
    is_final: bool
    payer_currency: str | None = None
    txid: str | None = None
    url: str | None = None


class CryptomusClient:
    def __init__(self) -> None:
        self._dev_mode = bool(config.DEV_MODE)
        self._merchant_id = config.CRYPTOMUS_MERCHANT_ID
        self._api_key = config.CRYPTOMUS_PAYMENT_API_KEY
        self._base_url = config.CRYPTOMUS_API_BASE_URL.rstrip("/")
        self._proxy_url = config.PROXY_URL or None
        self._timeout = aiohttp.ClientTimeout(total=config.CRYPTOMUS_REQUEST_TIMEOUT_SEC)
        self._session: aiohttp.ClientSession | None = None
        self.enabled = bool(self._merchant_id and self._api_key) or self._dev_mode

        if self._dev_mode:
            logger.info("Cryptomus client started in DEV_MODE mock mode.")
        elif not self.enabled:
            logger.warning("Cryptomus client disabled: merchant id or api key is missing.")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    def _ensure_enabled(self) -> None:
        if self._dev_mode:
            return
        if not self.enabled or not self._merchant_id or not self._api_key:
            raise CryptomusConfigurationError(
                "Cryptomus credentials are not configured. "
                "Set CRYPTOMUS_MERCHANT_ID and CRYPTOMUS_PAYMENT_API_KEY."
            )

    @staticmethod
    def _format_amount(amount: float) -> str:
        normalized = f"{round(float(amount), 8):.8f}".rstrip("0").rstrip(".")
        return normalized or "0"

    @staticmethod
    def _normalize_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        return round(float(value), 8)

    @staticmethod
    def _serialize_payload(data: dict[str, Any]) -> str:
        return orjson.dumps(
            data,
            option=orjson.OPT_SORT_KEYS,
        ).decode("utf-8")

    def _generate_signature(self, data: dict[str, Any]) -> str:
        payload = self._serialize_payload(data)
        encoded_payload = base64.b64encode(payload.encode("utf-8"))
        return hashlib.md5(encoded_payload + self._api_key.encode("utf-8")).hexdigest()

    async def _mock_create_payment(
        self,
        *,
        amount: float,
        currency: str,
        order_id: str,
        network: str | None,
    ) -> CryptomusCreatePaymentResponse:
        mock_uuid = f"mock_uuid_{uuid4().hex[:10]}"
        return CryptomusCreatePaymentResponse(
            uuid=mock_uuid,
            order_id=order_id,
            amount=self._normalize_float(amount),
            currency=currency,
            network=network or "TRC20",
            address="T-MOCK-ADDRESS-TRC20-FOR-TESTING",
            url=f"https://example.com/mock-cryptomus/{mock_uuid}",
            payment_status="pending",
            status="pending",
            is_final=False,
        )

    async def _mock_get_status(
        self,
        *,
        uuid: str | None = None,
        order_id: str | None = None,
    ) -> CryptomusPaymentStatusResponse:
        invoice: Invoice | None = None
        lookup_external_id = uuid or order_id
        if lookup_external_id:
            async with async_session() as session:
                invoice = await session.scalar(
                    select(Invoice).where(Invoice.external_id == lookup_external_id)
                )

        if invoice is not None:
            amount_expected = self._normalize_float(invoice.amount_expected)
            amount_actual = self._normalize_float(invoice.amount_actual)

            if amount_actual <= 0:
                resolved_status = "pending"
                is_final = False
            elif amount_actual < amount_expected:
                resolved_status = "partially_paid"
                is_final = False
            else:
                resolved_status = "paid"
                is_final = True

            return CryptomusPaymentStatusResponse(
                uuid=invoice.external_id,
                order_id=order_id,
                amount=amount_expected,
                payment_amount=amount_actual,
                currency="USD",
                network=invoice.network or "TRC20",
                address=invoice.address or "T-MOCK-ADDRESS-TRC20-FOR-TESTING",
                status=resolved_status,
                payment_status=resolved_status,
                is_final=is_final,
                payer_currency="USDT",
                txid=f"mock_tx_{invoice.external_id}",
                url=f"https://example.com/mock-cryptomus/{invoice.external_id}",
            )

        fallback_uuid = lookup_external_id or f"mock_uuid_{uuid4().hex[:10]}"
        return CryptomusPaymentStatusResponse(
            uuid=fallback_uuid,
            order_id=order_id,
            amount=0.0,
            payment_amount=0.0,
            currency="USD",
            network="TRC20",
            address="T-MOCK-ADDRESS-TRC20-FOR-TESTING",
            status="pending",
            payment_status="pending",
            is_final=False,
            payer_currency="USDT",
            txid=None,
            url=f"https://example.com/mock-cryptomus/{fallback_uuid}",
        )

    async def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_enabled()

        body = self._serialize_payload(payload)
        headers = {
            "merchant": self._merchant_id,
            "sign": self._generate_signature(payload),
            "Content-Type": "application/json",
        }
        session = await self._get_session()
        url = f"{self._base_url}{path}"

        try:
            async with session.post(
                url,
                data=body.encode("utf-8"),
                headers=headers,
                proxy=self._proxy_url,
            ) as response:
                response_text = await response.text()
        except asyncio.TimeoutError as exc:  # type: ignore[name-defined]
            raise CryptomusAPIError(f"Cryptomus request timed out: {path}") from exc
        except aiohttp.ClientError as exc:
            raise CryptomusAPIError(f"Cryptomus transport error: {exc}") from exc

        if response.status >= 400:
            logger.error(
                "Cryptomus HTTP error path=%s status=%s body=%s",
                path,
                response.status,
                response_text,
            )
            raise CryptomusAPIError(
                f"Cryptomus returned HTTP {response.status} for {path}."
            )

        try:
            response_data = orjson.loads(response_text)
        except orjson.JSONDecodeError as exc:
            logger.error("Cryptomus returned invalid JSON path=%s body=%s", path, response_text)
            raise CryptomusAPIError("Cryptomus returned invalid JSON response.") from exc

        if response_data.get("state") not in (0, "0", None):
            error_message = response_data.get("message") or response_data.get("errors") or response_data
            logger.error("Cryptomus API business error path=%s payload=%s", path, error_message)
            raise CryptomusAPIError(f"Cryptomus API error: {error_message}")

        result = response_data.get("result")
        if not isinstance(result, dict):
            raise CryptomusAPIError("Cryptomus API returned unexpected payload format.")

        return result

    async def create_payment(
        self,
        amount: float,
        currency: str,
        order_id: str,
        *,
        network: str | None = None,
        to_currency: str | None = None,
        url_return: str | None = None,
        url_success: str | None = None,
        url_callback: str | None = None,
        additional_data: str | None = None,
        is_payment_multiple: bool = True,
        lifetime: int | None = None,
    ) -> CryptomusCreatePaymentResponse:
        payload: dict[str, Any] = {
            "amount": self._format_amount(amount),
            "currency": currency,
            "order_id": order_id,
            "is_payment_multiple": is_payment_multiple,
            "lifetime": lifetime or config.CRYPTOMUS_INVOICE_LIFETIME_SEC,
            "accuracy_payment_percent": config.CRYPTOMUS_ACCURACY_PAYMENT_PERCENT,
        }
        if network:
            payload["network"] = network
        if to_currency:
            payload["to_currency"] = to_currency
        if url_return:
            payload["url_return"] = url_return
        if url_success:
            payload["url_success"] = url_success
        if url_callback:
            payload["url_callback"] = url_callback
        if additional_data:
            payload["additional_data"] = additional_data

        if self._dev_mode:
            return await self._mock_create_payment(
                amount=amount,
                currency=currency,
                order_id=order_id,
                network=network,
            )

        result = await self._request(config.CRYPTOMUS_CREATE_PAYMENT_PATH, payload)
        return CryptomusCreatePaymentResponse(
            uuid=str(result["uuid"]),
            order_id=str(result["order_id"]),
            amount=self._normalize_float(result.get("amount", amount)),
            currency=str(result.get("currency", currency)),
            network=result.get("network"),
            address=result.get("address"),
            url=result.get("url"),
            payment_status=result.get("payment_status"),
            status=result.get("status"),
            is_final=bool(result.get("is_final")) if result.get("is_final") is not None else None,
        )

    async def get_status(
        self,
        *,
        uuid: str | None = None,
        order_id: str | None = None,
    ) -> CryptomusPaymentStatusResponse:
        if not uuid and not order_id:
            raise ValueError("Either uuid or order_id must be provided.")

        if self._dev_mode:
            return await self._mock_get_status(uuid=uuid, order_id=order_id)

        payload: dict[str, Any] = {}
        if uuid:
            payload["uuid"] = uuid
        if order_id:
            payload["order_id"] = order_id

        result = await self._request(config.CRYPTOMUS_PAYMENT_INFO_PATH, payload)
        resolved_status = str(result.get("status") or result.get("payment_status") or "unknown")
        return CryptomusPaymentStatusResponse(
            uuid=str(result["uuid"]),
            order_id=result.get("order_id"),
            amount=self._normalize_float(result.get("amount")),
            payment_amount=self._normalize_float(result.get("payment_amount")),
            currency=result.get("currency"),
            network=result.get("network"),
            address=result.get("address"),
            status=resolved_status,
            payment_status=result.get("payment_status"),
            is_final=bool(result.get("is_final")),
            payer_currency=result.get("payer_currency"),
            txid=result.get("txid"),
            url=result.get("url"),
        )

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None


cryptomus_client = CryptomusClient()
