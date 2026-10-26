"""Schema v3: database/00..13 (ALL_IN_ONE.sql + 12_gap_remediation + 13_gap_seed_views_security).

Those scripts build the database; this revision only marks it. On a database built from them run
`alembic stamp v3_baseline` once, then `alembic upgrade head`.

Revision ID: v3_baseline
Revises:
Created: 2026-10-26
"""

revision = "v3_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise RuntimeError("The v3 baseline cannot be downgraded; restore from backup instead.")
