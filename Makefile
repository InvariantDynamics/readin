.PHONY: check format lint test validate demo workbench

check: lint test validate

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest -q

validate:
	uv run python scripts/validate_contracts.py

demo:
	uv run python scripts/demo_local_loop.py

workbench:
	uv run python scripts/serve_demo_workbench.py
