import asyncio

from fastapi import APIRouter

router = APIRouter(prefix="/clipboard", tags=["clipboard"])
clipboard_content = ""
clear_task = None


async def clear_clipboard_after_delay():
  """Clear clipboard content after 30 seconds"""
  await asyncio.sleep(30)
  global clipboard_content
  clipboard_content = ""


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
