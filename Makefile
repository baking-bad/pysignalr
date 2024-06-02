.ONESHELL:
.PHONY: $(MAKECMDGOALS)
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
	docker-compose up --build --exit-code-from test_runner test_runner || docker compose down

docs:           ## Generate documentation
	docker-compose run --rm docs sphinx-build -b html docs/source docs/build || docker compose down

##

black:          ## Format with black
	docker-compose run --rm formatter 'pip install black && black src tests example.py' || docker compose down

ruff:           ## Lint with ruff
	docker-compose run --rm linter 'pip install ruff && ruff check --fix --unsafe-fixes src tests example.py' || docker compose down

mypy:           ## Lint with mypy
	docker-compose run --rm linter 'pip install mypy && mypy --strict src tests example.py' || docker compose down

cover:          ## Print coverage for the current branch
	docker-compose run --rm coverage 'pip install diff-cover && diff-cover --compare-branch `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'` coverage.xml' || docker compose down

##

clean:          ## Remove all files from .gitignore except for `.venv`
	sudo git clean -xdf --exclude=".venv"
