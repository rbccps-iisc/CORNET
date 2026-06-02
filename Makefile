.PHONY: install install-python install-ns3 install-ns3-v24 install-ns3-v47 \
        install-mininet install-gazebo verify validate validate-v24 validate-v47 \
        docs docs-check compat-check test

# ── Install ──────────────────────────────────────────────────────────────────

## install: Run all install steps (Python + NS-3 + Mininet + Gazebo)
install: install-python install-ns3 install-mininet install-gazebo

## install-python: Install cornet-framework Python package (editable)
install-python:
	bash scripts/install/install_python.sh

## install-ns3: Clone, build, and patch NS-3 3.38 + NR v2.4 (default, ~/ns-3-dev)
install-ns3:
	bash scripts/install/install_ns3.sh

## install-ns3-v24: Install NS-3 3.38 + NR v2.4 into ~/ns-3-dev-v24
install-ns3-v24:
	NS3_DIR=~/ns-3-dev-v24 PATCH_SET=v2.4-ns3.38 bash scripts/install/install_ns3.sh

## install-ns3-v47: Install NS-3 3.47 + NR v4.2 into ~/ns-3-dev-v47
install-ns3-v47:
	NS3_DIR=~/ns-3-dev-v47 PATCH_SET=v4.2-ns3.47 bash scripts/install/install_ns3.sh

## install-mininet: Install Mininet-WiFi + Docker
install-mininet:
	bash scripts/install/install_mininet.sh

## install-gazebo: Install Gazebo Classic 11 + ROS 2 Humble
install-gazebo:
	bash scripts/install/install_gazebo_ros2.sh

## verify: Check all components are correctly installed
verify:
	bash scripts/install/verify.sh

# ── Dual-version validation ───────────────────────────────────────────────────

# Override these to use non-default NS-3 install directories.
NS3_DIR_V24 ?= $(HOME)/ns-3-dev-v24
NS3_DIR_V47 ?= $(HOME)/ns-3-dev-v47

## validate: Run pendulum_nr_control against both NS-3 versions (v2.4 + v4.2).
##            Skips v4.2 with a warning if ~/ns-3-dev-v47/.cornet-built is absent.
validate: validate-v24
	@if [ -f "$(NS3_DIR_V47)/.cornet-built" ]; then \
	    $(MAKE) validate-v47; \
	else \
	    echo "WARNING: $(NS3_DIR_V47)/.cornet-built not found — v4.2 run skipped."; \
	    echo "         Run 'make install-ns3-v47' to install NS-3 3.47 + NR v4.2."; \
	fi

## validate-v24: Run pendulum_nr_control against NS-3 v2.4, tag entry @ns3-v24
validate-v24:
	NS3_DIR=$(NS3_DIR_V24) CORNET_NS3_TAG=ns3-v24 python -m cornet tasks/pendulum_nr_control

## validate-v47: Run pendulum_nr_control against NS-3 v4.2, tag entry @ns3-v47
validate-v47:
	NS3_DIR=$(NS3_DIR_V47) CORNET_NS3_TAG=ns3-v47 python -m cornet tasks/pendulum_nr_control

# ── Compatibility check ───────────────────────────────────────────────────────

## compat-check: Run NS-3 compatibility pre-flight check (default: v2.4-ns3.38)
compat-check:
	python3 scripts/check_ns3_compat.py --ns3-dir "$${NS3_DIR:-$$HOME/ns-3-dev}" --patch-set "$${PATCH_SET:-v2.4-ns3.38}"

## compat-check-json: Same as compat-check but emit JSON
compat-check-json:
	python3 scripts/check_ns3_compat.py --ns3-dir "$${NS3_DIR:-$$HOME/ns-3-dev}" --patch-set "$${PATCH_SET:-v2.4-ns3.38}" --json

# ── Documentation ─────────────────────────────────────────────────────────────

## docs: Re-generate docs/reference/config-schema.md from schema.py
docs:
	python3 scripts/gen_schema_docs.py

## docs-check: Verify docs/reference/config-schema.md is up to date (CI use)
docs-check:
	python3 scripts/gen_schema_docs.py
	git diff --exit-code docs/reference/config-schema.md || \
	    (echo "ERROR: docs/reference/config-schema.md is out of date. Run 'make docs' and commit." && exit 1)

# ── Tests ─────────────────────────────────────────────────────────────────────

## test: Run the full test suite
test:
	python3 -m pytest tests/ -v

# ── Help ──────────────────────────────────────────────────────────────────────

## help: List available targets
help:
	@grep -E '^## ' Makefile | sed 's/^## /  /'
