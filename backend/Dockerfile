FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for rasterio/gdal if needed, 
# though binary wheels often suffice. installing libgl1-mesa-glx for some cv libs if used
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libexpat1 \
    libexpat1-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY app ./app
COPY db ./db
RUN pip install --no-cache-dir .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4000"]
