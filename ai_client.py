import os
import json
import base64
import logging
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

logger = logging.getLogger(__name__)

PRICE_MARKUP_RANGES = {
    "футболка": (500, 900),
    "поло": (500, 900),
    "майка": (500, 900),
    "худи": (900, 1300),
    "свитшот": (900, 1300),
    "толстовка": (900, 1300),
    "зип-худи": (900, 1300),
    "рубашка": (500, 900),
    "блуза": (500, 900),
    "кардиган": (500, 900),
    "джинсы": (700, 1200),
    "брюки": (700, 1200),
    "спортивные штаны": (700, 1200),
    "шорты": (400, 700),
    "ветровка": (900, 1500),
    "бомбер": (900, 1500),
    "лёгкая куртка": (900, 1500),
    "легкая куртка": (900, 1500),
    "зимняя куртка": (1000, 2000),
    "пуховик": (1000, 2000),
    "кроссовки": (500, 1000),
    "кеды": (500, 1000),
    "ботинки": (500, 1000),
    "обувь": (500, 1000),
    "сумка": (300, 700),
    "ремень": (300, 700),
    "кепка": (300, 700),
    "шапка": (300, 700),
    "аксессуары": (300, 700),
}


def fallback_price_markup(result, supplier_text):
    product_type = result.get("product_type", "")
    title = result.get("title", "")
    searchable_text = " ".join(
        str(value).lower()
        for value in (product_type, title, supplier_text)
        if value
    )

    markup_range = (700, 1100)
    matched_keyword = None
    for keyword, candidate_range in PRICE_MARKUP_RANGES.items():
        if keyword in searchable_text:
            markup_range = candidate_range
            matched_keyword = keyword
            break

    markup = sum(markup_range) // 2
    logger.warning(
        "Using price fallback: product_keyword=%s markup_range=%s markup=%s",
        matched_keyword,
        markup_range,
        markup,
    )
    return markup

api_key = os.getenv("AITUNNEL_API_KEY") or os.getenv("OPENAI_API_KEY")
logger.info(
    "AI API key configured: %s (AITUNNEL_API_KEY=%s, OPENAI_API_KEY=%s)",
    bool(api_key),
    bool(os.getenv("AITUNNEL_API_KEY")),
    bool(os.getenv("OPENAI_API_KEY")),
)

client = (
    OpenAI(
        api_key=api_key,
        base_url="https://api.aitunnel.ru/v1",
        timeout=120.0,
    )
    if api_key
    else None
)


def is_ai_configured():
    return client is not None


def test_ai_connection():
    if client is None:
        return "API key is not configured"

    response = client.chat.completions.create(
       model="google/gemini-2.5-flash",
        messages=[
            {
                "role": "user",
                "content": "Ответь одним словом: READY",
            }
        ],
    )

    return response.choices[0].message.content


def load_marketplace_prompt():
    prompt_path = Path(__file__).resolve().parent / "MARKETPLACE_PROMPT.md"
    return prompt_path.read_text(encoding="utf-8")

def generate_listing(
    supplier_text,
    purchase_price,
    extra_info,
    photos=None,
):
    if client is None:
        logger.error(
            "AI client is not configured: no API key found "
            "(AITUNNEL_API_KEY=%s, OPENAI_API_KEY=%s)",
            bool(os.getenv("AITUNNEL_API_KEY")),
            bool(os.getenv("OPENAI_API_KEY")),
        )
        raise RuntimeError("AI client is not configured: API key is missing")

    prompt = (
        load_marketplace_prompt()
        + "\n\n"
        + "## ДАННЫЕ ТЕКУЩЕГО ЗАПРОСА\n\n"
        + f"Описание поставщика:\n{supplier_text}\n\n"
        + f"Закупочная цена: {purchase_price} ₽\n\n"
        + f"Дополнительная информация:\n{extra_info}\n\n"
        + "Проанализируй также приложенные фотографии товара.\n\n"
        + "Верни результат строго в JSON без markdown и текста вне JSON."
    )
    user_content = [
        {
            "type": "text",
            "text": prompt,
        }
    ]

    if photos:
        for photo in photos:
            try:
                photo_bytes = photo.getvalue()
                mime_type = photo.type or "image/jpeg"
                encoded_photo = base64.b64encode(photo_bytes).decode("utf-8")

                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_photo}"
                        },
                    }
                )
            except Exception:
                continue
    response = client.chat.completions.create(
        model="google/gemini-2.5-flash",
        messages=[
            {
                "role": "user",
                "content": user_content,
            }
        ],
    )

    content = response.choices[0].message.content

    if not content or not content.strip():
        raise ValueError(
            "AI вернул пустой ответ. Попробуй создать карточку ещё раз."
        )

    content = content.strip()

    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

        content = content.strip()

    result = json.loads(content)

    listing = result.get("listing") or {}
    pricing = result.get("pricing") or {}
    location = result.get("location") or {}
    market_analysis = result.get("market_analysis") or {}

    result["title"] = listing.get("title") or result.get("title", "")
    result["product_type"] = result.get("product_type") or listing.get(
        "product_type",
        "",
    )
    result["description"] = listing.get("description") or result.get(
        "description",
        "",
    )
    result["recommended_price"] = pricing.get(
        "recommended_price",
        result.get("recommended_price", 0),
    )
    result["city"] = location.get("recommended_city") or result.get(
        "city",
        "",
    )
    result["city_reason"] = location.get("reason") or result.get(
        "city_reason",
        "",
    )
    result["competition"] = market_analysis.get(
        "competition",
        result.get("competition", ""),
    )
    result["sale_probability"] = market_analysis.get(
        "sale_probability_percent",
        result.get("sale_probability", ""),
    )
    result["sale_time"] = market_analysis.get(
        "estimated_sale_time",
        result.get("sale_time", ""),
    )

    ai_price = result.get("recommended_price")
    if (
        isinstance(ai_price, bool)
        or not isinstance(ai_price, (int, float))
        or ai_price <= purchase_price
    ):
        result["recommended_price"] = purchase_price + fallback_price_markup(
            result,
            supplier_text,
        )

    city = str(result.get("city", "")).strip()

    if not city:
        result["city"] = "не определено"
        result["city_reason"] = (
            "Город не определён по ответу AI; требуется уточнение."
        )

    competition = str(result.get("competition", "")).strip().lower()
    sale_probability = str(result.get("sale_probability", "")).strip()
    sale_time = str(result.get("sale_time", "")).strip()

    if not competition or competition in {"не определено", "не определена", "unknown"}:
        result["competition"] = "Средняя"

    if not sale_probability or "не определ" in sale_probability.lower():
        result["sale_probability"] = "70%"

    if not sale_time or "не определ" in sale_time.lower():
        result["sale_time"] = "1–3 недели"

    return result