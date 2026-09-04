import asyncio
import logging
import os
import uuid

from dotenv import load_dotenv
from yookassa import Configuration, Payment

load_dotenv()

YOOKASSA_RETURN_URL = "https://t.me/SellMindAIBot"
logger = logging.getLogger(__name__)


class PaymentConfigurationError(RuntimeError):
    pass


def _configure_yookassa():
    shop_id = os.environ.get("YOOKASSA_SHOP_ID")
    secret_key = os.environ.get("YOOKASSA_SECRET_KEY")
    logger.info(
        "YooKassa config: shop_id_present=%s shop_id_prefix=%s "
        "secret_key_present=%s",
        bool(shop_id),
        shop_id[:4] if shop_id else "",
        bool(secret_key),
    )
    if not shop_id or not secret_key:
        raise PaymentConfigurationError(
            "YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY are required"
        )
    Configuration.configure(shop_id, secret_key)


def _create_payment_sync(
    telegram_id,
    tariff,
    payment_method_type,
    customer_email,
):
    from subscription_service import TARIFF_DETAILS

    details = TARIFF_DETAILS[tariff]
    _configure_yookassa()

    amount_value = f"{details['price']}.00"
    idempotence_key = str(uuid.uuid4())
    payment_payload = {
        "amount": {
            "value": amount_value,
            "currency": "RUB",
        },
        "capture": True,
        "payment_method_data": {"type": payment_method_type},
        "confirmation": {
            "type": "redirect",
            "return_url": YOOKASSA_RETURN_URL,
        },
        "description": f"Подписка SELLMIND {details['name']} на 30 дней",
        "metadata": {
            "telegram_id": str(telegram_id),
            "tariff": tariff,
        },
        "receipt": {
            "customer": {"email": customer_email},
            "items": [
                {
                    "description": f"Подписка SELLMIND {details['name']}",
                    "quantity": "1.00",
                    "amount": {
                        "value": amount_value,
                        "currency": "RUB",
                    },
                    "vat_code": 1,
                    "payment_subject": "service",
                    "payment_mode": "full_payment",
                }
            ],
        },
    }

    logger.info(
        "Creating YooKassa payment: tariff=%s method=%s amount_value=%s "
        "idempotence_key=%s",
        tariff,
        payment_method_type,
        amount_value,
        idempotence_key,
    )
    try:
        payment = Payment.create(payment_payload, idempotence_key)
    except Exception as error:
        logger.error(
            "YooKassa Payment.create failed: %s; error_type=%s; "
            "error_code=%s; description=%s",
            str(error),
            type(error).__name__,
            getattr(error, "code", None),
            getattr(error, "description", None),
            exc_info=True,
        )
        raise

    return payment.confirmation.confirmation_url


async def create_yookassa_payment(
    telegram_id,
    tariff,
    payment_method_type,
    customer_email,
):
    if payment_method_type not in {"bank_card", "sbp"}:
        raise ValueError("Unsupported YooKassa payment method")
    return await asyncio.to_thread(
        _create_payment_sync,
        telegram_id,
        tariff,
        payment_method_type,
        customer_email,
    )
