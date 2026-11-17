"""One ASC visit per day, however many of the ASC's calls were worked on that day. Data only.

0040 counted a visit per call per day. For each ASC day, the first call (lowest svc.contract_visit_day id)
keeps the visit; every other call of that ASC on the same day gives its visit back: one less on the call's
svc.contract_visit total (the row goes when it reaches 0) and on the contract's visits_used. The day rows
stay, as history.

Revision ID: 0041_asc_one_visit_per_day
Revises: 0040_asc_visit_days
Created: 2026-11-17
"""

from alembic import op

revision = "0041_asc_one_visit_per_day"
down_revision = "0040_asc_visit_days"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        SELECT d.[service_contract_id], d.[service_call_id], COUNT(*) AS [extra]
        INTO #asc_same_day
        FROM (
            SELECT [service_contract_id], [service_call_id],
                   ROW_NUMBER() OVER (PARTITION BY [service_contract_id], [visit_date] ORDER BY [id]) AS [n]
            FROM [svc].[contract_visit_day]
        ) d
        WHERE d.[n] > 1
        GROUP BY d.[service_contract_id], d.[service_call_id];

        -- Delete first: after the update a lowered count could look like one to delete.
        DELETE cv
        FROM [svc].[contract_visit] cv
        JOIN #asc_same_day x ON x.[service_call_id] = cv.[service_call_id]
        WHERE cv.[visits] <= x.[extra];

        UPDATE cv SET cv.[visits] = cv.[visits] - x.[extra], cv.[updated_at] = SYSUTCDATETIME()
        FROM [svc].[contract_visit] cv
        JOIN #asc_same_day x ON x.[service_call_id] = cv.[service_call_id]
        WHERE cv.[visits] > x.[extra];

        UPDATE sc
        SET sc.[visits_used] = CASE WHEN sc.[visits_used] > t.[extra] THEN sc.[visits_used] - t.[extra] ELSE 0 END,
            sc.[updated_at] = SYSUTCDATETIME()
        FROM [svc].[service_contract] sc
        JOIN (SELECT [service_contract_id], SUM([extra]) AS [extra]
              FROM #asc_same_day GROUP BY [service_contract_id]) t ON t.[service_contract_id] = sc.[id];

        DROP TABLE #asc_same_day;
    """)


def downgrade() -> None:
    """The visits given back are not taken again."""
