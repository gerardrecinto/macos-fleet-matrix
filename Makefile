.PHONY: test lint swift-test rust-test terraform-validate

test:
	python -m pytest

lint:
	ruff check .

swift-test:
	swift test

rust-test:
	cd src/mfm/Reaper && cargo fmt -- --check && cargo clippy --all-targets -- -D warnings && cargo test

terraform-validate:
	for provider in aws gcp azure openstack alicloud; do \
		(cd terraform/control-plane/$$provider && terraform init -backend=false -input=false && terraform validate) || exit 1; \
	done
