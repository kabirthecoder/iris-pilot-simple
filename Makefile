PYTHON ?= python3

.PHONY: up install run load status test down

up:        ## start PostgreSQL 16 + PostGIS 3.4
	docker compose up -d --wait db

install:   ## create .venv and install
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -q -e ".[dev]"

run:       ## THE one command: set up (idempotent) and run all stages
	.venv/bin/pilot setup
	.venv/bin/pilot run

load:      ## load delivery files into staging: make load FILE=path/to/file.geojson
	.venv/bin/pilot load $(FILE)

status:    ## is each output fresh or STALE?
	.venv/bin/pilot status

test:      ## tests against the database from `make up`
	.venv/bin/pytest -v

down:      ## stop and remove the database
	docker compose down -v
