import os
import json

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

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

def generate_listing(
    supplier_text,
    purchase_price,
    extra_info,
):
    if client is None:
        return {"error": "AI не настроен"}

    prompt = f"""
Ты — AVELON Marketplace AI.

Твоя задача — на основе данных поставщика создать структурированную карточку объявления для Avito.

Данные пользователя:

Описание поставщика:
{supplier_text}

Закупочная цена:
{purchase_price} ₽

Дополнительная информация:
{extra_info}

Определи:
- бренд;
- тип товара;
- цвет;
- пол;
- размеры;
- материал;
- SEO-заголовок для Avito максимум 50 символов;
- продающее описание;
- рекомендуемую цену;
- город публикации;
- уровень конкуренции;
- вероятность продажи строго в процентах, например "70%";
- ожидаемый срок продажи;
- рекомендации по фотографиям.

Правила:
- не пиши, оригинальный товар или нет;
- доставка по всей России;
- описание должно быть продающим, но честным;
- используй уместные эмодзи;
- минимальная прибыль не меньше 1000 ₽;
- заголовок оптимизируй под поиск Avito;
- город выбирай по балансу спроса, конкуренции и стоимости продвижения;
- если характеристику нельзя определить уверенно — напиши "не определено";
- не выдумывай неизвестные характеристики.
- краткое объяснение, почему выбран этот город;
- поле sale_probability всегда возвращай строкой в формате от 0% до 100%;

Верни результат СТРОГО в JSON.
Без markdown.
Без ```json.
Без какого-либо текста до или после JSON.

Формат:

{{
    "brand": "",
    "product_type": "",
    "color": "",
    "gender": "",
    "sizes": "",
    "material": "",
    "title": "",
    "description": "",
    "recommended_price": 0,
    "city": "",
    "city_reason": ""
    "competition": "",
    "sale_probability": "",
    "sale_time": "",
    "photo_recommendations": ""
}}
"""

    response = client.chat.completions.create(
        model="google/gemini-2.5-flash",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    content = response.choices[0].message.content
    return json.loads(content)