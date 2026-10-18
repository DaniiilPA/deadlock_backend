"""one_open_alert_per_project

Revision ID: a1b2c3d4e5f6
Revises: 10e159511290
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "10e159511290"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE alerts SET status='RESOLVED', resolved_at=NOW() WHERE status='OPEN'"
    )

    op.drop_index("uq_open_alert_per_stage_trigger", table_name="alerts")

    op.create_index(
        "uq_open_alert_per_project",
        "alerts",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )


def downgrade() -> None:
    op.drop_index("uq_open_alert_per_project", table_name="alerts")

    op.create_index(
        "uq_open_alert_per_stage_trigger",
        "alerts",
        [
            "project_id",
            sa.literal_column(
                "COALESCE(schedule_id, '00000000-0000-0000-0000-000000000000'::uuid)"
            ),
            "trigger_type",
        ],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )
