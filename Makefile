ADDON_DIR := $(HOME)/Library/Application Support/Anki2/addons21
MODULE := speedup
SRC := $(CURDIR)/src/$(MODULE)
LINK := $(ADDON_DIR)/$(MODULE)

.PHONY: link unlink build test lint format clean

link:
	@mkdir -p "$(ADDON_DIR)"
	@rm -rf "$(LINK)"
	@ln -s "$(SRC)" "$(LINK)"
	@echo "Linked $(LINK) -> $(SRC)"

unlink:
	@rm -f "$(LINK)"
	@echo "Removed $(LINK)"

build:
	@python3 scripts/build.py

test:
	@python3 -m pytest

lint:
	@python3 -m ruff check src tests scripts
	@python3 -m mypy src/speedup || true

format:
	@python3 -m ruff format src tests scripts

clean:
	@rm -rf dist
	@find . -name __pycache__ -type d -prune -exec rm -rf {} +
