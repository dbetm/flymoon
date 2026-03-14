SHELL=/bin/bash


CMD_ACTIVATE_VENV = source .venv/bin/activate
CMD_CHECK_ENV = [ ! -f .env ] && cp .env.mock .env || :
PYTHON = python3.9


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


run:
	@( \
		$(CMD_ACTIVATE_VENV) || exit 1; \
		python3 app.py; \
	)



setup: create-env install
