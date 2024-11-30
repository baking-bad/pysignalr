.PHONY: $(MAKECMDGOALS)
MAKEFLAGS += --no-print-directory
##
##    🚧 pysignalr developer tools
##
SOURCE = src tests example.py example_with_token.py

help:           ## Show this help (default)
	@grep -F -h "##" $(MAKEFILE_LIST) | grep -F -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

install:        ## Install dependencies
	poetry sync

update:         ## Update dependencies
	poetry update

all:            ## Run a whole CI pipeline: formatters, linters, tests
	make lint test

lint:           ## Lint with all tools
	make black ruff mypy

test:           ## Run test suite
	pytest --cov-report=term-missing --cov=pysignalr --cov-report=xml --asyncio-mode=auto -s -v tests

##

black:          ## Format with black
	black $(SOURCE)

ruff:           ## Lint with ruff
	ruff check --fix --unsafe-fixes $(SOURCE)

mypy:           ## Lint with mypy
	mypy --strict $(SOURCE)

cover:          ## Print coverage for the current branch
	diff-cover --compare-branch origin/master coverage.xml

##

clean:          ## Remove all files from .gitignore except for `.venv`
	git clean -xdf --exclude=".venv"
