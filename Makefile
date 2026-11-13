# Checks for herdr-switchboard.
#
# There is nothing to build: the plugin is one Python script that uses only the
# standard library. These targets test and lint it, and CI runs the same targets
# (.github/workflows/ci.yml), so a green `make check` here predicts a green CI.
#
# Works with the GNU make 3.81 that macOS ships.

PYTHON ?= python3

PROGRAM := bin/switchboard
TESTS := tests/test_switchboard.py
SOURCES := $(wildcard $(PROGRAM) tests/*.py)
SCRIPTS := $(wildcard .github/scripts/*.sh)

# ruff, pinned. It runs through uvx when uv is installed, so nothing has to be
# installed into the project; otherwise a ruff found on PATH is used.
RUFF_VERSION ?= 0.17.3
# E9     syntax errors, including syntax newer than Python 3.9 (--target-version py39)
# F      pyflakes: undefined names, unused imports and variables
# FA102  an `X | Y` annotation, which Python 3.9 evaluates and rejects at import
#        time. Write Optional[X] or Union[X, Y]: the project avoids `from __future__`.
RUFF_RULES := E9,F,FA102
ifneq ($(shell command -v uvx 2>/dev/null),)
RUFF := uvx --quiet ruff@$(RUFF_VERSION)
else
RUFF := $(shell command -v ruff 2>/dev/null)
endif

# Set REQUIRE_TOOLS=1 (CI does) to fail, instead of skipping, when ruff or
# gitleaks is not installed.
REQUIRE_TOOLS ?=

# Neither the tests nor the linters may leave bytecode in the tree.
export PYTHONDONTWRITEBYTECODE := 1

# The __pycache__ directories of the tree, as `make lint` checks them and
# `make clean` removes them: the same scope for both, .git and a local .venv aside.
FIND_PYCACHE := find . -path ./.git -prune -o -path ./.venv -prune -o -name __pycache__ -type d

.DEFAULT_GOAL := help
.PHONY: help check test lint compile ruff scripts pycache secrets clean

help:
	@echo "make test     run the test suite ($(PYTHON) $(TESTS))"
	@echo "make lint     byte-compile, ruff, shell syntax, no bytecode left behind"
	@echo "make secrets  scan the whole git history with gitleaks"
	@echo "make check    all of the above: what CI runs"
	@echo "make clean    remove caches"
	@echo ""
	@echo "PYTHON=python3.9 make test   runs the tests with another interpreter"

check: test lint secrets

# Guard: bin/switchboard and tests/test_switchboard.py arrive with the port pull
# request. Until then, and only while NEITHER file exists, the tests are skipped.
# A program without its test file is a failure, not a skip. Once the port has
# landed on main, remove the skip branch so a missing test file always fails
# (and remove the matching `if: hashFiles(...)` guards in .github/workflows/ci.yml).
test:
	@if [ -f $(TESTS) ]; then \
	  $(PYTHON) $(TESTS); \
	elif [ -f $(PROGRAM) ]; then \
	  echo "test: $(PROGRAM) exists but $(TESTS) does not: the program has no tests to run" >&2; \
	  exit 1; \
	else \
	  echo "test: SKIPPED, neither $(PROGRAM) nor $(TESTS) exists yet (remove this guard once the port has landed)"; \
	fi

lint: compile ruff scripts pycache

# Compile in memory with the selected interpreter. Unlike py_compile, this writes
# no .pyc anywhere, and it rejects syntax that interpreter does not know.
compile:
	@if [ -z "$(SOURCES)" ]; then \
	  echo "compile: nothing to compile yet"; \
	else \
	  $(PYTHON) -c 'import sys; [compile(open(p, "rb").read(), p, "exec", dont_inherit=True) for p in sys.argv[1:]]' $(SOURCES) \
	  && echo "compile: ok with $$($(PYTHON) -c 'import platform; print(platform.python_version())') ($(SOURCES))"; \
	fi

ruff:
	@if [ -n "$(RUFF)" ]; then \
	  echo "ruff: $$($(RUFF) --version)"; \
	  if [ -z "$(SOURCES)" ]; then \
	    echo "ruff: nothing to lint yet"; \
	  else \
	    $(RUFF) check --no-cache --isolated --target-version py39 --select $(RUFF_RULES) $(SOURCES); \
	  fi; \
	elif [ -n "$(REQUIRE_TOOLS)" ]; then \
	  echo "ruff: not installed; install uv (https://docs.astral.sh/uv/) or ruff" >&2; exit 1; \
	else \
	  echo "ruff: SKIPPED, neither uvx nor ruff is installed"; \
	fi

scripts:
	@for s in $(SCRIPTS); do bash -n "$$s" || exit 1; done; \
	echo "scripts: shell syntax ok ($(SCRIPTS))"

pycache:
	@found=$$($(FIND_PYCACHE) -print); \
	if [ -n "$$found" ]; then \
	  echo "pycache: bytecode left in the tree:" >&2; echo "$$found" >&2; \
	  echo "pycache: run 'make clean'; tests must not write bytecode (PYTHONDONTWRITEBYTECODE=1)" >&2; \
	  exit 1; \
	fi; \
	echo "pycache: none in the tree"

# The same scan CI runs. Inline `gitleaks:allow` comments are ignored on purpose:
# a real false positive gets a narrow allowlist entry in .gitleaks.toml, where it
# is reviewed, not a comment next to the string.
secrets:
	@if command -v gitleaks >/dev/null 2>&1; then \
	  gitleaks git --config .gitleaks.toml --ignore-gitleaks-allow --redact --no-banner --verbose . ; \
	elif [ -n "$(REQUIRE_TOOLS)" ]; then \
	  echo "secrets: gitleaks is not installed" >&2; exit 1; \
	else \
	  echo "secrets: SKIPPED, gitleaks is not installed (https://github.com/gitleaks/gitleaks)"; \
	fi

clean:
	@$(FIND_PYCACHE) -prune -exec rm -rf {} +
	@rm -rf .ruff_cache
