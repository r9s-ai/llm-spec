.PHONY: help pre-commit-install pre-commit pre-commit-all pre-commit-files pre-commit-update

PRE_COMMIT ?= pre-commit

help:
	@echo "Targets:"
	@echo "  pre-commit-install  Install git hooks"
	@echo "  pre-commit          Run hooks on staged files"
	@echo "  pre-commit-all      Run hooks on all files"
	@echo "  pre-commit-files    Run hooks on given files (make pre-commit-files FILES='a.py b.py')"
	@echo "  pre-commit-update   Update hook revisions"

pre-commit-install:
	@$(PRE_COMMIT) install

pre-commit:
	@$(PRE_COMMIT) run

pre-commit-all:
	@$(PRE_COMMIT) run --all-files

pre-commit-files:
	@test -n "$(FILES)" || (echo "FILES is required (e.g. make pre-commit-files FILES='path/to/file.py')" && exit 2)
	@$(PRE_COMMIT) run --files $(FILES)

pre-commit-update:
	@$(PRE_COMMIT) autoupdate
