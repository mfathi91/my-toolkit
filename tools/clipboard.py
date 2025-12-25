import asyncio
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

router = APIRouter(prefix="/clipboard", tags=["clipboard"])
clipboard_content = ""
clear_task = None

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


async def clear_clipboard_after_delay():
  """Clear clipboard content after 30 seconds"""
  await asyncio.sleep(30)
  global clipboard_content
  clipboard_content = ""


@router.get("/", response_class=HTMLResponse)
async def clipboard_ui(request: Request) -> HTMLResponse:
  """Serve the clipboard UI page"""
  return templates.TemplateResponse("clipboard.html", {"request": request})


@router.get("/clip")
async def get_clipboard_content() -> dict:
  return {"text": clipboard_content}


@router.post("/clip")
async def set_clipboard_content(text: str) -> dict:
  global clipboard_content, clear_task
  if clear_task and not clear_task.done():
    clear_task.cancel()
  clipboard_content = text
  clear_task = asyncio.create_task(clear_clipboard_after_delay())
  return {"status": "success", "text": clipboard_content}
