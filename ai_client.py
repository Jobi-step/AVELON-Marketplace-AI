import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

client = (
    OpenAI(
        api_key=api_key,
        base_url="https://api.aitunnel.ru/v1",
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
        model="gpt-5.4-mini",
        messages=[
            {
                "role": "user",
                "content": "Ответь одним словом: READY",
            }
        ],
    )

    return response.choices[0].message.content