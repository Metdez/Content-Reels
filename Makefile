.PHONY: setup test cov lint run serve clean venv e2e-seed
PY := ./.venv/bin/python
PIP := ./.venv/bin/pip
# Windows venv lives in .venv/Scripts — run the .exe shims directly there
# (e.g. .venv/Scripts/pytest.exe, .venv/Scripts/ruff.exe).

setup:
	bash scripts/setup.sh

venv:
	python3 -m venv .venv && $(PIP) install --upgrade pip && $(PIP) install -e ".[dev]"

test:
	./.venv/bin/pytest -q

# Coverage is on by default (pyproject addopts); `cov` is an explicit alias.
cov:
	./.venv/bin/pytest -q

lint:
	./.venv/bin/ruff check content_machine tests

# Seed a real rendered fixture job into DATA_DIR for Playwright / manual QA
# (no pipeline run). Start the server first: `make serve`.
e2e-seed:
	$(PY) scripts/seed_fixture.py

run:
	./.venv/bin/content-machine $(ARGS)

serve:
	./.venv/bin/content-machine serve

clean:
	rm -rf .venv data __pycache__ */__pycache__ .pytest_cache *.egg-info
