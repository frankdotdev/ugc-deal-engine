.PHONY: install test lint start run web worker check up down logs backup

install:
	python -m venv .venv && .venv/bin/pip install -e ".[dev,prod]"

test:
	.venv/bin/python -m pytest

lint:
	.venv/bin/ruff check src tests

check:
	.venv/bin/ugc-engine check-config

start:
	.venv/bin/ugc-engine start

run:
	.venv/bin/ugc-engine start

web:
	.venv/bin/ugc-engine web

worker:
	.venv/bin/ugc-engine worker

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

backup:
	.venv/bin/ugc-engine backup backups/ugc_$$(date +%Y%m%d_%H%M%S).db
