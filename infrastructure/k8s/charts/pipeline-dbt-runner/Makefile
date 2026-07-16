# =============================================================================
# Makefile — pipeline-dbt-runner image
# =============================================================================
# Configurable variables (override on the command line):
#   REGISTRY   — image registry prefix (default: my-registry)
#   IMAGE      — image name            (default: pipeline-dbt-runner)
#   DBT_VER    — dbt-core/bigquery version  (default: 1.7.14)
#   LIB_VER    — culvert version            (default: 0.1.1)
#   TAG        — full image tag        (default: $(DBT_VER)-$(LIB_VER))
#
# Examples:
#   make build
#   make build REGISTRY=gcr.io/my-project
#   make push  REGISTRY=gcr.io/my-project
#   make run-local
# =============================================================================

REGISTRY  ?= my-registry
IMAGE     ?= pipeline-dbt-runner
DBT_VER   ?= 1.7.14
LIB_VER   ?= 0.1.1
TAG       ?= $(DBT_VER)-$(LIB_VER)

FULL_IMAGE := $(REGISTRY)/$(IMAGE):$(TAG)

# Optional: override PyPI index for culvert[transform] (private registry)
PIP_INDEX_URL ?= https://pypi.org/simple/

# Local smoke-test settings
LOCAL_PROJECT_DIR  ?= $(shell pwd)/local-dbt-projects
LOCAL_PROFILES_DIR ?= $(shell pwd)/local-profiles
FAKE_CREDENTIALS   ?= $(HOME)/.config/gcloud/application_default_credentials.json

.PHONY: build push run-local version help

## build: Build the Docker image locally
build:
	@echo "==> Building $(FULL_IMAGE)"
	docker build \
		--build-arg DBT_VERSION=$(DBT_VER) \
		--build-arg PIPELINE_LIB_VERSION=$(LIB_VER) \
		--build-arg PIP_INDEX_URL=$(PIP_INDEX_URL) \
		--tag $(FULL_IMAGE) \
		--file Dockerfile \
		.
	@echo "==> Built $(FULL_IMAGE)"

## push: Push the image to the registry (run 'make build' first)
push:
	@echo "==> Pushing $(FULL_IMAGE)"
	docker push $(FULL_IMAGE)
	@echo "==> Pushed $(FULL_IMAGE)"

## run-local: Run the image locally for a smoke test
##   Requires:
##     - A dbt project at LOCAL_PROJECT_DIR/<dbt-project-name>
##     - A profiles.yml at LOCAL_PROFILES_DIR/profiles.yml
##     - ADC at FAKE_CREDENTIALS (gcloud auth application-default login)
run-local:
	@echo "==> Running $(FULL_IMAGE) locally"
	@if [ ! -f "$(FAKE_CREDENTIALS)" ]; then \
		echo "WARNING: $(FAKE_CREDENTIALS) not found."; \
		echo "Run: gcloud auth application-default login"; \
	fi
	docker run --rm \
		--env DBT_PROJECT=bigquery-to-mapped-product \
		--env DBT_TARGET=dev \
		--env DBT_PROFILES_DIR=/app/profiles \
		--env GOOGLE_APPLICATION_CREDENTIALS=/app/creds/adc.json \
		--volume "$(LOCAL_PROJECT_DIR):/app/projects" \
		--volume "$(LOCAL_PROFILES_DIR):/app/profiles" \
		--volume "$(FAKE_CREDENTIALS):/app/creds/adc.json:ro" \
		$(FULL_IMAGE) \
		debug

## version: Print the version that would be baked into the image
version:
	@echo "Image     : $(FULL_IMAGE)"
	@echo "dbt       : $(DBT_VER)"
	@echo "lib       : $(LIB_VER)"
	@echo "Registry  : $(REGISTRY)"
	@echo "Tag       : $(TAG)"

## help: Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/^## /  /'
