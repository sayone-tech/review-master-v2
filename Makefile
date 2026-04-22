.PHONY: up down migrate makemigrations shell test lint typecheck seed fmt

up:
	docker-compose up -d

down:
	docker-compose down

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
