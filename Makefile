SHELL=/bin/bash


install:
	@[ ! -d .venv ] && python3.9 -m venv .venv ||:;
	@( \
		source .venv/bin/activate || exit 1; \
		pip install -r requirements.txt; \
	)


dev-install:
	@( \
		source .venv/bin/activate || exit 1; \
		pip install -r requirements-dev.txt; \
	)


lint:
	@( \
		black --check . --exclude '.cache|.venv'; \
		isort --check-only .; \
		autoflake --check --recursive --remove-all-unused-imports --remove-unused-variables --exclude '.cache|.venv' .; \
	)


lint-apply:
	@( \
		black . --exclude '.cache|.venv'; \
		isort .; \
		autoflake --in-place --recursive --remove-all-unused-imports --remove-unused-variables --exclude '.cache|.venv' .; \
	)


create-env:
	@[ ! -f .env ] && cp .env.mock .env ||:;


setup: create-env install
