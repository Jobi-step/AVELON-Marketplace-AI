from pathlib import Path
import os

from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Route

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "sellmind-mini-app.html"


async def homepage(request):
    return FileResponse(HTML_PATH, media_type="text/html")


async def page_fallback(request):
    return FileResponse(HTML_PATH, media_type="text/html")


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/sellmind-mini-app.html", homepage),
        Route("/{path:path}", page_fallback),
    ]
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
