# syntax=docker/dockerfile:1.6
FROM python:3.12-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends git libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

RUN apt-get insatll -y --no-insatll-recommends i2c-tools libgl1-mesa-glx libsm6 libxext6 libxrender-dev pkg-config libzmq3-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt

RUN pip3 install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    --mount=type=cache,target=/root/.cache/pip \
    poetry install --only main --no-root

COPY src ./src
COPY templates ./templates
