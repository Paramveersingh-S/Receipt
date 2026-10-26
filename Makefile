ifeq ($(OS),Windows_NT)
    PYTHON := .venv/Scripts/python.exe
    export PYTHONPATH := apps/api;.
else
    PYTHON := .venv/bin/python
    export PYTHONPATH := apps/api:.
endif

.PHONY: dev test lint mock bench demo demo-smoke

dev:
	$(PYTHON) -m uvicorn receipt_api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir apps/api

test:
	$(PYTHON) -m pytest tests -v

lint:
	$(PYTHON) -m scripts.lint

mock:
	$(PYTHON) -m uvicorn receipt_api.mock_server:app --reload --host 0.0.0.0 --port 8000 --app-dir apps/api

bench:
	$(PYTHON) -m bench.runner

demo:
	$(PYTHON) -m receipt_api.demo_runner

demo-smoke:
	$(PYTHON) -m scripts.demo_smoke
