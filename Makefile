.PHONY: up down rebuild migrate makemigrations shell test lint typecheck seed fmt worker beat flower

up:
	docker-compose up -d

down:
	docker-compose down

rebuild:
	docker-compose down
	docker volume rm review-master_static_css 2>/dev/null || true
	docker-compose up -d --build

migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

shell:
	docker-compose exec web python manage.py shell

test:
	docker-compose exec web pytest apps/ -x -q

lint:
	pre-commit run --all-files

typecheck:
	docker-compose exec web mypy .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

seed:
	docker-compose exec web python manage.py loaddata fixtures/demo.json

worker:
	docker-compose up worker

beat:
	docker-compose up beat

flower:
	docker-compose up flower
