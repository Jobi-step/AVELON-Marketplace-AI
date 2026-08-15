import os
import json
from database import (
    ensure_subscription_columns,
    activate_subscription,
    increment_paid_generation,
    get_paid_generation_info,
    expire_subscription_if_needed,
    init_db,
    create_user_if_not_exists,
    get_user,
    get_remaining_free_generations,
    increment_generation,
    save_product,
    get_saved_products,
    delete_saved_product as db_delete_saved_product,
)

from ai_client import generate_listing
from dotenv import load_dotenv
from telegram import (
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    PreCheckoutQueryHandler,
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BASIC_PRICE_STARS = 299
PREMIUM_PRICE_STARS = 599

BASIC_GENERATION_LIMIT = 50
PREMIUM_GENERATION_LIMIT = 150

SUBSCRIPTION_PERIOD = 2592000

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )

    keyboard = [
        [KeyboardButton("🚀 Создать объявление")],
        [
            KeyboardButton("📦 Сохранённые товары"),
            KeyboardButton("👤 Мой профиль"),
        ],
        [
            KeyboardButton("💎 Управление подпиской"),
            KeyboardButton("📖 Как пользоваться"),
        ],
        [KeyboardButton("⚙️ Настройки")],
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )

    welcome_text = (
        f"👋 Привет, {user.first_name or 'продавец'}!\n\n"
        "🧠 SELLMIND — AI-мозг ваших продаж.\n\n"
        "Превращаем фотографии товара в готовое объявление для Avito за несколько секунд.\n\n"
        "📸 Анализируем фотографии товара\n"
        "✍️ Создаём заголовок и продающее описание\n"
        "💰 Рассчитываем рекомендуемую цену\n"
        "📍 Подбираем город для размещения\n"
        "📊 Оцениваем конкуренцию и вероятность продажи\n\n"
        "🎁 Для старта доступны 3 бесплатные генерации.\n\n"
        "Нажмите «🚀 Создать объявление» — остальное сделает SELLMIND."
    )

    try:
        with open("assets/sellmind_welcome.png", "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=welcome_text,
                reply_markup=reply_markup,
            )
    except FileNotFoundError:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
        )


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if context.user_data.get("stage") != "waiting_photos":
        return

    if "photos" not in context.user_data:
        context.user_data["photos"] = []

    photo = update.message.photo[-1]

    context.user_data["photos"].append(photo.file_id)

    photo_count = len(context.user_data["photos"])

    await update.message.reply_text(
        f"Фото добавлено. Загружено: {photo_count}\n\n"
        "Можешь отправить ещё фото."
    )

async def create_listing_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )

    expire_subscription_if_needed(user.id)

    db_user = get_user(user.id)

    if db_user:
        tariff = db_user[2]

        if tariff == "free":
            remaining_free = get_remaining_free_generations(
                user.id
            )

            if remaining_free <= 0:
                keyboard = [
                    [KeyboardButton("💎 Управление подпиской")],
                    [KeyboardButton("⬅️ Главное меню")],
                ]

                await update.message.reply_text(
                    "🎁 Бесплатные генерации закончились.\n\n"
                    "Вы использовали все 3 бесплатные генерации.\n\n"
                    "Чтобы продолжить создавать объявления, "
                    "оформите подписку.",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard,
                        resize_keyboard=True,
                    ),
                )
                return

        elif tariff in ("basic", "premium"):
            paid_used, paid_limit = get_paid_generation_info(
                user.id
            )

            if paid_used >= paid_limit:
                keyboard = [
                    [KeyboardButton("💎 Управление подпиской")],
                    [KeyboardButton("⬅️ Главное меню")],
                ]

                await update.message.reply_text(
                    "📊 Лимит генераций по вашему тарифу закончился.\n\n"
                    "Новый лимит станет доступен в следующем "
                    "периоде подписки.",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard,
                        resize_keyboard=True,
                    ),
                )
                return
    
    context.user_data.clear()
    context.user_data["stage"] = "waiting_photos"
    context.user_data["photos"] = []

    await update.message.reply_text(
        "Шаг 1 из 3 — Фотографии\n\n"
        "Отправьте фотографии товара.\n"
        "Можно загрузить несколько изображений.\n\n"
        "Когда закончите, нажмите кнопку «✅ Фото загружены».",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("✅ Фото загружены")],
                [KeyboardButton("⬅️ Главное меню")],
            ],
            resize_keyboard=True,
        ),
    )


