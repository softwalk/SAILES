.PHONY: test demo compliance preflight

test:
	python3 -m unittest discover -s tests -v

demo:
	python3 tools/demo.py
	python3 tools/shadow_e2e.py

compliance:
	python3 tools/compliance_gate.py --mode source

preflight:
	deploy/proxmox/operations/00_preflight.sh

.PHONY: all
all:
	bash ci/run_all.sh
