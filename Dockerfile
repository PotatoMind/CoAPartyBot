FROM python:3.10.6-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH" \
    POETRY_VERSION=1.2.0

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        build-essential

ADD . /app
WORKDIR /app

RUN curl -sSL https://install.python-poetry.org | python
RUN poetry install