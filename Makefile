.ONESHELL:
.PHONY: $(MAKECMDGOALS)
SRC = src tests example.py example_with_token.py
##
##    🚧 pysignalr developer tools
##

##

help:           ## Show this help (default)
	@grep -F -h "##" $(MAKEFILE_LIST) | grep -F -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

all:            ## Run a whole CI pipeline: formatters, linters, tests and docs
	make lint test docs

lint:           ## Lint with all tools
	make black ruff mypy

test:           ## Run test suite
	pytest --cov-report=term-missing --cov=pysignalr --cov-report=xml --asyncio-mode=auto -s -v tests

##

black:          ## Format with black
	black $(SRC)

ruff:           ## Lint with ruff
	ruff check --fix --unsafe-fixes $(SRC)

mypy:           ## Lint with mypy
	mypy --strict $(SRC)

cover:          ## Print coverage for the current branch
	diff-cover --compare-branch origin/master coverage.xml

##

clean:          ## Remove all files from .gitignore except for `.venv`
	git clean -xdf --exclude=".venv"
