PROJECT ?= your-gcp-project-id
BUCKET  ?= $(PROJECT)-lakehouse-bronze
START   ?= 2025-01-01
END     ?= 2025-01-31

.PHONY: install fmt lint test tf-validate ingest-dry ingest local-metrics benchmark

install:
	pip install -r ingestion/requirements-dev.txt -r sql/benchmarks/requirements.txt

fmt:
	terraform -chdir=terraform fmt -recursive
	cd ingestion && ruff check --fix .

lint:
	terraform -chdir=terraform fmt -check -recursive
	cd ingestion && ruff check .

test:
	cd ingestion && pytest -q

tf-validate:
	terraform -chdir=terraform init -backend=false
	terraform -chdir=terraform validate

ingest-dry:
	cd ingestion/src && python -m bcra_ingest.cli --start $(START) --end $(END) --dry-run --out-dir ../../data

ingest:
	cd ingestion/src && python -m bcra_ingest.cli --start $(START) --end $(END) --bucket $(BUCKET) --out-dir ../../data

local-metrics:
	python sql/benchmarks/local_metrics.py

benchmark:
	python sql/benchmarks/benchmark.py --project $(PROJECT) --dataset gold
