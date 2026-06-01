.PHONY: install install-python install-ns3 install-mininet install-gazebo verify \
        docs docs-check compat-check test

# ── Install ──────────────────────────────────────────────────────────────────

## install: Run all install steps (Python + NS-3 + Mininet + Gazebo)
install: install-python install-ns3 install-mininet install-gazebo

## install-python: Install cornet-framework Python package (editable)
install-python:
	bash scripts/install/install_python.sh

## install-ns3: Clone, build, and patch NS-3 3.38 + NR v2.4
install-ns3:
	bash scripts/install/install_ns3.sh

## install-mininet: Install Mininet-WiFi + Docker
install-mininet:
	bash scripts/install/install_mininet.sh

## install-gazebo: Install Gazebo Classic 11 + ROS 2 Humble
install-gazebo:
	bash scripts/install/install_gazebo_ros2.sh

## verify: Check all components are correctly installed
verify:
	bash scripts/install/verify.sh

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
