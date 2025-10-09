# Repository Guidelines

## Project Structure & Module Organization

The monorepo splits runtime code by platform. `backend/` hosts the FastAPI service; application modules live under `backend/app/` and migrations in `backend/alembic/`. Automated API probes and fixtures sit in `backend/tests/` (unit, integration, e2e). The Flutter client lives in `frontend/gomuseum_app/` with production code in `lib/`, widget tests in `test/`, and golden/integration flows in `integration_test/`. Shared operations scripts (`scripts/`), container assets (`docker/` plus per-service Dockerfiles), deployment manifests (`deployment/`), and higher-level design docs (`docs/`) round out the repo. Use `Pictures-for-test/` when you need sample assets.

## Build, Test, and Development Commands

Use the root Makefile for quick loops: `make test` (runs `npm run test` then falls back to `pytest`), `make lint`, and `make format`. Backend development happens inside `backend/`; install deps with `pip install -r requirements.txt` or the Poetry extras, then run `pytest` or `pytest --maxfail=1 --disable-warnings`. Start the API locally with `uvicorn app.main:app --reload`. For Flutter work, run `cd frontend/gomuseum_app && flutter pub get`, `flutter analyze`, and `flutter test`. Docker builds live under `docker/` if you need container images.

## Coding Style & Naming Conventions

Python code follows Black (88 columns), isort (Black profile), flake8, and strict mypy; keep modules snake_case, classes UpperCamelCase, and constants UPPER_SNAKE. JavaScript/TypeScript and Markdown go through ESLint and Prettier; keep camelCase for variables and kebab-case for utility scripts. Flutter uses the included `analysis_options.yaml`: prefer single quotes, package imports, const constructors, and explicit types. Run `npm run lint` or `npx eslint .` plus `npx prettier --check .` before pushing.

## Testing Guidelines

Place Python tests beside the feature in `backend/tests/<layer>/` and name files `test_*.py`. Coverage must stay ≥80% (enforced via pytest `--cov-fail-under=80`). Prefer async fixtures for I/O and mock external APIs with `fakeredis` or `httpx`'s test client. Flutter widget tests live under `frontend/gomuseum_app/test/`; integration suites run from `integration_test/` using `flutter drive --driver integration_test/driver.dart`. Capture new media in `Pictures-for-test/` to keep assets deterministic.

## Commit & Pull Request Guidelines

Follow the existing conventional style: `feat:`, `fix(scope):`, `chore:` etc., with imperative subject lines and short descriptions. Squash unrelated changes, reference issue IDs in the body, and include context links to docs when relevant. Before opening a PR, run `make lint` and the relevant test suites, attach screenshots or curl snippets for user-facing changes, and call out config updates or new secrets (see `API_KEYS_SETUP_GUIDE.md`). Request review from the backend or Flutter owners depending on the surface area.
