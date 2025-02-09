SHELL=/bin/bash


OS := $(shell uname 2>/dev/null || echo Windows)

ifeq ($(OS), Windows_NT)
	CMD_ACTIVATE_VENV = .venv\Scripts\activate
	CMD_CHECK_ENV = if not exist .env copy .env.mock .env
	PYTHON = python
else
	CMD_ACTIVATE_VENV = source .venv/bin/activate
	CMD_CHECK_ENV = [ ! -f .env ] && cp .env.mock .env || :
	PYTHON = python3.9
endif


install:
	@[ ! -d .venv ] && $(PYTHON) -m venv .venv ||:;
	@( \
		$(CMD_ACTIVATE_VENV) || exit 1; \
		pip install -r requirements.txt; \
	)


dev-install:
	@( \
		$(CMD_ACTIVATE_VENV) || exit 1; \
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
	@$(CMD_CHECK_ENV)


setup: create-env install
