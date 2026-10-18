from __future__ import annotations


TRIGGER_PRIORITY: dict[str, int] = {
    "WORK_OFF_SCHEDULE": 100,
    "EQUIPMENT_DEFICIT": 80,
    "EQUIPMENT_IDLE": 60,
    "EQUIPMENT_MISMATCH": 40,
    "EQUIPMENT_SURPLUS": 20,
}


def violation_priority(v: dict) -> int:
    base = TRIGGER_PRIORITY.get(v.get("type", ""), 0)
    return base + (10 if v.get("severity") == "RED" else 0)


def reconcile_violations(old: list[dict], new: list[dict]) -> list[dict]:
    old_by_key = {
        (v.get("type"), v.get("schedule_id")): v for v in old
    }
    result: list[dict] = []
    for nv in new:
        key = (nv.get("type"), nv.get("schedule_id"))
        prev = old_by_key.get(key)
        if prev is None:
            result.append(nv)
            continue

        merged = dict(nv)
        merged["created_at"] = prev.get("created_at", nv.get("created_at"))
        merged["yellow_escalated_at"] = prev.get("yellow_escalated_at")
        if prev.get("severity") == "RED":
            merged["severity"] = "RED"
        result.append(merged)
    return result


def aggregate_summary(violations: list[dict]) -> dict:
    if not violations:
        return {}

    severities = {v.get("severity") for v in violations}
    severity = "RED" if "RED" in severities else "YELLOW"

    main = max(violations, key=violation_priority)

    yellow_escalates = [
        v["escalate_at"]
        for v in violations
        if v.get("severity") == "YELLOW" and v.get("escalate_at")
    ]
    escalate_at = min(yellow_escalates) if yellow_escalates else None

    return {
        "severity": severity,
        "trigger_type": main.get("type"),
        "schedule_id": main.get("schedule_id"),
        "frame_id": main.get("frame_id"),
        "escalate_at": escalate_at,
    }