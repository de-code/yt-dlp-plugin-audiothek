#!/usr/bin/make -f

VENV = venv
PIP = $(VENV)/bin/pip
PYTHON = $(VENV)/bin/python


venv-clean:
	@if [ -d "$(VENV)" ]; then \
		rm -rf "$(VENV)"; \
	fi

venv-create:
	python3 -m venv $(VENV)

dev-install:
	$(PIP) install --disable-pip-version-check -r requirements.build.txt
	$(PIP) install --disable-pip-version-check \
		-r requirements.txt \
		-r requirements.dev.txt

dev-venv: venv-create dev-install


dev-flake8:
	$(PYTHON) -m flake8 yt_dlp_plugins

dev-pylint:
	$(PYTHON) -m pylint yt_dlp_plugins

dev-mypy:
	$(PYTHON) -m mypy \
		--check-untyped-defs \
		--follow-untyped-imports \
		yt_dlp_plugins

dev-lint: dev-flake8 dev-pylint dev-mypy

dev-unittest:
	$(PYTHON) -m pytest -p no:cacheprovider $(ARGS) tests

dev-test: dev-lint dev-unittest

dev-watch:
	$(PYTHON) -m pytest_watcher \
		--runner=$(VENV)/bin/python \
		. \
		-m pytest -vv $(PYTEST_WATCH_MODULES)


create-plugin-link:
	mkdir -p ~/.config/yt-dlp/plugins
	ln -s "$(PWD)" ~/.config/yt-dlp/plugins/audiothek
