#!/usr/bin/env python3
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


workflow = load("dr_workflow", "services/orchestrator/app/workflow.py")
crm = load("dr_crm", "services/crm_api/app/domain.py")


def main():
    original = workflow.WorkflowEngine()
    state = original.start("tenant-dr", "campaign-dr", "contact-dr")
    state = original.transition(state, "event-1")
    persisted = original.checkpoints[state.run_id]
    restored_engine = workflow.WorkflowEngine()
    restored = restored_engine.restore(persisted)
    resumed = restored_engine.transition(restored, "event-2")
    if resumed.checkpoint_no != 3: raise SystemExit("CHECKPOINT_RECOVERY_FAILED")

    store = crm.CRMStore()
    contact = store.create_contact("tenant-dr", {"display_name":"DR"})
    store.suppress("tenant-dr", contact["id"])
    audit = store.export_audit("tenant-dr")
    if not store.verify_audit(audit): raise SystemExit("AUDIT_RECOVERY_FAILED")
    print({"checkpoint_restore":"PASS", "audit_chain":"PASS", "rpo_events":0, "replayed_checkpoint":resumed.checkpoint_no})


if __name__ == "__main__": main()
