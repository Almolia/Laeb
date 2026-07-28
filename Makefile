.PHONY: up down logs ps build rebuild seed demo test fresh smoke

up:
	docker compose up -d --build

down:
	docker compose down

fresh:
	docker compose down -v && docker compose up -d --build

logs:
	docker compose logs -f $(S)

ps:
	docker compose ps

build:
	docker compose build

seed:
	docker compose exec identity python -m app.seed || python scripts/seed.py

demo:
	bash scripts/demo.sh

smoke:
	bash scripts/smoke.sh

test:
	docker compose exec $(S) pytest -q
