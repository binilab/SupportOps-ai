PYTHON ?= python3

.PHONY: validate-data test

validate-data:
	$(PYTHON) scripts/validate_gold_dataset.py

test:
	$(PYTHON) -m pytest -q
