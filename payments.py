import asyncio
import os

from dotenv import load_dotenv
from yookassa import Configuration, Payment

load_dotenv()

YOOKASSA_RETURN_URL = "https://t.me/SellMindAIBot"


class PaymentConfigurationError(RuntimeError):
    pass


def _configure_yookassa():
    shop_id = os.environ.get("YOOKASSA_SHOP_ID")
    secret_key = os.environ.get("YOOKASSA_SECRET_KEY")
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

    payment = Payment.create(
        {
            "amount": {
                "value": f"{details['price']}.00",
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
                            "value": f"{details['price']}.00",
                            "currency": "RUB",
                        },
                        "vat_code": 1,
                        "payment_subject": "service",
                        "payment_mode": "full_payment",
                    }
                ],
            },
        }
    )
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
