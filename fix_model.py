from pathlib import Path

path = Path("app/db/models/incidents.py")
src = path.read_text(encoding="utf-8")

old = '''    __table_args__ = (
        Index(
            "uq_open_alert_per_stage_trigger",
            "project_id",
            # Защита от NULL != NULL в PostgreSQL:
            text("COALESCE(schedule_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "trigger_type",
            unique=True,
            postgresql_where=(text("status = 'OPEN'")),
        ),
    )'''

new = '''    __table_args__ = (
        Index(
            "uq_open_alert_per_project",
            "project_id",
            unique=True,
            postgresql_where=(text("status = 'OPEN'")),
        ),
    )'''

if new in src:
    print("OK: model already updated")
elif old not in src:
    print("FAIL: old block not found. Check incidents.py manually.")
else:
    path.write_text(src.replace(old, new), encoding="utf-8")
    print("OK: incidents.py updated")
