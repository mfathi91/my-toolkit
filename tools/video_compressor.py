"""Video compression tool with hardware acceleration support"""

import logging
import platform
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

# Setup directories
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"

# Create directories if they don't exist
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Configure logging
logger = logging.getLogger(__name__)

# Store job status in memory (use Redis/database for production)
job_status: dict[str, dict[str, Any]] = {}


def get_hardware_encoder() -> tuple[str, str | None]:
  """
  Detect platform and return appropriate hardware encoder settings.
  Returns (encoder, hwaccel) tuple.
  """
  system = platform.system()
  machine = platform.machine()

  if system == "Darwin" and machine in ["arm64", "aarch64"]:
    # Apple Silicon (M1, M2, M3, M4)
    return "hevc_videotoolbox", "videotoolbox"
  elif system == "Linux":
    # Check if it's ARM64 (likely Docker on Mac) - use software encoding
    if machine in ["arm64", "aarch64"]:
      return "libx265", None
    # Intel Quick Sync for x86_64 Linux (Beelink N100)
    return "hevc_qsv", "qsv"
  elif system == "Windows":
    # Intel Quick Sync on Windows
    return "hevc_qsv", "qsv"
  else:
    # Fallback to software encoding
    return "libx265", None


def process_video(job_id: str, filename: str, compression_mode: str = "standard") -> None:
  """
  Process video using hardware acceleration (Apple VideoToolbox or Intel Quick Sync).
  This function runs in the background after upload completes.
  compression_mode: 'standard' or 'deep'
  """
  temp_input = TEMP_DIR / filename
  mode_prefix = "deepcompressed_" if compression_mode == "deep" else "compressed_"
  output_filename = f"{mode_prefix}{filename}"
  output_path = OUTPUT_DIR / output_filename

  # Update job status
  job_status[job_id] = {"status": "processing", "filename": output_filename, "error": None}

  # Get hardware encoder for current platform
  encoder, hwaccel = get_hardware_encoder()

  # Build FFmpeg command based on platform
  command = ["ffmpeg"]

  if hwaccel:
    command.extend(["-hwaccel", hwaccel])

  command.extend(["-i", str(temp_input)])

  # Video encoding settings
  if encoder == "hevc_videotoolbox":
    # Apple Silicon optimized settings
    if compression_mode == "deep":
      command.extend(
        [
          "-c:v",
          "hevc_videotoolbox",
          "-b:v",
          "1M",  # Lower bitrate for deep compression
          "-q:v",
          "50",  # Lower quality for more compression
        ]
      )
    else:
      command.extend(
        [
          "-c:v",
          "hevc_videotoolbox",
          "-b:v",
          "2M",  # Target bitrate for VideoToolbox
          "-q:v",
          "65",  # Quality (0-100, higher = better)
        ]
      )
  elif encoder == "hevc_qsv":
    # Intel Quick Sync optimized settings
    if compression_mode == "deep":
      command.extend(
        [
          "-c:v",
          "hevc_qsv",
          "-global_quality",
          "30",  # Lower quality for deep compression
          "-preset",
          "veryslow",
        ]
      )
    else:
      command.extend(
        [
          "-c:v",
          "hevc_qsv",
          "-global_quality",
          "25",  # Quality: 1-51, lower = better
          "-preset",
          "slow",
        ]
      )
  else:
    # Software fallback (libx265)
    if compression_mode == "deep":
      command.extend(
        [
          "-c:v",
          "libx265",
          "-crf",
          "30",  # Higher CRF for more compression
          "-preset",
          "veryslow",
        ]
      )
    else:
      command.extend(
        [
          "-c:v",
          "libx265",
          "-crf",
          "26",  # Constant Rate Factor
          "-preset",
          "medium",
        ]
      )

  # Common settings for all encoders
  command.extend(
    [
      "-c:a",
      "aac",  # Audio codec
      "-b:a",
      "128k",  # Audio bitrate
      "-tag:v",
      "hvc1",  # Ensures iOS/Nextcloud compatibility
      "-movflags",
      "+faststart",  # Enable streaming
      "-y",  # Overwrite output file if exists
      str(output_path),
    ]
  )

  logger.info(f"Starting {compression_mode} compression for {filename} using {encoder}")

  try:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    result.check_returncode()

    # Get file sizes for comparison
    original_size = temp_input.stat().st_size
    compressed_size = output_path.stat().st_size
    compression_ratio = (1 - compressed_size / original_size) * 100

    # Clean up temp file
    temp_input.unlink()

    # Update job status
    job_status[job_id] = {"status": "completed", "filename": output_filename, "original_size": original_size, "compressed_size": compressed_size, "compression_ratio": compression_ratio, "error": None}

    logger.info(f"✅ Successfully compressed: {filename} -> {output_filename}")
    logger.info(f"   Original: {original_size / (1024 * 1024):.2f} MB, Compressed: {compressed_size / (1024 * 1024):.2f} MB, Saved: {compression_ratio:.1f}%")

  except subprocess.CalledProcessError as e:
    error_msg = e.stderr if e.stderr else str(e)
    job_status[job_id] = {"status": "failed", "filename": None, "error": error_msg}
    logger.error(f"❌ Error compressing {filename}: {error_msg}")

    # Clean up temp file on error
    if temp_input.exists():
      temp_input.unlink()


