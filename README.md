# My Toolkit

A FastAPI-based multi-tool web application for personal utilities.

## Project Structure

```
my-toolkit/
├── main.py                      # Main FastAPI application
├── tools/                       # Tools package
│   ├── __init__.py             # Package init
│   └── video_compressor.py     # Video compression tool
├── app/
│   └── templates/
│       └── index.html          # Main web interface
├── temp/                       # Temporary upload directory
├── output/                     # Compressed output directory
└── pyproject.toml             # Project dependencies
```

## Architecture

### Main Application (`main.py`)
- FastAPI application initialization
- Template rendering for main page
- Routes tool-specific API routers

### Tools Module (`tools/`)
Each tool is a separate module with its own APIRouter:
- **video_compressor.py**: Hardware-accelerated video compression
  - Routes prefixed with `/video/`
  - Endpoints: encoder-info, logs, upload, status, download
  - Supports Apple VideoToolbox (M1/M2/M3/M4) and Intel Quick Sync (N100)

## Features

### Video Compressor
- Hardware-accelerated HEVC compression
- Platform detection (Apple Silicon / Intel QSV / Software fallback)
- Real-time log streaming via Sent Events
- Automatic file cleanup after download
- Background task processing
- Job status tracking

## Running the Application

### Using Docker from GitHub Container Registry

```bash
# Pull and run the latest image
docker run -d -p 8765:8765 \
  -v $(pwd)/temp:/app/temp \
  -v $(pwd)/output:/app/output \
  --name my-toolkit \
  ghcr.io/YOUR_USERNAME/my-toolkit:latest

# Or use docker compose with the pre-built image
# Update docker-compose.yml to use: image: ghcr.io/YOUR_USERNAME/my-toolkit:latest
docker compose up -d
```

### Using Docker (Local Build)

```bash
# Build and start the container
docker compose up -d

# View logs
docker compose logs -f

# Stop the container
docker compose down
```

Server runs at: http://localhost:8765

### Local Development

```bash
# Using uv (recommended)
uv run fastapi dev main.py

# Or with regular FastAPI
fastapi dev main.py
```

Development server runs at: http://127.0.0.1:8000

## Adding New Tools

To add a new tool:

1. Create a new file in `tools/` (e.g., `tools/image_optimizer.py`)
2. Create an APIRouter with prefix: `router = APIRouter(prefix="/images", tags=["image-optimizer"])`
3. Add your endpoints to the router
4. Import and include the router in `main.py`: `app.include_router(image_router)`
5. Update the sidebar in `index.html` with the new tool

## API Endpoints

### Video Compressor (`/video/`)
- `GET /video/encoder-info` - Get hardware encoder information
- `GET /video/logs` - Stream logs (SSE)
- `POST /video/upload` - Upload video for compression
- `GET /video/status/{job_id}` - Check compression job status
- `GET /video/download/{filename}` - Download compressed video

## Dependencies

- **fastapi[standard]** >= 0.115.0 - Web framework
- **jinja2** >= 3.1.0 - Template rendering
- **python-multipart** >= 0.0.9 - File upload handling
- **mypy** >= 1.8.0 (dev) - Type checking

## Hardware Support

### Apple Silicon (M1/M2/M3/M4)
- Uses VideoToolbox hardware acceleration
- Encoder: `hevc_videotoolbox`

### Intel CPUs (N100, i3, i5, i7)
- Uses Quick Sync Video acceleration
- Encoder: `hevc_qsv`

### Fallback
- Software encoding with libx265
- Used when no hardware acceleration detected
