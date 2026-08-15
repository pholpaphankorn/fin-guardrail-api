# Repository Guidelines

## Project Structure & Module Organization

Application code lives in `app/`. `app/main.py` defines FastAPI routes and runtime health, `app/schemas.py` contains Pydantic contracts, and `app/services/` separates vision extraction, image processing, deterministic validation, policy retrieval, and bounded workflow orchestration. Synthetic policies are in `data/policies/`; sample documents and mock responses are elsewhere under `data/`. Keep fast tests in `tests/unit/`, explicitly authorized live flows in `tests/e2e/`, and extraction benchmarks plus ground truth in `tests/evals/`. `scripts/run_eval.py` emits the offline routing, retrieval, grounding, and workflow regression report.

The request pipeline is: image upload -> quality checks -> Ollama vision extraction -> Python validation rules -> risk status. Keep high-stakes decisions in deterministic validators rather than model prompts.

## Build, Test, and Development Commands

Create an isolated environment and install pinned dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Use `python -m uvicorn app.main:app --reload` to run the API locally. Run `python -m pytest tests/unit` for the fast mocked suite, `python scripts/run_eval.py` for deterministic regression cases, and `RUN_LIVE_E2E=true python -m pytest -m e2e` only when live Ollama access and model calls are intended. Run `black --check app tests scripts` before review; use `black app tests scripts` to apply formatting.

## Coding Style & Naming Conventions

Target modern Python with four-space indentation, type hints, and short docstrings for public functions. Black is the source of formatting truth. Use `snake_case` for modules, functions, and variables; `PascalCase` for Pydantic models and other classes; and `UPPER_SNAKE_CASE` for constants. Keep endpoint orchestration thin and place reusable logic in `app/services/`.

## Testing Guidelines

Pytest and `pytest-asyncio` are configured in `pyproject.toml`. Name files `test_<area>.py` and tests `test_<behavior>`. Mark fast isolated tests with `@pytest.mark.unit` and live flows with `@pytest.mark.e2e`. Add regression coverage for validation boundaries, malformed model output, and image-quality edge cases. No coverage threshold is configured; changed behavior should have focused tests.

## Commit & Pull Request Guidelines

Follow the existing lowercase prefix style: `change:`, `test:`, `chore:`, or `style:` followed by a concise imperative summary. Keep commits focused. Pull requests should explain the risk or behavior changed, list verification commands, link relevant issues, and include sample request/response output when API contracts change.

## Security & Configuration

Store `OLLAMA_API_KEY` in `.env`; never commit credentials or real identity/medical documents. Set `USE_MOCK_LLM=true` for local deterministic work. Treat `tests/evals/output/` as generated diagnostic data and review it for sensitive content before sharing.
