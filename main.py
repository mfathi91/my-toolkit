import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from tools.video_compressor import router as video_router

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

# Setup FastAPI application
app = FastAPI(title="My Toolkit", version="1.0.0")

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Include tool routers
app.include_router(video_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
  """Serve the main page"""
  return templates.TemplateResponse("index.html", {"request": request})
