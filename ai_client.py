import os
import json
import base64

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("AITUNNEL_API_KEY")

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
    photos=None,
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

Также проанализируй приложенные фотографии товара.

Используй фотографии как дополнительный источник данных:
- определи тип товара;
- цвет;
- визуальные особенности;
- элементы дизайна;
- надписи и логотипы;
- примерную категорию;
- проверь, соответствует ли текст поставщика фотографиям.

Если текст поставщика и фотографии противоречат друг другу:
- не выдумывай;
- отдавай приоритет тому, что можно уверенно определить;
- при сомнении возвращай "не определено".

Не делай вывод об оригинальности товара по фотографиям.

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
- описание для Avito всегда делай по одной структуре;

СТРУКТУРА ОПИСАНИЯ:

1. Первая строка:
🔥 бренд + тип товара + цвет + короткая привлекательная характеристика.

2. Затем короткий абзац из 1–2 предложений:
кратко объясни, чем товар интересен покупателю.
Не используй пафосные или дешёвые рекламные выражения.

3. Затем характеристики ОБЯЗАТЕЛЬНО каждая с новой строки:

🏷 Бренд: ...
👕 Тип товара: ...
🎨 Цвет: ...
📏 Размеры: ...
🧵 Материал: ...
🇹🇷 Производство: ... — только если производство известно

4. Затем отдельной строкой:

📦 Доставка по всей России.

5. Если пользователь указал помощь с размером:

📐 Поможем подобрать подходящий размер.

6. В самом конце отдельным абзацем:

📩 Пишите или звоните прямо сейчас — отвечу на вопросы и помогу с выбором.

Правила оформления:
- между смысловыми блоками оставляй пустую строку;
- характеристики никогда не объединяй в одну строку;
- используй только уместные красивые эмодзи;
- не превращай описание в длинную статью;
- длина описания примерно 250–450 символов;
- не пиши больше одного короткого продающего абзаца перед характеристиками;
- первый продающий абзац максимум 1–2 предложения;
- не повторяй одни и те же преимущества разными словами;
- не используй длинные рекламные вступления;
- после короткого вступления сразу переходи к характеристикам;
- не используй слова "идеальный", "безупречный", "гарантированно", "эксклюзивный" без оснований;
- не выдумывай скидки, возврат, наличие, гарантии, качество или другие условия;
- не пиши, оригинальный товар или нет;
- - не пиши, оригинальный товар или нет;
- заголовок оптимизируй под поиск Avito;
- заголовок оптимизируй под поиск Avito;
- заголовок делай максимально простым и поисковым;
- структура заголовка: Бренд + тип товара + цвет + пол, если это помогает поиску;
- не используй слова "стильный", "тёплый", "новая коллекция", "идеальный", "премиальный", "унисекс" без необходимости;
- не добавляй лишние характеристики в заголовок;
- не перегружай заголовок;
- приоритет — естественный запрос покупателя на Avito;
- примеры хороших заголовков:
  "Balenciaga брюки мужские бежевые"
  "Armani Exchange олимпийка мужская чёрная"
  "Stone Island худи мужская розовая"
  "Maison Margiela футболка мужская белая"
- не выдумывай неизвестные характеристики;
- не выдумывай неизвестные характеристики;
- если характеристику нельзя определить уверенно — напиши "не определено";
- не используй Москву и Санкт-Петербург по умолчанию;
- город выбирай по балансу спроса, конкуренции и стоимости продвижения;
- если нет явных причин выбирать дорогой и перегретый рынок, предпочитай более выгодный город;
- recommended_price рассчитывай как реалистичную цену для продажи;
- minimum_price рассчитывай как нижнюю разумную границу цены для быстрой продажи;
- expected_profit рассчитывай как разницу между recommended_price и purchase_price;
- кратко объясняй, почему выбран этот город;
- поле sale_probability всегда возвращай строкой в формате от 0% до 100%;
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

    ai_price = result.get("recommended_price", 0)

    minimum_allowed_price = purchase_price + 1000
    maximum_allowed_price = purchase_price + 1600

    if (
        not isinstance(ai_price, (int, float))
        or ai_price < minimum_allowed_price
        or ai_price > maximum_allowed_price
    ):
        ai_price = purchase_price + 1200

    result["recommended_price"] = round(ai_price / 10) * 10

    city = str(result.get("city", "")).strip()

    blocked_default_cities = {
        "москва",
        "санкт-петербург",
        "спб",
    }

    if not city or city.lower() in blocked_default_cities:
        result["city"] = "Казань"
        result["city_reason"] = (
            "Выбран крупный региональный рынок с хорошим спросом "
            "и более умеренной конкуренцией, чем в Москве и Санкт-Петербурге."
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