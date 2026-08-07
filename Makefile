# Convenience targets wrapping ./forge (Phase 2).
REPO := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
FORGE := $(REPO)forge
PROJECT ?= sandbox/examples/hello-flake
PROFILE ?= trusted

.PHONY: help sandbox-list sandbox-init sandbox-enter sandbox-smoke sandbox-build-image

help:
	@echo "Targets:"
	@echo "  make sandbox-list"
	@echo "  make sandbox-init"
	@echo "  make sandbox-enter PROJECT=... PROFILE=trusted|devcontainer|agent-cell|incus"
	@echo "  make sandbox-smoke"
	@echo "  make sandbox-build-image"

sandbox-list:
	@$(FORGE) sandbox list

sandbox-init:
	@$(FORGE) sandbox init

sandbox-enter:
	@$(FORGE) sandbox enter $(PROJECT) --profile $(PROFILE)

sandbox-smoke:
	@$(FORGE) sandbox smoke

sandbox-build-image:
	@# shellcheck disable=SC1091
	@bash -c 'source "$(REPO)sandbox/lib/common.sh" && forge_ensure_image'
