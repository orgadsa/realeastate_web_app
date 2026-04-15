from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import (
    delete_property,
    get_all_properties,
    get_stats,
    init_db,
    update_property_field,
    upsert_property,
)

BASE_DIR = Path(__file__).parent
app = FastAPI(title="ניהול נכסים")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

STATUSES = ["חדש", "שיחה ראשונית", "ביקרתי", "חוו\"ד שמאי", "משא ומתן", "נסגר", "נפסל"]


@app.on_event("startup")
def startup():
    init_db()


@app.get("/share", response_class=HTMLResponse)
async def share_import(request: Request, background_tasks: BackgroundTasks, url: str = ""):
    """Accept a property URL via GET (for iOS Shortcuts / share sheet integration)."""
    url = url.strip()
    if not url:
        return templates.TemplateResponse(
            request=request,
            name="share.html",
            context={"status": "error", "message": "לא התקבל לינק"},
        )

    if "yad2.co.il" not in url and "madlan.co.il" not in url:
        return templates.TemplateResponse(
            request=request,
            name="share.html",
            context={"status": "error", "message": "הלינק חייב להיות מ-yad2 או madlan"},
        )

    background_tasks.add_task(_scrape_and_save, url)
    return templates.TemplateResponse(
        request=request,
        name="share.html",
        context={"status": "ok", "message": "הנכס בדרך! הוא יופיע בדשבורד בעוד כמה שניות"},
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, status: str | None = None):
    properties = get_all_properties(status_filter=status)
    stats = get_stats()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "properties": properties,
            "stats": stats,
            "statuses": STATUSES,
            "current_filter": status or "הכל",
        },
    )


@app.post("/api/import")
async def import_property(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "URL is required"}, status_code=400)

    if "yad2.co.il" not in url and "madlan.co.il" not in url:
        return JSONResponse(
            {"error": "URL must be from yad2.co.il or madlan.co.il"},
            status_code=400,
        )

    background_tasks.add_task(_scrape_and_save, url)
    return JSONResponse({"status": "scraping", "message": "הסקרייפינג התחיל, הנכס יופיע בקרוב..."})


async def _scrape_and_save(url: str):
    from scraper.browser import get_browser, get_page
    from scraper.parsers import get_parser_for_url

    try:
        parser = get_parser_for_url(url)
        async with get_browser() as browser:
            async with get_page(browser) as page:
                listing = await parser.parse(page, url)
        data = listing.model_dump()
        upsert_property(data)
    except Exception as e:
        print(f"Scraping error for {url}: {e}")


@app.post("/api/push")
async def push_property(request: Request):
    """
    Receive scraped listing data directly (from local CLI).
    Usage: python3 -m scraper --push <render-url> <yad2-link>
    """
    body = await request.json()
    if not body.get("url"):
        return JSONResponse({"error": "url field is required"}, status_code=400)
    prop_id = upsert_property(body)
    return JSONResponse({"status": "ok", "id": prop_id})


@app.patch("/api/properties/{prop_id}")
async def update_field(prop_id: int, request: Request):
    body = await request.json()
    field = body.get("field")
    value = body.get("value", "")
    if not field:
        return JSONResponse({"error": "field is required"}, status_code=400)
    ok = update_property_field(prop_id, field, value)
    if not ok:
        return JSONResponse({"error": "invalid field"}, status_code=400)
    return JSONResponse({"status": "ok"})


@app.delete("/api/properties/{prop_id}")
async def remove_property(prop_id: int):
    delete_property(prop_id)
    return JSONResponse({"status": "ok"})


@app.get("/api/properties")
async def list_properties(status: str | None = None):
    return get_all_properties(status_filter=status)


@app.get("/api/stats")
async def stats():
    return get_stats()
