import hmac
import hashlib
import json
import logging
import uuid
from typing import Optional, Dict, Any
import aiohttp

from bot.config import config

logger = logging.getLogger("TezCheck")

TEZCHECK_BASE_URL = "https://api.tezcheck.uz/api/merchant/v1"


class TezCheckClient:
    """
    TezCheck.uz Savdogar API (Merchant API) integratsiya mijozi.
    Click, Payme, Uzum va boshqa mahalliy to'lov tizimlaridan yagona hisob-faktura
    (bir martalik qat'iy to'lov havolasi - payment_url) yaratish va tekshirish uchun.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cash_desk_code: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: str = TEZCHECK_BASE_URL
    ):
        self.api_key = api_key or config.tezcheck_api_key
        self.cash_desk_code = cash_desk_code or config.tezcheck_cash_desk_code
        self.secret_key = secret_key or config.tezcheck_secret_key
        self.base_url = base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        """API kalit va kassa kodi mavjudligini tekshirish"""
        return bool(self.api_key and self.cash_desk_code)

    @property
    def is_enabled(self) -> bool:
        """Integratsiya yoqilganligini tekshirish (sozlamalarga ko'ra)"""
        return bool(config.tezcheck_enabled and self.is_configured)

    def _get_headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        """Standart HTTP sarlavhalarini shakllantirish"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Cash-Desk-Code": str(self.cash_desk_code),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if idempotency_key:
            headers["Idempotency-Key"] = str(idempotency_key)
        return headers

    async def check_connection(self) -> Dict[str, Any]:
        """
        Kassaning token bilan mosligini tekshirish (GET /me).
        """
        if not self.is_configured:
            return {"ok": False, "error": "TezCheck API kalit yoki Kassa kodi kiritilmagan"}

        url = f"{self.base_url}/me"
        headers = self._get_headers()

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url, headers=headers) as resp:
                    resp_data = await resp.json()
                    if resp.status == 200:
                        return {"ok": True, "data": resp_data.get("data", resp_data)}
                    else:
                        logger.warning(f"TezCheck /me xatosi ({resp.status}): {resp_data}")
                        return {
                            "ok": False,
                            "status": resp.status,
                            "error": resp_data.get("message", "Noma'lum xatolik")
                        }
        except Exception as e:
            logger.error(f"TezCheck connection error: {e}")
            return {"ok": False, "error": str(e)}

    async def create_bill(
        self,
        amount_uzs: int,
        title: str,
        external_reference: str = "",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Yangi to'lov hisobi (bir martalik payment_url) yaratish (POST /bills).

        :param amount_uzs: To'lov summasi so'mda (masalan: 15000)
        :param title: Buyurtma tavsifi (masalan: "1 oylik VIP obuna")
        :param external_reference: Ichki buyurtma ID si (masalan: "VIP-USER-12345")
        :param idempotency_key: Qayta takrorlanishdan saqlash kaliti (agar berilmasa, avtomatik uuid yaratiladi)
        :return: Natija lug'ati (payment_url, bill_id va h.k.)
        """
        if not self.is_configured:
            return {
                "ok": False,
                "error": "TezCheck sozlamalari to'liq kiritilmagan (API_KEY yoki CASH_DESK_CODE yetishmaydi)"
            }

        # TezCheck da summa tiyinda (amount_minor) beriladi: 1 so'm = 100 tiyin
        amount_minor = int(amount_uzs * 100)
        idem_key = idempotency_key or uuid.uuid4().hex

        payload = {
            "amount_minor": amount_minor,
            "title": title[:255] if title else "AniMovie VIP Obuna",
            "external_reference": str(external_reference) if external_reference else idem_key
        }

        url = f"{self.base_url}/bills"
        headers = self._get_headers(idempotency_key=idem_key)

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    resp_data = await resp.json()
                    if resp.status in (200, 201):
                        data = resp_data.get("data", resp_data)
                        bill_id = data.get("id") or data.get("code") or str(external_reference)
                        payment_url = data.get("payment_url")
                        return {
                            "ok": True,
                            "bill_id": bill_id,
                            "payment_url": payment_url,
                            "amount_uzs": amount_uzs,
                            "amount_minor": amount_minor,
                            "raw": data
                        }
                    else:
                        err_msg = resp_data.get("message") or str(resp_data)
                        logger.error(f"TezCheck create_bill xatosi ({resp.status}): {err_msg}")
                        return {
                            "ok": False,
                            "status": resp.status,
                            "error": err_msg,
                            "raw": resp_data
                        }
        except Exception as e:
            logger.error(f"TezCheck create_bill ulanish xatosi: {e}")
            return {"ok": False, "error": str(e)}

    async def get_bill_status(self, bill_id: str) -> Dict[str, Any]:
        """
        Mavjud to'lov hisobi holatini tekshirish (GET /bills/{bill_id}).
        """
        if not self.is_configured:
            return {"ok": False, "error": "TezCheck sozlanmagan"}

        url = f"{self.base_url}/bills/{bill_id}"
        headers = self._get_headers()

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url, headers=headers) as resp:
                    resp_data = await resp.json()
                    if resp.status == 200:
                        data = resp_data.get("data", resp_data)
                        raw_status = data.get("status", "").lower()
                        # TezCheck statuslari: 'paid', 'success', 'pending', 'expired', 'canceled'
                        is_paid = raw_status in ("paid", "success", "completed")
                        return {
                            "ok": True,
                            "status": raw_status,
                            "is_paid": is_paid,
                            "amount_minor": data.get("amount_minor"),
                            "raw": data
                        }
                    else:
                        return {
                            "ok": False,
                            "status": resp.status,
                            "error": resp_data.get("message", "Holatni olib bo'lmadi")
                        }
        except Exception as e:
            logger.error(f"TezCheck get_bill_status xatosi: {e}")
            return {"ok": False, "error": str(e)}

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        TezCheck vebhuk imzosini (HMAC-SHA256) tekshirish.
        """
        if not self.secret_key:
            return True  # Agar maxfiy kalit o'rnatilmagan bo'lsa, tekshiruv o'tkazilmaydi

        try:
            to_sign = payload_bytes
            if timestamp:
                to_sign = f"{timestamp}.".encode("utf-8") + payload_bytes

            expected_sig = hmac.new(
                self.secret_key.encode("utf-8"),
                to_sign,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected_sig.lower(), signature.lower())
        except Exception as e:
            logger.error(f"TezCheck webhook imzo tekshirishda xatolik: {e}")
            return False


# Yagona global mijoz obyekti
tezcheck_client = TezCheckClient()
