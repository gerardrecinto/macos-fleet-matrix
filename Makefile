.PHONY: test lint swift-test

test:
	python -m pytest

lint:
	ruff check .

swift-test:
	swift test
