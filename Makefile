SHELL=/bin/bash


install:
	@[ ! -d .venv ] && python3.9 -m venv .venv ||:;
	@( \
		source .venv/bin/activate; \
		pip install -r requirements.txt; \
	)


create-env:
	@[ ! -f .env ] && cp .env.mock .env ||:;


setup: create-env install
