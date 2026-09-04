from pathlib import Path
import os
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from starlette.requests import Request
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from telegram import Bot
from yookassa.domain.notification import WebhookNotificationFactory

from database import (
    claim_yookassa_payment,
    ensure_subscription_columns,
    get_paid_generation_info,
    get_remaining_free_generations,
    get_saved_products,
    get_user,
    create_user_if_not_exists,
    expire_subscription_if_needed,
    init_db,
)
from telegram_bot import is_unlimited_user
from payments import create_yookassa_payment
from subscription_service import TARIFF_DETAILS, activate_paid_subscription

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "sellmind-mini-app.html"
WEBHOOK_URL = (
    "https://avelon-marketplace-ai-production.up.railway.app"
    "/yookassa/webhook"
)
SUBSCRIPTION_PERIOD = 2592000
MAX_WEBAPP_AUTH_AGE = 86400

load_dotenv(BASE_DIR / ".env")


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
        auth_date = int(values["auth_date"])
        if abs(int(time.time()) - auth_date) > MAX_WEBAPP_AUTH_AGE:
            return None
        user = json.loads(values["user"])
        if not isinstance(user.get("id"), int):
            return None
        return user
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _init_data_from_request(request):
    return (
        request.headers.get("X-Telegram-Init-Data")
        or request.query_params.get("initData")
        or request.query_params.get("init_data")
    )


def _authenticated_webapp_user(request):
    return _telegram_webapp_user(_init_data_from_request(request))


def _profile_payload(user_data):
    user_id = user_data["id"]
    username = user_data.get("username")
    first_name = user_data.get("first_name", "")
    create_user_if_not_exists(user_id, username)
    expire_subscription_if_needed(user_id)
    db_user = get_user(user_id)
    saved_products = get_saved_products(user_id)
    unlimited = is_unlimited_user(
        type("TelegramUser", (), {"id": user_id, "username": username})()
    )
    tariff = db_user[2] if db_user and not unlimited else "unlimited" if unlimited else "free"
    tariff_names = {
        "free": "Бесплатный",
        "basic": "Базовый",
        "premium": "Премиум",
        "unlimited": "Безлимит",
    }
    if tariff == "free":
        generation_limit = 3
        generations_used = max(3 - get_remaining_free_generations(user_id), 0)
    elif unlimited:
        generation_limit = None
        generations_used = 0
    else:
        generations_used, generation_limit = get_paid_generation_info(user_id)
    return {
        "telegram_id": user_id,
        "username": username,
        "first_name": first_name,
        "tariff": tariff,
        "tariff_display": tariff_names[tariff],
        "generations_used": generations_used,
        "generation_limit": generation_limit,
        "generations_remaining": (
            None if generation_limit is None
            else max(generation_limit - generations_used, 0)
        ),
        "saved_products_count": len(saved_products),
    }


def _saved_product_payload(product):
    return {
        "id": product[0],
        "title": product[1],
        "description": product[2],
        "purchase_price": product[4],
        "recommended_price": product[5],
        "city": product[6],
        "competition": product[7],
        "sale_probability": product[8],
        "sale_time": product[9],
        "created_at": product[10],
    }


async def profile_route(request: Request):
    user = _authenticated_webapp_user(request)
    if not user:
        return JSONResponse({"error": "Invalid or missing Telegram initData"}, status_code=401)
    return JSONResponse(_profile_payload(user))


async def saved_products_route(request: Request):
    user = _authenticated_webapp_user(request)
    if not user:
        return JSONResponse({"error": "Invalid or missing Telegram initData"}, status_code=401)
    products = get_saved_products(user["id"])
    return JSONResponse({"products": [_saved_product_payload(product) for product in products]})


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
        Route("/api/profile", profile_route, methods=["GET"]),
        Route("/api/saved-products", saved_products_route, methods=["GET"]),
        Route("/api/yookassa/create", create_yookassa_payment_route, methods=["POST"]),
        Route("/yookassa/webhook", yookassa_webhook, methods=["POST"]),
        Route("/{path:path}", page_fallback),
    ]
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
