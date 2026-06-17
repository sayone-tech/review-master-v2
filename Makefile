.PHONY: up down rebuild migrate makemigrations shell test lint typecheck seed fmt worker beat flower

# Pin the Compose project name so container/volume names (e.g. review-master_static_css
# referenced by `rebuild`) stay stable regardless of the checkout directory name.
COMPOSE := docker-compose -p review-master

up:
	$(COMPOSE) up

down:
	$(COMPOSE) down

rebuild:
	$(COMPOSE) down
	docker volume rm review-master_static_css 2>/dev/null || true
	$(COMPOSE) up -d --build

migrate:
	$(COMPOSE) exec web python manage.py migrate

makemigrations:
	$(COMPOSE) exec web python manage.py makemigrations

shell:
	$(COMPOSE) exec web python manage.py shell

test:
	$(COMPOSE) exec web pytest apps/ -x -q

lint:
	pre-commit run --all-files

typecheck:
	$(COMPOSE) exec web mypy .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

seed:
	$(COMPOSE) exec web python manage.py loaddata fixtures/demo.json

worker:
	$(COMPOSE) up worker

beat:
	$(COMPOSE) up beat

flower:
	$(COMPOSE) up flower
