.PHONY: test format lint

test:
	npm run test || pytest

format:
	black backend/ || true
	npx prettier --write .

lint:
	npx eslint . || true

