.PHONY: install dev test docker-up docker-down

install:
	python -m pip install -r requirements.txt
	playwright install chromium

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

docker-up:
	docker compose up --build

docker-down:
	docker compose down
