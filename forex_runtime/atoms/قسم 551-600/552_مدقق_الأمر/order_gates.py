from __future__ import annotations

from typing import Any

from shared.financial_scope import text

from order_validation import _neutral_pair_contract

# Campaign 450-901 batch B: the OPEN-path gates (parent authority, margin
# verdict, snapshot validity) extracted verbatim -- same behavior, smaller atom.

AUTHORITY_FIELDS = ("decision_id", "parent_decision_id", "owner_command_id")


STAGE_PARENT = "PARENT_DECISION"
STAGE_MARGIN = "MARGIN_VERDICT"
STAGE_SNAPSHOT = "SNAPSHOT_VALIDITY"
SNAPSHOT_USABLE_STATUS = "READY"


async def run_open_gates(atom, body: dict[str, Any],
                         authority_fields: tuple = AUTHORITY_FIELDS) -> str:
    """Empty string = all OPEN gates passed; else the refusal reason."""
    if not _neutral_pair_contract(body) \
            and not any(text(body.get(field)) for field in authority_fields):
        atom._parent_decision_blocked += 1
        await atom._refuse(body, "PARENT_DECISION_MISSING", STAGE_PARENT,
                           measured_at=__import__("time").time())
        return "PARENT_DECISION_MISSING"
    verdict = atom._margin_verdicts.get(
        (body.get("account_id"), text(body.get("request_id"))))
    if verdict is None:
        atom._margin_verdict_blocked += 1
        await atom._refuse(body, "MARGIN_VERDICT_MISSING", STAGE_MARGIN,
                           measured_at=__import__("time").time())
        return "MARGIN_VERDICT_MISSING"
    if not verdict.get("approved"):
        atom._margin_verdict_blocked += 1
        await atom._refuse(body, "MARGIN_VERDICT_REJECTED", STAGE_MARGIN,
                           value=verdict.get("required_margin"),
                           threshold=verdict.get("free_margin"),
                           measured_at=verdict.get("measured_at"))
        return "MARGIN_VERDICT_REJECTED"
    snapshot_id = text(body.get("snapshot_id"))
    if snapshot_id:
        record = atom._snapshots.get(snapshot_id)
        if record is None:
            atom._snapshot_validity_blocked += 1
            await atom._refuse(body, "SNAPSHOT_UNKNOWN", STAGE_SNAPSHOT,
                           measured_at=__import__("time").time())
            return "SNAPSHOT_UNKNOWN"
        if not record.get("usable_for_new_exposure"):
            atom._snapshot_validity_blocked += 1
            await atom._refuse(body, "SNAPSHOT_NOT_USABLE", STAGE_SNAPSHOT,
                               value=record.get("snapshot_status"),
                               threshold=SNAPSHOT_USABLE_STATUS,
                               measured_at=record.get("measured_at"))
            return "SNAPSHOT_NOT_USABLE"
    return ""
