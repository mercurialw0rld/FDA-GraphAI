import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from pydantic import BaseModel, Field
NodeFn = Callable[[Mapping[str, Any]], dict[str, Any]]


class AuditEntry(BaseModel):
    timestamp: str
    node: str
    drug_name: str
    data_hash: str
    status: str
    updates_keys: list[str] = Field(default_factory=list)
    error: str | None = None


audit_log: list[AuditEntry] = []


def _build_snapshot(state: Mapping[str, Any], updates: Mapping[str, Any], error: str | None) -> str:
    """Builds a deterministic payload used for tamper-evident hashing."""
    snapshot = {
        "drug": str(state.get("drug_name", "unknown")),
        "has_fda_data": state.get("raw_fda_data") is not None,
        "update_keys": sorted([str(k) for k in updates.keys()]),
        "error": error,
    }
    return json.dumps(snapshot, sort_keys=True, ensure_ascii=True)


def create_audit_node(node_name: str, node_fn: NodeFn) -> NodeFn:
    """Wraps a node to automatically log execution and preserve behavior."""

    def audit_wrapper(state: Mapping[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        error_message: str | None = None
        status = "executed"

        try:
            node_result = node_fn(state)
            if not isinstance(node_result, dict):
                raise TypeError(f"Node '{node_name}' debe devolver dict, obtuvo {type(node_result).__name__}")
            updates = node_result
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
            snapshot = _build_snapshot(state, updates, error_message)
            audit_log.append(
                AuditEntry(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    node=node_name,
                    drug_name=str(state.get("drug_name", "unknown")),
                    data_hash=hashlib.sha256(snapshot.encode()).hexdigest()[:12],
                    status=status,
                    updates_keys=sorted([str(k) for k in updates.keys()]),
                    error=error_message,
                )
            )
            raise

        snapshot = _build_snapshot(state, updates, error_message)
        audit_log.append(
            AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                node=node_name,
                drug_name=str(state.get("drug_name", "unknown")),
                data_hash=hashlib.sha256(snapshot.encode()).hexdigest()[:12],
                status=status,
                updates_keys=sorted([str(k) for k in updates.keys()]),
                error=error_message,
            )
        )
        return updates

    return audit_wrapper


def export_audit_report(drug_name: str, output_dir: str | Path | None = None) -> Path:
    """Exports the in-memory audit trail and returns the output file path."""
    reports_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parents[1] / "audit_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_path = reports_dir / f"audit_{drug_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump([e.model_dump() for e in audit_log], f, indent=2, ensure_ascii=False)
    return report_path


def clear_audit_log() -> None:
    audit_log.clear()