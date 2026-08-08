import os

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
    sizes,
    material,
    extra_info,
):
    if client is None:
        return "AI не настроен"

    prompt = f"""
Ты — AVELON Marketplace AI.

Создай карточку объявления для Avito.

Данные товара:
Описание поставщика: {supplier_text}
Закупочная цена: {purchase_price} ₽
Размеры: {sizes}
Материал: {material}
Дополнительная информация: {extra_info}

Правила:
- заголовок максимум 50 символов;
- укажи бренд, тип товара, цвет и пол, если они известны;
- описание должно быть продающим, но честным;
- не придумывай неизвестные характеристики;
- доставка по всей России;
- минимальная прибыль должна быть не меньше 1000 ₽;
- предложи рекомендованную цену;
- укажи ожидаемую прибыль;
- предложи город публикации;
- оцени конкуренцию;
- оцени вероятность продажи;
- оцени ожидаемый срок продажи.

Ответ выдай структурированно и понятно.
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

    return response.choices[0].message.content