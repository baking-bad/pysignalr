.ONESHELL:
.PHONY: $(MAKECMDGOALS)
##
##    🚧 pysignalr developer tools
##

##

help:           ## Show this help (default)
	@grep -F -h "##" $(MAKEFILE_LIST) | grep -F -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

all:            ## Run a whole CI pipeline: formatters, linters and tests
	make lint test docs

lint:           ## Lint with all tools
	make black ruff mypy

test:           ## Run test suite
	PYTHONPATH=src poetry run pytest --cov-report=term-missing --cov=pysignalr --cov-report=xml -s -v tests

##

black:          ## Format with black
	black src tests example.py

ruff:           ## Lint with ruff
	ruff check --fix --unsafe-fixes src tests example.py

mypy:           ## Lint with mypy
	mypy --strict src tests example.py

cover:          ## Print coverage for the current branch
	diff-cover --compare-branch `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'` coverage.xml

##

clean:          ## Remove all files from .gitignore except for `.venv`
	git clean -xdf --exclude=".venv"
