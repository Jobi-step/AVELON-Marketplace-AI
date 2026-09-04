from pathlib import Path
import os
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

from starlette.requests import Request
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from telegram import Bot
from yookassa.domain.notification import WebhookNotificationFactory

from database import claim_yookassa_payment, ensure_subscription_columns, init_db
from payments import create_yookassa_payment
from subscription_service import TARIFF_DETAILS, activate_paid_subscription

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "sellmind-mini-app.html"
WEBHOOK_URL = (
    "https://avelon-marketplace-ai-production.up.railway.app"
    "/yookassa/webhook"
)
SUBSCRIPTION_PERIOD = 2592000


async def homepage(request):
    return FileResponse(HTML_PATH, media_type="text/html")


async def page_fallback(request):
    return FileResponse(HTML_PATH, media_type="text/html")


def _telegram_webapp_user(init_data):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token or not init_data:
        return None

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        return None

    try:
        return json.loads(values["user"])
    except (KeyError, json.JSONDecodeError):
        return None


async def create_yookassa_payment_route(request: Request):
    try:
        payload = await request.json()
        user = _telegram_webapp_user(payload.get("init_data", ""))
        tariff = payload.get("tariff")
        payment_method_type = payload.get("payment_method_type")
        customer_email = str(payload.get("customer_email", "")).strip()

        if not user or tariff not in TARIFF_DETAILS:
            return JSONResponse({"error": "Invalid Telegram session or tariff"}, status_code=400)
        if payment_method_type not in {"bank_card", "sbp"}:
            return JSONResponse({"error": "Invalid payment method"}, status_code=400)
        if "@" not in customer_email:
            return JSONResponse({"error": "Valid email is required"}, status_code=400)

        payment_url = await create_yookassa_payment(
            telegram_id=user["id"],
            tariff=tariff,
            payment_method_type=payment_method_type,
            customer_email=customer_email,
        )
        return JSONResponse({"payment_url": payment_url})
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to create YooKassa payment")
        return JSONResponse({"error": "Payment creation failed"}, status_code=500)


async def yookassa_webhook(request: Request):
    try:
        event_json = await request.json()
        notification = WebhookNotificationFactory().create(event_json)
        if notification.event != "payment.succeeded":
            return JSONResponse({"ok": True})

        payment = notification.object
        if not claim_yookassa_payment(payment.id):
            return JSONResponse({"ok": True})
        metadata = payment.metadata or {}
        telegram_id = int(metadata["telegram_id"])
        tariff = metadata["tariff"]
        subscription_until = int(
            (datetime.now(timezone.utc) + timedelta(seconds=SUBSCRIPTION_PERIOD)).timestamp()
        )
        details = activate_paid_subscription(
            telegram_id=telegram_id,
            tariff=tariff,
            subscription_until=subscription_until,
        )

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if bot_token:
            async with Bot(bot_token) as bot:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        "✅ Подписка активирована!\n\n"
                        f"💳 Тариф: {details['name']}\n"
                        f"🤖 Генераций: {details['generation_limit']}\n"
                        "📅 Срок: 30 дней\n\n"
                        "Можно создавать объявления."
                    ),
                )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to process YooKassa webhook")

    return JSONResponse({"ok": True})


init_db()
ensure_subscription_columns()


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/sellmind-mini-app.html", homepage),
        Route("/api/yookassa/create", create_yookassa_payment_route, methods=["POST"]),
        Route("/yookassa/webhook", yookassa_webhook, methods=["POST"]),
        Route("/{path:path}", page_fallback),
    ]
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
