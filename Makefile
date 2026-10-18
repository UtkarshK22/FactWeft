SHELL := /bin/bash
COMPOSE ?= docker compose
API_IMAGE ?= factweft-api:latest

.PHONY: up down logs seed dev test test-restart lint fmt health ps clean image

## image: build the API image directly with buildx
# (avoids the Docker 29 bake sandbox refusing to read the Dockerfile on some hosts)
image:
	docker buildx build ./backend -t $(API_IMAGE) --load

## up: build the API image and start FalkorDB + API
up: image
	$(COMPOSE) up -d --no-build

## down: stop containers (named volume keeps graphs)
down:
	$(COMPOSE) down

## dev: build, then run the API with uvicorn --reload (inside the container)
dev: image
	$(COMPOSE) up -d --no-build
	@echo "API:     http://localhost:8000/api/health"
	@echo "Browser: http://localhost:3000"

## seed: idempotently seed the static demo base (schema, agents, concepts, sources, sessions, procedure)
seed: image
	$(COMPOSE) run --rm api python -m app.memory.seed

## test: unit + integration tests inside the api container
test: image
	$(COMPOSE) run --rm api python -m pytest -q

## test-restart: T01 persistence check from the HOST; restarts the falkordb container.
## Requires host deps: cd backend && pip install -r requirements-dev.txt
test-restart:
	cd backend && python -m pytest -q -m docker_control

lint: image
	$(COMPOSE) run --rm api ruff check app tests

fmt: image
	$(COMPOSE) run --rm api ruff format app tests

health:
	@curl -s http://localhost:8000/api/health
	@echo

logs:
	$(COMPOSE) logs -f api

ps:
	$(COMPOSE) ps

clean:
	$(COMPOSE) down -v