async def photos_done(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    photos = context.user_data.get("photos", [])

    if not photos:
        await update.message.reply_text(
            "Сначала отправьте хотя бы одну фотографию товара."
        )
        return

    context.user_data["stage"] = "waiting_supplier_text"

    await update.message.reply_text(
        f"Шаг 2 из 3 — Описание\n\n"
        f"Фотографий загружено: {len(photos)}\n\n"
        "Теперь отправьте описание товара от поставщика одним сообщением.",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("⬅️ Главное меню")],
            ],
            resize_keyboard=True,
        ),
    )

async def new_listing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await create_listing_start(update, context)

async def main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    keyboard = [
        [KeyboardButton("🚀 Создать объявление")],
        [
            KeyboardButton("📦 Сохранённые товары"),
            KeyboardButton("👤 Мой профиль"),
        ],
        [
            KeyboardButton("💎 Управление подпиской"),
            KeyboardButton("📖 Как пользоваться"),
        ],
        [KeyboardButton("⚙️ Настройки")],
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )

    await update.message.reply_text(
        "🧠 SELLMIND\n\n"
        "AI-мозг ваших продаж.\n"
        "Создавайте готовые объявления для Avito быстрее и проще.\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
    )

async def save_current_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    ai_result = context.user_data.get("ai_result")
    purchase_price = context.user_data.get("purchase_price")
    supplier_text = context.user_data.get("supplier_text", "")

    if not ai_result:
        await update.message.reply_text(
            "Сначала создайте объявление."
        )
        return

    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )

    product = {
        "title": ai_result.get("title", "Без названия"),
        "description": ai_result.get("description", ""),
        "purchase_price": purchase_price,
        "recommended_price": ai_result.get("recommended_price", 0),
        "city": ai_result.get("city", "не определено"),
        "competition": ai_result.get("competition", "не определено"),
        "sale_probability": ai_result.get(
            "sale_probability",
            "не определено",
        ),
        "sale_time": ai_result.get("sale_time", "не определено"),
        "supplier_text": supplier_text,
    }

    save_product(
        telegram_id=user.id,
        product=product,
    )

    await update.message.reply_text(
        "💾 Товар сохранён."
    )
