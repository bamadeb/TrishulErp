"""ASC visits counted by day: svc.contract_visit_day, and the days already worked.

  * svc.contract_visit_day   one row per ASC service call per India day an engineer reached its site.
                             That day used one ASC visit, however many engineers went.
  * Backfill: the days of visits already made (svc.service_visit.service_started_at) on calls of a live
    ASC that ran that day: the call's own ASC, or for a call not linked to one, the ASC covering its
    machine when the call was logged (it came in before the ASC reached Trishul). A call logged before
    the ASC started isn't an ASC call. A call already counted by hand stays on that ASC.
    Each call's total in svc.contract_visit becomes the larger of its days and the hand count, and the
    contract's visits_used moves by the difference.

Revision ids 0038/0039 are taken by another developer's migrations already on RDS, hence 0040.

Revision ID: 0040_asc_visit_days
Revises: 0038_merge_heads
Created: 2026-11-17
"""

from alembic import op

revision = "0040_asc_visit_days"
down_revision = "0038_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [svc].[contract_visit_day] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_contract_visit_day] PRIMARY KEY,
            [service_contract_id] BIGINT NOT NULL,
            [service_call_id] BIGINT NOT NULL,
            [visit_date] DATE NOT NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_contract_visit_day_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            CONSTRAINT [UQ_svc_contract_visit_day_call_date] UNIQUE ([service_call_id], [visit_date]),
            CONSTRAINT [FK_svc_contract_visit_day_service_contract_id]
                FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]),
            CONSTRAINT [FK_svc_contract_visit_day_service_call_id]
                FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id])
        );
    """)
    op.execute("""
        CREATE INDEX [IX_svc_contract_visit_day_service_contract_id]
            ON [svc].[contract_visit_day] ([service_contract_id], [visit_date]);
    """)
    op.execute("""
        EXEC sys.sp_addextendedproperty N'MS_Description',
            N'ASC visit days: one per service call per day an engineer reached the site (one ASC visit)',
            N'SCHEMA', N'svc', N'TABLE', N'contract_visit_day';
    """)
    # Days already worked. India date = UTC + 330 minutes.
    op.execute("""
        WITH days AS (
            SELECT DISTINCT v.[service_call_id],
                   CAST(DATEADD(MINUTE, 330, v.[service_started_at]) AS DATE) AS [visit_date]
            FROM [svc].[service_visit] v
            WHERE v.[is_active] = 1 AND v.[service_started_at] IS NOT NULL
        ),
        chosen AS (
            SELECT d.[service_call_id], d.[visit_date],
                   COALESCE(
                       cv.[service_contract_id],
                       CASE WHEN c.[service_contract_id] IS NOT NULL THEN
                           (SELECT TOP 1 sc.[id] FROM [svc].[service_contract] sc
                            WHERE sc.[id] = c.[service_contract_id] AND sc.[contract_type] = N'ASC'
                              AND d.[visit_date] BETWEEN sc.[start_date] AND sc.[end_date])
                       ELSE
                           -- Not linked: the ASC covering the machine when the call was logged.
                           (SELECT TOP 1 sc.[id] FROM [svc].[service_contract] sc
                            JOIN [svc].[contract_coverage] cc ON cc.[service_contract_id] = sc.[id] AND cc.[is_active] = 1
                            WHERE cc.[machine_unit_id] = c.[machine_unit_id] AND sc.[contract_type] = N'ASC'
                              AND sc.[is_active] = 1 AND sc.[status] <> N'Cancelled'
                              AND CAST(c.[received_at] AS DATE) BETWEEN sc.[start_date] AND sc.[end_date]
                              AND d.[visit_date] BETWEEN sc.[start_date] AND sc.[end_date]
                            ORDER BY sc.[end_date] DESC)
                       END
                   ) AS [service_contract_id]
            FROM days d
            JOIN [svc].[service_call] c ON c.[id] = d.[service_call_id] AND c.[is_active] = 1
            LEFT JOIN [svc].[contract_visit] cv ON cv.[service_call_id] = d.[service_call_id]
        )
        INSERT INTO [svc].[contract_visit_day] ([service_contract_id], [service_call_id], [visit_date])
        SELECT ch.[service_contract_id], ch.[service_call_id], ch.[visit_date]
        FROM chosen ch
        JOIN [svc].[service_contract] sc ON sc.[id] = ch.[service_contract_id]
        WHERE sc.[is_active] = 1 AND sc.[status] <> N'Cancelled';
    """)
    # Each call's total: the larger of its days and what was counted by hand; the contract moves by the change.
    op.execute("""
        SELECT d.[service_contract_id], d.[service_call_id], COUNT(*) AS [days],
               ISNULL(cv.[visits], 0) AS [before],
               CASE WHEN COUNT(*) > ISNULL(cv.[visits], 0) THEN COUNT(*) ELSE ISNULL(cv.[visits], 0) END AS [after]
        INTO #asc_call_totals
        FROM [svc].[contract_visit_day] d
        LEFT JOIN [svc].[contract_visit] cv ON cv.[service_call_id] = d.[service_call_id]
        GROUP BY d.[service_contract_id], d.[service_call_id], cv.[visits];

        UPDATE cv SET cv.[visits] = t.[after], cv.[updated_at] = SYSUTCDATETIME()
        FROM [svc].[contract_visit] cv
        JOIN #asc_call_totals t ON t.[service_call_id] = cv.[service_call_id]
        WHERE t.[after] <> t.[before];

        INSERT INTO [svc].[contract_visit] ([service_contract_id], [service_call_id], [visits], [remarks])
        SELECT t.[service_contract_id], t.[service_call_id], t.[after], NULL
        FROM #asc_call_totals t
        WHERE NOT EXISTS (SELECT 1 FROM [svc].[contract_visit] cv WHERE cv.[service_call_id] = t.[service_call_id]);

        UPDATE sc SET sc.[visits_used] = sc.[visits_used] + x.[added], sc.[updated_at] = SYSUTCDATETIME()
        FROM [svc].[service_contract] sc
        JOIN (SELECT [service_contract_id], SUM([after] - [before]) AS [added]
              FROM #asc_call_totals GROUP BY [service_contract_id]) x ON x.[service_contract_id] = sc.[id]
        WHERE x.[added] <> 0;

        DROP TABLE #asc_call_totals;
    """)


def downgrade() -> None:
    """Visits the days added stay in svc.contract_visit and svc.service_contract.visits_used."""
    op.execute("DROP TABLE [svc].[contract_visit_day];")
