"""Item ageing by barcode: a scanned GRN batch (lot) number is logged as a Lot scan.

  * inv.scan_log  resolved_type may be Lot: a batch label scanned (its lot number), whose stock and age come from
                  that batch's own GRN date.

Revision ID: 0055_batch_scan
Revises: 0054_stock_counts
Created: 2026-11-27
"""

from alembic import op

revision = "0055_batch_scan"
down_revision = "0054_stock_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE [inv].[scan_log] DROP CONSTRAINT [CK_inv_scan_log_resolved_type];")
    op.execute("""
        ALTER TABLE [inv].[scan_log] ADD CONSTRAINT [CK_inv_scan_log_resolved_type]
            CHECK ([resolved_type] IN (N'Item', N'Lot', N'Bin', N'Rack', N'Location', N'Many', N'Unknown'));
    """)


def downgrade() -> None:
    op.execute("UPDATE [inv].[scan_log] SET [resolved_type] = N'Item' WHERE [resolved_type] = N'Lot';")
    op.execute("ALTER TABLE [inv].[scan_log] DROP CONSTRAINT [CK_inv_scan_log_resolved_type];")
    op.execute("""
        ALTER TABLE [inv].[scan_log] ADD CONSTRAINT [CK_inv_scan_log_resolved_type]
            CHECK ([resolved_type] IN (N'Item', N'Bin', N'Rack', N'Location', N'Many', N'Unknown'));
    """)