async def show_saved_products(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )

    saved_products = get_saved_products(user.id)

    if not saved_products:
        keyboard = [
            [KeyboardButton("🚀 Создать объявление")],
            [KeyboardButton("⬅️ Главное меню")],
        ]

        await update.message.reply_text(
            "📦 Сохранённых товаров пока нет.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
            ),
        )
        return

    keyboard = []

    for index, product in enumerate(saved_products, start=1):
        title = product[1] or "Без названия"

        button_text = f"{index}. {title}"

        if len(button_text) > 45:
            button_text = button_text[:42] + "..."

        keyboard.append(
            [KeyboardButton(button_text)]
        )

    keyboard.append(
        [KeyboardButton("⬅️ Главное меню")]
    )

    await update.message.reply_text(
        "📦 Сохранённые товары\n\n"
        "Выберите товар:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

async def open_saved_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = update.message.text.strip()

    try:
        product_number = int(text.split(".", 1)[0])
    except (ValueError, IndexError):
        return

    user = update.effective_user

    saved_products = get_saved_products(user.id)

    if product_number < 1 or product_number > len(saved_products):
        await update.message.reply_text(
            "Товар не найден."
        )
        return

    product = saved_products[product_number - 1]

    product_id = product[0]
    title = product[1] or "Без названия"
    description = product[2] or ""
    purchase_price = product[4] or 0
    recommended_price = product[5] or 0
    city = product[6] or "не определено"
    competition = product[7] or "не определено"
    sale_probability = product[8] or "не определено"
    sale_time = product[9] or "не определено"

    context.user_data["opened_saved_product_id"] = product_id

    keyboard = [
        [KeyboardButton("🗑 Удалить товар")],
        [KeyboardButton("📦 К сохранённым товарам")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    await update.message.reply_text(
        f"📦 Сохранённый товар\n\n"
        f"🏷 {title}\n\n"
        f"{description}\n\n"
        f"💰 Закупочная цена: {purchase_price:,.0f} ₽\n"
        f"💵 Рекомендуемая цена: {recommended_price:,.0f} ₽\n\n"
        f"📍 Город: {city}\n"
        f"📊 Конкуренция: {competition}\n"
        f"🎯 Вероятность продажи: {sale_probability}\n"
        f"⏱ Срок продажи: {sale_time}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

async def delete_saved_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    product_id = context.user_data.get(
        "opened_saved_product_id"
    )

    if product_id is None:
        await update.message.reply_text(
            "Сначала выберите сохранённый товар."
        )
        return

    user = update.effective_user

    db_delete_saved_product(
        product_id=product_id,
        telegram_id=user.id,
    )

    context.user_data.pop(
        "opened_saved_product_id",
        None,
    )

    await update.message.reply_text(
        "🗑 Товар удалён."
    )

    await show_saved_products(
        update,
        context,
    )

async def show_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )
    expire_subscription_if_needed(user.id)

    db_user = get_user(user.id)

    saved_products = get_saved_products(
        user.id
    )

    telegram_id = user.id
    username = (
        f"@{user.username}"
        if user.username
        else "не указан"
    )

    tariff = "free"
    subscription_until = None

    if db_user:
        tariff = db_user[2]
        subscription_until = db_user[5]

    remaining_free = get_remaining_free_generations(
        user.id
    )

    tariff_names = {
        "free": "Бесплатный",
        "basic": "Базовый",
        "premium": "Премиум",
    }

    tariff_display = tariff_names.get(
        tariff,
        tariff,
    )

    subscription_display = (
        subscription_until
        if subscription_until
        else "не активирована"
    )

    keyboard = [
        [KeyboardButton("💎 Управление подпиской")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    profile_text = (
        "👤 ПРОФИЛЬ SELLMIND\n\n"
        f"🆔 Telegram ID: {telegram_id}\n"
        f"👤 Username: {username}\n\n"
        f"💎 Тариф: {tariff_display}\n"
    )

    if tariff == "free":
        profile_text += (
            f"🎁 Бесплатных генераций: {remaining_free} из 3\n"
            "📅 Подписка: не активирована\n"
    )
    else:
        paid_used, paid_limit = get_paid_generation_info(user.id)

        paid_remaining = max(
            paid_limit - paid_used,
            0,
        )
        
        profile_text += (
        f"⚡ Генераций осталось: {paid_remaining} из {paid_limit}\n"
        f"📅 Подписка до: {subscription_display}\n"
        )

    profile_text += (
        f"\n📦 Сохранённых товаров: {len(saved_products)}\n\n"
        "🧠 SELLMIND — AI-мозг ваших продаж."
        )

    await update.message.reply_text(
        profile_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

async def show_subscription(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [KeyboardButton("🟦 Базовая подписка")],
        [KeyboardButton("💎 Премиум подписка")],
        [KeyboardButton("👤 Назад в профиль")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    subscription_text = (
    "💎 ПОДПИСКИ SELLMIND\n\n"
    "Выберите тариф под ваш объём работы:\n\n"
    "🟦 БАЗОВАЯ\n"
    "Для регулярного создания объявлений.\n"
    "• 50 AI-генераций каждые 30 дней\n"
    "• Все основные функции SELLMIND\n"
    "• Сохранённые товары\n"
    "• Аналитика объявления\n\n"
    "💎 ПРЕМИУМ\n"
    "Для активных продавцов и больших объёмов.\n"
    "• 150 AI-генераций каждые 30 дней\n"
    "• Всё из Базовой подписки\n"
    "• Расширенный лимит генераций\n\n"
    "Оплата проходит через Telegram Stars ⭐"
)

    await update.message.reply_text(
        subscription_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

async def show_basic_plan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [KeyboardButton("💳 Оформить базовую")],
        [KeyboardButton("💎 К тарифам")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    basic_text = (
    "🟦 SELLMIND BASIC\n\n"
    "Для регулярного создания объявлений и повседневной работы.\n\n"
    "Что входит:\n"
    "• 50 AI-генераций на 30 дней\n"
    "• Заголовок и продающее описание\n"
    "• Рекомендуемая цена\n"
    "• Выбор города размещения\n"
    "• Аналитика объявления\n"
    "• Сохранённые товары\n\n"
    "💳 Стоимость: 299 ⭐ / 30 дней\n\n"
    "Подписка активируется автоматически после успешной оплаты."
    )

    await update.message.reply_text(
        basic_text
    )

async def buy_basic_plan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )

    invoice_link = await context.bot.create_invoice_link(
        title="SELLMIND Basic",
        description=(
            "50 AI-генераций объявлений каждые 30 дней."
        ),
        payload=f"subscription:basic:{user.id}",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="SELLMIND Basic",
                amount=BASIC_PRICE_STARS,
            )
        ],
        subscription_period=SUBSCRIPTION_PERIOD,
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Оплатить {BASIC_PRICE_STARS} ⭐",
                    url=invoice_link,
                )
            ]
        ]
    )

    await update.message.reply_text(
        "🟦 SELLMIND Basic\n\n"
        "50 AI-генераций каждые 30 дней.\n"
        f"Стоимость: {BASIC_PRICE_STARS} ⭐ / 30 дней.\n\n"
        "Подписка продлевается автоматически через Telegram Stars.",
        reply_markup=keyboard,
    )

async def buy_premium_plan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )

    invoice_link = await context.bot.create_invoice_link(
        title="SELLMIND Premium",
        description=(
            "150 AI-генераций объявлений каждые 30 дней."
        ),
        payload=f"subscription:premium:{user.id}",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="SELLMIND Premium",
                amount=PREMIUM_PRICE_STARS,
            )
        ],
        subscription_period=SUBSCRIPTION_PERIOD,
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Оплатить {PREMIUM_PRICE_STARS} ⭐",
                    url=invoice_link,
                )
            ]
        ]
    )

    await update.message.reply_text(
        "💎 SELLMIND Premium\n\n"
        "150 AI-генераций каждые 30 дней.\n"
        f"Стоимость: {PREMIUM_PRICE_STARS} ⭐ / 30 дней.\n\n"
        "Подписка продлевается автоматически через Telegram Stars.",
        reply_markup=keyboard,
    )

