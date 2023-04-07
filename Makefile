.ONESHELL:
.PHONY: $(MAKECMDGOALS)
##
##    🚧 pysignalr developer tools
##
## DEV=1                Install dev dependencies
DEV=1

##

help:           ## Show this help (default)
	@grep -F -h "##" $(MAKEFILE_LIST) | grep -F -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

all:            ## Run a whole CI pipeline: formatters, linters and tests
	make install lint test docs

install:        ## Install project dependencies
	poetry install \
	`if [ "${DEV}" = "0" ]; then echo "--without dev"; fi`

lint:           ## Lint with all tools
	make isort black ruff mypy

test:           ## Run test suite
	poetry run pytest --cov-report=term-missing --cov=pysignalr --cov-report=xml -s -v tests

##

isort:          ## Format with isort
	poetry run isort src tests example.py

black:          ## Format with black
	poetry run black src tests example.py

ruff:           ## Lint with ruff
	poetry run ruff check src tests example.py

mypy:           ## Lint with mypy
	poetry run mypy --strict src tests example.py

cover:          ## Print coverage for the current branch
	poetry run diff-cover --compare-branch `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'` coverage.xml

build:          ## Build Python wheel package
	poetry build

##

clean:          ## Remove all files from .gitignore except for `.venv`
	git clean -xdf --exclude=".venv"
	rm -r ~/.cache/flakeheaven

update:         ## Update dependencies, export requirements.txt
	rm requirements.* poetry.lock
	make install
	poetry export --without-hashes -o requirements.txt

