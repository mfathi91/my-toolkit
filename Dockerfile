FROM python:3.13-slim

# Install ffmpeg and VA-API libraries
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    vainfo \
    libva-drm2 \
    libva2 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Intel media driver only on amd64 (not needed for ARM)
RUN if [ "$(dpkg --print-architecture)" = "amd64" ]; then \
    echo "deb http://deb.debian.org/debian trixie non-free non-free-firmware" > /etc/apt/sources.list.d/non-free.list && \
    apt-get update && \
    apt-get install -y intel-media-va-driver && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp output

# Expose port
EXPOSE 8765

# Run the application
CMD ["uv", "run", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8765"]
