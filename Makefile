.PHONY: test lint swift-test rust-test terraform-validate terragrunt-validate k8s-validate

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
		(cd terraform/control-plane/modules/$$provider && terraform init -backend=false -input=false && terraform validate) || exit 1; \
	done

terragrunt-validate:
	cd terraform/control-plane && terragrunt hcl format --check
	for provider in aws gcp azure openstack alicloud; do \
		(cd terraform/control-plane/live/$$provider && terragrunt validate) || exit 1; \
	done

k8s-validate:
	kubectl kustomize deploy/k8s/control-plane | kubeconform -strict -summary
	kubeconform -strict -summary \
		-schema-location default \
		-schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
		deploy/argocd/application.yaml
