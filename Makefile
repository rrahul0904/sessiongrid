.PHONY: install dev test migrate downgrade docker-up docker-down

install:
	python -m pip install -r requirements.txt
	playwright install chromium

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

migrate:
	alembic upgrade head

downgrade:
	alembic downgrade -1

docker-up:
	docker compose up --build

docker-down:
	docker compose down