async def precheckout_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.pre_checkout_query

    await query.answer(
        ok=True
    )

async def successful_payment_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    payment = update.message.successful_payment
    user = update.effective_user

    payload = payment.invoice_payload

    parts = payload.split(":")

    if len(parts) != 3:
        return

    payment_type, tariff, payload_user_id = parts

    if payment_type != "subscription":
        return

    if str(user.id) != payload_user_id:
        return

    if tariff == "basic":
        generation_limit = BASIC_GENERATION_LIMIT
        tariff_name = "Базовый"

    elif tariff == "premium":
        generation_limit = PREMIUM_GENERATION_LIMIT
        tariff_name = "Премиум"

    else:
        return

    expiration_date = (
        payment.subscription_expiration_date
    )

    if not expiration_date:
        return

    activate_subscription(
        telegram_id=user.id,
        tariff=tariff,
        subscription_until=expiration_date,
        generation_limit=generation_limit,
    )

    keyboard = [
        [KeyboardButton("🚀 Создать объявление")],
        [KeyboardButton("👤 Мой профиль")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    await update.message.reply_text(
        "✅ Подписка активирована!\n\n"
        f"💳 Тариф: {tariff_name}\n"
        f"🤖 Генераций: {generation_limit}\n"
        "📅 Срок: 30 дней\n\n"
        "Можно создавать объявления.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

async def show_premium_plan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [KeyboardButton("💳 Оформить премиум")],
        [KeyboardButton("💎 К тарифам")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    premium_text = (
    "💎 SELLMIND PREMIUM\n\n"
    "Для активных продавцов, больших объёмов и постоянной работы.\n\n"
    "Что входит:\n"
    "• 150 AI-генераций на 30 дней\n"
    "• Заголовок и продающее описание\n"
    "• Рекомендуемая цена\n"
    "• Выбор города размещения\n"
    "• Аналитика объявления\n"
    "• Сохранённые товары\n"
    "• Увеличенный лимит генераций\n\n"
    "💳 Стоимость: 599 ⭐ / 30 дней\n\n"
    "Подписка активируется автоматически после успешной оплаты."
    )

    await update.message.reply_text(
        premium_text
    )

async def show_settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
    [KeyboardButton("📖 Гайд")],
    [
        KeyboardButton("🔔 Уведомления"),
        KeyboardButton("🌐 Язык"),
    ],
    [KeyboardButton("🆘 Поддержка")],
    [KeyboardButton("⬅️ Главное меню")],
    ]

    await update.message.reply_text(
        "⚙️ Настройки\n\n"
        "Выберите раздел:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

async def show_notifications(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [KeyboardButton("✅ Уведомления включены")],
        [KeyboardButton("⚙️ Назад в настройки")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    await update.message.reply_text(
        "🔔 Уведомления\n\n"
        "Сейчас уведомления включены.\n\n"
        "Позже здесь можно будет управлять уведомлениями о подписке, "
        "новых функциях и важных событиях.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


async def show_language(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [KeyboardButton("🇷🇺 Русский")],
        [KeyboardButton("⚙️ Назад в настройки")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    await update.message.reply_text(
        "🌐 Язык\n\n"
        "Текущий язык: 🇷🇺 Русский",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


async def show_support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [KeyboardButton("📖 Гайд")],
        [KeyboardButton("⚙️ Назад в настройки")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    support_text = (
        "🛟 ПОДДЕРЖКА SELLMIND\n\n"
        "Возник вопрос, ошибка или проблема с оплатой?\n"
        "Мы поможем разобраться.\n\n"
        "👤 Миша — @pulkapup\n"
        "👤 Марат — @upon_aiti\n\n"
        "При обращении желательно сразу указать:\n"
        "• что вы пытались сделать;\n"
        "• на каком этапе возникла проблема;\n"
        "• приложить скриншот ошибки, если он есть.\n\n"
        "⚡ Постараемся помочь максимально быстро."
    )

    await update.message.reply_text(
        support_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )
    
async def show_guide(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [KeyboardButton("🚀 Создать объявление")],
        [KeyboardButton("🆘 Поддержка")],
        [KeyboardButton("⬅️ Главное меню")],
    ]

    guide_text = (
    "📖 КАК ПОЛЬЗОВАТЬСЯ SELLMIND\n\n"
    "Создание объявления занимает всего несколько шагов:\n\n"
    "1️⃣ Нажмите «🚀 Создать объявление».\n\n"
    "2️⃣ Загрузите фотографии товара.\n"
    "Можно отправить несколько изображений — SELLMIND проанализирует их вместе.\n\n"
    "3️⃣ Отправьте краткую информацию о товаре.\n"
    "Например: бренд, модель, размеры, материал и другие данные от поставщика.\n\n"
    "4️⃣ Укажите закупочную цену.\n\n"
    "5️⃣ SELLMIND подготовит:\n"
    "• заголовок;\n"
    "• продающее описание;\n"
    "• рекомендуемую цену;\n"
    "• город размещения;\n"
    "• анализ конкуренции;\n"
    "• вероятность и ориентировочный срок продажи.\n\n"
    "6️⃣ Сохраните готовый товар или перегенерируйте объявление.\n\n"
    "💡 Чем качественнее фотографии и исходная информация, тем точнее результат."
)

    await update.message.reply_text(
        guide_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

async def regenerate_listing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    supplier_text = context.user_data.get(
        "supplier_text",
        "",
    )
    purchase_price = context.user_data.get(
        "purchase_price"
    )
    telegram_photos = context.user_data.get(
        "telegram_photos",
        [],
    )

    if not supplier_text or not purchase_price:
        await update.message.reply_text(
            "Не хватает данных для перегенерации."
        )
        return

    user = update.effective_user

    create_user_if_not_exists(
        telegram_id=user.id,
        username=user.username,
    )

    db_user = get_user(user.id)
    expire_subscription_if_needed(user.id)

    db_user = get_user(user.id)

    if db_user:
        tariff = db_user[2]
        remaining_free = get_remaining_free_generations(user.id)
        if tariff == "free" and remaining_free <= 0:
            keyboard = [
                [KeyboardButton("💎 Управление подпиской")],
                [KeyboardButton("⬅️ Главное меню")],
            ]

            await update.message.reply_text(
                "🎁 Бесплатные генерации закончились.\n\n"
                "Чтобы продолжить создавать объявления, "
                "выберите подписку.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard,
                    resize_keyboard=True,
                ),
            )
            return

        if tariff in ("basic", "premium"):
            paid_used, paid_limit = get_paid_generation_info(
                user.id
            )

            if paid_used >= paid_limit:
                await update.message.reply_text(
                    "📊 Лимит генераций по вашему тарифу закончился."
                )
                return

    await update.message.reply_text(
        "🔄 SELLMIND создаёт новый вариант..."
    )

    try:
        ai_result = generate_listing(
            supplier_text=supplier_text,
            purchase_price=purchase_price,
            extra_info="",
            photos=telegram_photos,
        )

    except Exception as e:
        print(e)

        await update.message.reply_text(
            "Не удалось перегенерировать объявление."
        )
        return

    if isinstance(ai_result, dict) and ai_result.get("error"):
        await update.message.reply_text(
            f"Не удалось создать объявление.\n\n"
            f"{ai_result['error']}"
        )
        return

    if db_user:
        if db_user[2] == "free":
            increment_generation(user.id)

        elif db_user[2] in ("basic", "premium"):
            increment_paid_generation(user.id)

    context.user_data["ai_result"] = ai_result
    context.user_data["stage"] = "listing_ready"

    title = ai_result.get(
        "title",
        "Заголовок не определён",
    )

    description = ai_result.get(
        "description",
        "Описание не определено",
    )

    recommended_price = ai_result.get(
        "recommended_price",
        0,
    )

    city = ai_result.get(
        "city",
        "не определено",
    )

    competition = ai_result.get(
        "competition",
        "не определено",
    )

    sale_probability = ai_result.get(
        "sale_probability",
        "не определено",
    )

    sale_time = ai_result.get(
        "sale_time",
        "не определено",
    )

    result_keyboard = [
        [
            KeyboardButton("💾 Сохранить товар"),
            KeyboardButton("🔄 Перегенерировать"),
        ],
        [
            KeyboardButton("➕ Новое объявление"),
            KeyboardButton("⬅️ Главное меню"),
        ],
    ]

    result_reply_markup = ReplyKeyboardMarkup(
        result_keyboard,
        resize_keyboard=True,
    )

    await update.message.reply_text(
        f"✅ Новый вариант готов!\n\n"
        f"🏷 Заголовок:\n{title}\n\n"
        f"📝 Описание:\n{description}\n\n"
        f"💰 Закупочная цена: {purchase_price:,.0f} ₽\n"
        f"💵 Рекомендуемая цена: {recommended_price:,.0f} ₽\n\n"
        f"📍 Город: {city}\n"
        f"📊 Конкуренция: {competition}\n"
        f"🎯 Вероятность продажи: {sale_probability}\n"
        f"⏱ Срок продажи: {sale_time}",
        reply_markup=result_reply_markup,
    )

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    stage = context.user_data.get("stage")

    if stage == "waiting_supplier_text":
        supplier_text = update.message.text.strip()

        if not supplier_text:
            await update.message.reply_text(
                "Описание не должно быть пустым."
            )
            return

        context.user_data["supplier_text"] = supplier_text
        context.user_data["stage"] = "waiting_purchase_price"

        await update.message.reply_text(
            "Шаг 3 из 3 — Закупочная цена\n\n"
            "Введите закупочную цену товара в рублях.\n\n"
            "Например: 2500"
        )
        return

    elif stage == "waiting_purchase_price":
        price_text = update.message.text.strip().replace(" ", "")

        if not price_text.isdigit():
            await update.message.reply_text(
                "Введите закупочную цену только цифрами.\n\n"
                "Например: 2500"
            )
            return

        purchase_price = int(price_text)

        if purchase_price <= 0:
            await update.message.reply_text(
                "Цена должна быть больше 0."
            )
            return

        context.user_data["purchase_price"] = purchase_price
        context.user_data["stage"] = "generating"

        supplier_text = context.user_data.get("supplier_text", "")

        telegram_photos = []

        for file_id in context.user_data.get("photos", []):
            telegram_file = await context.bot.get_file(file_id)
            photo_bytes = await telegram_file.download_as_bytearray()

            class TelegramPhoto:
                def __init__(self, data):
                    self._data = bytes(data)
                    self.type = "image/jpeg"

                def getvalue(self):
                    return self._data

            telegram_photos.append(TelegramPhoto(photo_bytes))
            context.user_data["telegram_photos"] = telegram_photos

        user = update.effective_user

        create_user_if_not_exists(
            telegram_id=user.id,
            username=user.username,
        )

        db_user = get_user(user.id)
        expire_subscription_if_needed(user.id)

        db_user = get_user(user.id)

        if db_user:
            tariff = db_user[2]
            remaining_free = get_remaining_free_generations(user.id)

            if tariff == "free" and remaining_free <= 0:
                keyboard = [
                    [KeyboardButton("💎 Управление подпиской")],
                    [KeyboardButton("⬅️ Главное меню")],
                ]

                await update.message.reply_text(
                    "🎁 Бесплатные генерации закончились.\n\n"
                    "Вы уже использовали 3 бесплатных объявления.\n"
                    "Чтобы продолжить создавать объявления, выберите подписку.",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard,
                        resize_keyboard=True,
                    ),
                )
                return

            await update.message.reply_text(
                "⌛ SELLMIND анализирует товар и создаёт объявление..."
            )

        db_user = get_user(user.id)

        if db_user:
            tariff = db_user[2]
            remaining_free = get_remaining_free_generations(user.id)

            if tariff == "free" and remaining_free <= 0:
                keyboard = [
                    [KeyboardButton("💎 Управление подпиской")],
                    [KeyboardButton("⬅️ Главное меню")],
                ]

                await update.message.reply_text(
                    "🎁 Бесплатные генерации закончились.\n\n"
                    "Вы уже использовали 3 бесплатных объявления.\n"
                    "Чтобы продолжить создавать объявления, выберите подписку.",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard,
                        resize_keyboard=True,
                    ),
                )
                return

            if tariff in ("basic", "premium"):
                paid_used, paid_limit = get_paid_generation_info(
                    user.id
                )

                if paid_used >= paid_limit:
                    await update.message.reply_text(
                        "📊 Лимит генераций по вашему тарифу закончился."
                    )
                return

        try:
            ai_result = generate_listing(
                supplier_text=supplier_text,
                purchase_price=purchase_price,
                extra_info="",
                photos=telegram_photos, 
            )

            context.user_data["ai_result"] = ai_result

        except Exception as e:
            context.user_data["stage"] = "waiting_purchase_price"

            await update.message.reply_text(
                "Не удалось создать объявление.\n"
                "Попробуйте ещё раз."
            )

            print(e)
            return

        if isinstance(ai_result, dict) and ai_result.get("error"):
            context.user_data["stage"] = "waiting_purchase_price"

            await update.message.reply_text(
                f"Не удалось создать объявление.\n\n"
                f"{ai_result['error']}"
            )
            return

        if db_user:
            if db_user[2] == "free":
                increment_generation(user.id)

            elif db_user[2] in ("basic", "premium"):
                increment_paid_generation(user.id)

        context.user_data["ai_result"] = ai_result
        context.user_data["stage"] = "listing_ready"

        title = ai_result.get("title") or "Заголовок не определён"
        description = ai_result.get("description") or "Описание не определено"
        recommended_price = ai_result.get("recommended_price") or 0
        city = ai_result.get("city") or "не определён"
        competition = ai_result.get("competition") or "не определена"
        sale_probability = ai_result.get("sale_probability") or "не определена"
        sale_time = ai_result.get("sale_time") or "не определён"

        result_keyboard = [
            [
                KeyboardButton("💾 Сохранить товар"),
                KeyboardButton("🔄 Перегенерировать"),
            ],
            [
                KeyboardButton("🚀 Создать объявление"),
                KeyboardButton("⬅️ Главное меню"),
            ],
        ]

        result_reply_markup = ReplyKeyboardMarkup(
            result_keyboard,
            resize_keyboard=True,
        )

        await update.message.reply_text(
            "✅ Объявление готово\n\n"
            f"🏷 {title}\n\n"
            f"{description}\n\n"
            f"💰 Закупочная цена: {purchase_price:,} ₽\n"
            f"💵 Рекомендуемая цена: {recommended_price:,} ₽\n\n"
            f"📍 Город: {city}\n"
            f"📊 Конкуренция: {competition}\n"
            f"🎯 Вероятность продажи: {sale_probability}\n"
            f"⏱ Срок продажи: {sale_time}",
            reply_markup=result_reply_markup,
            )

async def show_terms(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    terms_text = (
        "📄 УСЛОВИЯ ИСПОЛЬЗОВАНИЯ SELLMIND\n\n"
        "SELLMIND предоставляет AI-инструменты для создания и анализа объявлений.\n\n"
        "Пользователь самостоятельно отвечает за:\n"
        "• достоверность информации о товаре;\n"
        "• соответствие объявления правилам Avito;\n"
        "• законность продажи товара;\n"
        "• итоговую цену и условия сделки.\n\n"
        "AI-рекомендации носят информационный характер и не гарантируют продажу товара "
        "в конкретный срок или по конкретной цене.\n\n"
        "Оплачивая подписку, пользователь получает доступ к лимиту AI-генераций "
        "на указанный период.\n\n"
        "По вопросам использования и оплаты обращайтесь в поддержку SELLMIND."
    )

    await update.message.reply_text(terms_text)

async def support_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    support_text = (
        "🛟 ПОДДЕРЖКА SELLMIND\n\n"
        "Возник вопрос или проблема?\n\n"
        "👤 Миша — @pulkapup\n"
        "👤 Марат — @upon_aiti\n\n"
        "При обращении желательно приложить скриншот и кратко описать проблему."
    )

    await update.message.reply_text(support_text)


async def pay_support_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    pay_support_text = (
        "💳 ПОДДЕРЖКА ПО ОПЛАТЕ\n\n"
        "Если подписка не активировалась или возникла проблема с Telegram Stars, "
        "напишите в поддержку:\n\n"
        "👤 Миша — @pulkapup\n"
        "👤 Марат — @upon_aiti\n\n"
        "Укажите ваш Telegram username и приложите скриншот оплаты."
    )

    await update.message.reply_text(pay_support_text)
        
def main():
    init_db()
    ensure_subscription_columns()

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("support", support_command)
    )

    application.add_handler(
        CommandHandler("paysupport", pay_support_command)
    )

    application.add_handler(
        CommandHandler("terms", show_terms)
    )

    application.add_handler(
        CommandHandler("profile", show_profile)
    )

    application.add_handler(
        CommandHandler("guide", show_guide)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^💳 Оформить базовую$"),
            buy_basic_plan,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^💳 Оформить премиум$"),
            buy_premium_plan,
        )
    )

    application.add_handler(
        PreCheckoutQueryHandler(
            precheckout_callback
        )
    )

    application.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment_callback,
        )
    )

    application.add_handler(
        MessageHandler(
        filters.TEXT & filters.Regex("^⬅️ Главное меню$"),
        main_menu,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^💾 Сохранить товар$"),
            save_current_product,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^🔄 Перегенерировать$"),
            regenerate_listing,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^📦 Сохранённые товары$"),
            show_saved_products,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^👤 Мой профиль$"),
            show_profile,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^⚙️ Настройки$"),
            show_settings,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^🔔 Уведомления$"),
            show_notifications,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^🌐 Язык$"),
            show_language,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^🆘 Поддержка$"),
            show_support,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^📖 Гайд$"),
            show_guide,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^⚙️ Назад в настройки$"),
            show_settings,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^💎 Управление подпиской$"),
            show_subscription,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^🟦 Базовая подписка$"),
            show_basic_plan,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^💎 Премиум подписка$"),
            show_premium_plan,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^💎 К тарифам$"),
            show_subscription,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^👤 Назад в профиль$"),
            show_profile,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^📦 К сохранённым товарам$"),
            show_saved_products,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^🗑 Удалить товар$"),
            delete_saved_product,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^\d+\.\s"),
            open_saved_product,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^➕ Новое объявление$"),
            new_listing,
        )
    )

    application.add_handler(
    MessageHandler(
        filters.TEXT & filters.Regex("^🚀 Создать объявление$"),
        create_listing_start,
    )
)

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("^✅ Фото загружены$"),
            photos_done,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & ~filters.Regex("^🚀 Создать объявление$")
            & ~filters.Regex("^✅ Фото загружены$")
            & ~filters.Regex("^⬅️ Главное меню$")
            & ~filters.Regex("^📦 Сохранённые товары$")
            & ~filters.Regex("^👤 Мой профиль$")
            & ~filters.Regex("^⚙️ Настройки$")
            & ~filters.Regex("^🔔 Уведомления$")
            & ~filters.Regex("^🌐 Язык$")
            & ~filters.Regex("^🆘 Поддержка$")
            & ~filters.Regex("^📖 Гайд$")
            & ~filters.Regex("^⚙️ Назад в настройки$")
            & ~filters.Regex("^💎 Управление подпиской$")
            & ~filters.Regex("^🟦 Базовая подписка$")
            & ~filters.Regex("^💎 Премиум подписка$")
            & ~filters.Regex("^💳 Оформить базовую$")
            & ~filters.Regex("^💳 Оформить премиум$")
            & ~filters.Regex("^💎 К тарифам$")
            & ~filters.Regex("^👤 Назад в профиль$")
            & ~filters.Regex("^📦 К сохранённым товарам$")
            & ~filters.Regex("^🗑 Удалить товар$")
            & ~filters.Regex(r"^\d+\.\s")
            & ~filters.Regex("^➕ Новое объявление$")
            & ~filters.Regex("^💾 Сохранить товар$")
            & ~filters.Regex("^🔄 Перегенерировать$"),
            handle_text,
        )
    )

    application.add_handler(
            MessageHandler(filters.PHOTO, handle_photo)
        )

    print("Telegram-бот SELLMIND запущен")

    application.run_polling()


if __name__ == "__main__":
    main()