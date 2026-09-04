#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  cp .env.example .env
fi

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
