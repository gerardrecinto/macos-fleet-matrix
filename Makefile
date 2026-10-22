.PHONY: test lint swift-test rust-test terraform-validate terragrunt-validate k8s-validate k8s-policy-test trivy-config

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
	for platform in ack openshift; do \
		(cd terraform/kubernetes/modules/$$platform && terraform init -backend=false -input=false && terraform validate) || exit 1; \
	done

terragrunt-validate:
	cd terraform/control-plane && terragrunt hcl format --check
	for provider in aws gcp azure openstack alicloud; do \
		(cd terraform/control-plane/live/$$provider && terragrunt validate) || exit 1; \
	done
	cd terraform/kubernetes && terragrunt hcl format --check
	for platform in ack openshift; do \
		(cd terraform/kubernetes/live/$$platform && terragrunt validate) || exit 1; \
	done

k8s-validate:
	kubectl kustomize deploy/k8s/control-plane | kubeconform -strict -summary
	kubeconform -strict -summary \
		-schema-location default \
		-schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
		deploy/argocd/application.yaml
	kubectl kustomize deploy/k8s/overlays/openshift | kubeconform -strict -summary
	kubectl kustomize deploy/k8s/policies | kubeconform -strict -summary \
		-schema-location default \
		-schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'

k8s-policy-test:
	for target in deploy/k8s/control-plane deploy/k8s/overlays/openshift; do \
		kubectl kustomize $$target > /tmp/mfm-rendered.yaml; \
		kyverno apply deploy/k8s/policies/disallow-latest-tag.yaml deploy/k8s/policies/require-pod-security.yaml deploy/k8s/policies/require-resource-limits.yaml --resource /tmp/mfm-rendered.yaml || exit 1; \
	done

trivy-config:
	for path in terraform/kubernetes deploy/k8s .harness; do \
		trivy config --severity HIGH,CRITICAL --exit-code 1 $$path || exit 1; \
	done
