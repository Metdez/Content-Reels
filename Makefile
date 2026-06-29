.PHONY: setup test run serve clean
PY := ./.venv/bin/python
PIP := ./.venv/bin/pip

setup:
	bash scripts/setup.sh

venv:
	python3 -m venv .venv && $(PIP) install --upgrade pip && $(PIP) install -e ".[dev]"

test:
	./.venv/bin/pytest -q

run:
	./.venv/bin/content-machine $(ARGS)

serve:
	./.venv/bin/content-machine serve

clean:
	rm -rf .venv data __pycache__ */__pycache__ .pytest_cache *.egg-info
