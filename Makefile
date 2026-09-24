.PHONY: $(MAKECMDGOALS)
MAKEFLAGS += --no-print-directory
##
##    🚧 pysignalr developer tools
##
SOURCE = src tests example.py example_with_token.py
WEBSOCKETS ?= >=15.0.1,<18
COVERAGE ?= 0
COVERAGE_FLAGS = --cov-report=term-missing --cov=pysignalr --cov-report=xml

help:           ## Show this help (default)
	@grep -F -h "##" $(MAKEFILE_LIST) | grep -F -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

install:        ## Install dependencies from the lockfile
	uv sync --locked

build:          ## Build package distributions
	uv build

publish:        ## Publish built distributions to PyPI
	uv publish

update:         ## Update dependencies
	uv sync -U

all:            ## Run a whole CI pipeline: formatters, linters, tests
	make format lint test

format:
	ruff format $(SOURCE)

lint:           ## Lint with all tools
	make ruff mypy

check:          ## Check lint, formatting, and types without modifying files
	ruff check $(SOURCE)
	ruff format --check $(SOURCE)
	$(MAKE) mypy

test-unit:      ## Run unit tests without Docker
	pytest --asyncio-mode=auto -q --ignore=tests/test_pysignalr/test_pysignalr.py tests

test:           ## Run test suite
	pytest $(COVERAGE_FLAGS) --asyncio-mode=auto -s -v tests

test-websockets: ## Run tests with WEBSOCKETS constraint (COVERAGE=1 enables coverage)
	uv run --locked --with 'websockets$(WEBSOCKETS)' pytest $(if $(filter 1,$(COVERAGE)),$(COVERAGE_FLAGS)) --asyncio-mode=auto -q tests

##

ruff:           ## Lint and format with ruff
	ruff check --fix --unsafe-fixes $(SOURCE)

mypy:           ## Lint with mypy
	mypy --strict $(SOURCE)

cover:          ## Print coverage for the current branch
	diff-cover --compare-branch origin/master coverage.xml

##

clean:          ## Remove all files from .gitignore except for `.venv`
	git clean -xdf --exclude=".venv"