# Create API router for video compressor
router = APIRouter(prefix="/video", tags=["video-compressor"])


@router.post("/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), compression_mode: str = Form("standard")) -> dict[str, Any]:
  """
  Handle video upload and trigger background compression.
  The video is saved to a temp directory and compression
  starts immediately in the background.
  compression_mode: 'standard' or 'deep'
  """
  if not file.filename:
    raise HTTPException(status_code=400, detail="No filename provided")

  # Generate unique job ID
  job_id = str(uuid.uuid4())

  # Save to temp directory
  temp_path = TEMP_DIR / file.filename

  with open(temp_path, "wb") as buffer:
    content = await file.read()
    buffer.write(content)

  logger.info(f"📤 Uploaded {file.filename} ({len(content) / (1024 * 1024):.2f} MB) - Job ID: {job_id[:8]}")

  # Initialize job status
  job_status[job_id] = {"status": "uploaded", "filename": file.filename}

  # Start compression in background
  background_tasks.add_task(process_video, job_id, file.filename, compression_mode)

  # Detect current platform
  encoder, _ = get_hardware_encoder()
  platform_name = {
    "hevc_videotoolbox": "Apple VideoToolbox (M4)",
    "hevc_qsv": "Intel Quick Sync (N100)",
    "libx265": "Software (CPU)",
  }.get(encoder, "Unknown")

  # Get encoding characteristics
  if encoder == "hevc_videotoolbox":
    codec_details = {
      "codec": "HEVC (H.265)",
      "quality": "65/100" if compression_mode == "standard" else "50/100 (Deep)",
      "bitrate": "2 Mbps" if compression_mode == "standard" else "1 Mbps (Deep)",
      "acceleration": "Hardware (VideoToolbox)",
    }
  elif encoder == "hevc_qsv":
    codec_details = {
      "codec": "HEVC (H.265)",
      "quality": "CQ 25" if compression_mode == "standard" else "CQ 30 (Deep)",
      "preset": "Slow" if compression_mode == "standard" else "Very Slow (Deep)",
      "acceleration": "Hardware (Quick Sync)",
    }
  else:
    codec_details = {
      "codec": "HEVC (H.265)",
      "quality": "CRF 26" if compression_mode == "standard" else "CRF 30 (Deep)",
      "preset": "Medium" if compression_mode == "standard" else "Very Slow (Deep)",
      "acceleration": "Software (CPU)",
    }

  return {
    "message": f"Successfully uploaded {file.filename}. Compression started in background.",
    "job_id": job_id,
    "filename": file.filename,
    "size": len(content),
    "encoder": platform_name,
    "codec_details": codec_details,
    "compression_mode": compression_mode,
  }


@router.get("/status/{job_id}")
async def get_status(job_id: str) -> dict[str, Any]:
  """Check the status of a compression job"""
  if job_id not in job_status:
    raise HTTPException(status_code=404, detail="Job not found")

  return job_status[job_id]


@router.get("/download/{filename}")
async def download_file(filename: str, background_tasks: BackgroundTasks) -> FileResponse:
  """Download a compressed video file and schedule cleanup"""
  file_path = OUTPUT_DIR / filename

  if not file_path.exists():
    raise HTTPException(status_code=404, detail="File not found")

  # Schedule cleanup of the compressed file after download
  def cleanup_files() -> None:
    try:
      # Remove compressed file
      if file_path.exists():
        file_path.unlink()
        logger.info(f"🗑️  Cleaned up compressed file: {filename}")

      # Try to find and remove the original temp file
      original_filename = filename.replace("compressed_", "")
      original_path = TEMP_DIR / original_filename
      if original_path.exists():
        original_path.unlink()
        logger.info(f"🗑️  Cleaned up temp file: {original_filename}")
    except Exception as e:
      logger.warning(f"⚠️  Cleanup error: {e}")

  background_tasks.add_task(cleanup_files)

  return FileResponse(path=file_path, filename=filename, media_type="video/mp4")
