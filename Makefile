.PHONY: build test serve sample lint format

build:
	python -m src.build_site

sample:
	python -m src.build_site

test:
	pytest

lint:
	ruff check src tests

format:
	black src tests

serve:
	python -m http.server --directory site 8000
