from database import activate_subscription, create_user_if_not_exists

BASIC_GENERATION_LIMIT = 50
PREMIUM_GENERATION_LIMIT = 150


TARIFF_DETAILS = {
    "basic": {
        "name": "Базовый",
        "generation_limit": BASIC_GENERATION_LIMIT,
        "price": 299,
    },
    "premium": {
        "name": "Премиум",
        "generation_limit": PREMIUM_GENERATION_LIMIT,
        "price": 599,
    },
}


def activate_paid_subscription(telegram_id, tariff, subscription_until):
    details = TARIFF_DETAILS.get(tariff)
    if not details:
        raise ValueError(f"Unknown tariff: {tariff}")

    create_user_if_not_exists(telegram_id=telegram_id)
    activate_subscription(
        telegram_id=telegram_id,
        tariff=tariff,
        subscription_until=subscription_until,
        generation_limit=details["generation_limit"],
    )

    return details
