"""Biometric integration foundation for future eSSL attendance sync.

  * hr.biometric_device              registered terminals / controllers
  * hr.biometric_employee_mapping    Trishul employee <-> biometric user id
  * hr.biometric_sync_log            every sync attempt (manual or scheduled)
  * hr.biometric_punch_log           stored punches with duplicate protection
  * Permissions: hr.biometric.view / manage / sync (ADMIN + HR)

Synchronization stays disabled by default (TRISHUL_BIOMETRIC_SYNC_ENABLED=false).
This revision does not invent eSSL API fields or seed punch data.

Parent: 0042_machine_engineer (main chain head). Local reporting heads
0038_reporting_assignment / 0039_reporting_close are intentionally left untouched.
0028_merge_service_report_salary is also preserved.

Revision ID: 0043_biometric_foundation
Revises: 0042_machine_engineer
Created: 2026-11-18
"""

from alembic import op

revision = "0043_biometric_foundation"
down_revision = "0042_machine_engineer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.biometric_device', N'U') IS NULL
        BEGIN
            CREATE TABLE hr.biometric_device (
                id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_hr_biometric_device PRIMARY KEY,
                code NVARCHAR(40) NOT NULL,
                name NVARCHAR(120) NOT NULL,
                vendor NVARCHAR(40) NOT NULL
                    CONSTRAINT DF_hr_biometric_device_vendor DEFAULT (N'ESSL'),
                serial_number NVARCHAR(80) NULL,
                location_name NVARCHAR(120) NULL,
                branch_id BIGINT NULL,
                external_device_id NVARCHAR(80) NULL,
                credential_secret_name NVARCHAR(100) NULL,
                base_url NVARCHAR(300) NULL,
                is_sync_enabled BIT NOT NULL
                    CONSTRAINT DF_hr_biometric_device_is_sync_enabled DEFAULT (0),
                last_synced_at DATETIME2(0) NULL,
                created_at DATETIME2(0) NOT NULL
                    CONSTRAINT DF_hr_biometric_device_created_at DEFAULT (SYSUTCDATETIME()),
                created_by_user_id BIGINT NULL,
                updated_at DATETIME2(0) NULL,
                updated_by_user_id BIGINT NULL,
                is_active BIT NOT NULL
                    CONSTRAINT DF_hr_biometric_device_is_active DEFAULT (1),
                row_version ROWVERSION NOT NULL,
                CONSTRAINT UQ_hr_biometric_device_code UNIQUE (code),
                CONSTRAINT FK_hr_biometric_device_branch
                    FOREIGN KEY (branch_id) REFERENCES core.branch(id)
            );
            CREATE INDEX IX_hr_biometric_device_branch ON hr.biometric_device(branch_id);
        END
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.biometric_sync_log', N'U') IS NULL
        BEGIN
            CREATE TABLE hr.biometric_sync_log (
                id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_hr_biometric_sync_log PRIMARY KEY,
                device_id BIGINT NULL,
                started_at DATETIME2(0) NOT NULL
                    CONSTRAINT DF_hr_biometric_sync_log_started_at DEFAULT (SYSUTCDATETIME()),
                finished_at DATETIME2(0) NULL,
                status NVARCHAR(20) NOT NULL,
                [trigger] NVARCHAR(20) NOT NULL,
                records_fetched INT NOT NULL
                    CONSTRAINT DF_hr_biometric_sync_log_records_fetched DEFAULT (0),
                records_inserted INT NOT NULL
                    CONSTRAINT DF_hr_biometric_sync_log_records_inserted DEFAULT (0),
                records_duplicate INT NOT NULL
                    CONSTRAINT DF_hr_biometric_sync_log_records_duplicate DEFAULT (0),
                error_message NVARCHAR(500) NULL,
                created_by_user_id BIGINT NULL,
                created_at DATETIME2(0) NOT NULL
                    CONSTRAINT DF_hr_biometric_sync_log_created_at DEFAULT (SYSUTCDATETIME()),
                CONSTRAINT FK_hr_biometric_sync_log_device
                    FOREIGN KEY (device_id) REFERENCES hr.biometric_device(id)
            );
            CREATE INDEX IX_hr_biometric_sync_log_device ON hr.biometric_sync_log(device_id);
            CREATE INDEX IX_hr_biometric_sync_log_started ON hr.biometric_sync_log(started_at DESC);
        END
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.biometric_employee_mapping', N'U') IS NULL
        BEGIN
            CREATE TABLE hr.biometric_employee_mapping (
                id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_hr_biometric_employee_mapping PRIMARY KEY,
                employee_id BIGINT NOT NULL,
                biometric_user_id NVARCHAR(80) NOT NULL,
                device_id BIGINT NULL,
                effective_from DATE NOT NULL,
                effective_to DATE NULL,
                created_at DATETIME2(0) NOT NULL
                    CONSTRAINT DF_hr_biometric_employee_mapping_created_at DEFAULT (SYSUTCDATETIME()),
                created_by_user_id BIGINT NULL,
                updated_at DATETIME2(0) NULL,
                updated_by_user_id BIGINT NULL,
                is_active BIT NOT NULL
                    CONSTRAINT DF_hr_biometric_employee_mapping_is_active DEFAULT (1),
                row_version ROWVERSION NOT NULL,
                CONSTRAINT FK_hr_biometric_employee_mapping_employee
                    FOREIGN KEY (employee_id) REFERENCES core.employee(id),
                CONSTRAINT FK_hr_biometric_employee_mapping_device
                    FOREIGN KEY (device_id) REFERENCES hr.biometric_device(id)
            );
            CREATE INDEX IX_hr_biometric_employee_mapping_employee
                ON hr.biometric_employee_mapping(employee_id);
            CREATE INDEX IX_hr_biometric_employee_mapping_user
                ON hr.biometric_employee_mapping(biometric_user_id);
            -- One active mapping per biometric user on a device (NULL device = global).
            CREATE UNIQUE INDEX UX_hr_biometric_employee_mapping_active
                ON hr.biometric_employee_mapping(biometric_user_id, device_id)
                WHERE is_active = 1 AND device_id IS NOT NULL;
            CREATE UNIQUE INDEX UX_hr_biometric_employee_mapping_active_global
                ON hr.biometric_employee_mapping(biometric_user_id)
                WHERE is_active = 1 AND device_id IS NULL;
        END
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.biometric_punch_log', N'U') IS NULL
        BEGIN
            CREATE TABLE hr.biometric_punch_log (
                id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_hr_biometric_punch_log PRIMARY KEY,
                device_id BIGINT NOT NULL,
                employee_id BIGINT NULL,
                biometric_user_id NVARCHAR(80) NOT NULL,
                punched_at DATETIME2(0) NOT NULL,
                punch_type NVARCHAR(20) NULL,
                external_punch_id NVARCHAR(100) NULL,
                source NVARCHAR(20) NOT NULL
                    CONSTRAINT DF_hr_biometric_punch_log_source DEFAULT (N'Sync'),
                sync_log_id BIGINT NULL,
                created_at DATETIME2(0) NOT NULL
                    CONSTRAINT DF_hr_biometric_punch_log_created_at DEFAULT (SYSUTCDATETIME()),
                created_by_user_id BIGINT NULL,
                is_active BIT NOT NULL
                    CONSTRAINT DF_hr_biometric_punch_log_is_active DEFAULT (1),
                CONSTRAINT FK_hr_biometric_punch_log_device
                    FOREIGN KEY (device_id) REFERENCES hr.biometric_device(id),
                CONSTRAINT FK_hr_biometric_punch_log_employee
                    FOREIGN KEY (employee_id) REFERENCES core.employee(id),
                CONSTRAINT FK_hr_biometric_punch_log_sync_log
                    FOREIGN KEY (sync_log_id) REFERENCES hr.biometric_sync_log(id)
            );
            -- Prefer vendor punch id when present.
            CREATE UNIQUE INDEX UX_hr_biometric_punch_external
                ON hr.biometric_punch_log(device_id, external_punch_id)
                WHERE external_punch_id IS NOT NULL AND is_active = 1;
            -- Composite fallback only when no external punch id is supplied.
            CREATE UNIQUE INDEX UX_hr_biometric_punch_composite
                ON hr.biometric_punch_log(device_id, biometric_user_id, punched_at)
                WHERE external_punch_id IS NULL AND is_active = 1;
            CREATE INDEX IX_hr_biometric_punch_employee ON hr.biometric_punch_log(employee_id, punched_at);
            CREATE INDEX IX_hr_biometric_punch_device_time ON hr.biometric_punch_log(device_id, punched_at DESC);
        END
    """)
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'HR', v.[description]
        FROM (VALUES
            (N'hr.biometric.view', N'See biometric devices, employee mappings, punch logs and sync history'),
            (N'hr.biometric.manage', N'Register and update biometric devices and employee mappings'),
            (N'hr.biometric.sync', N'Run manual biometric synchronization')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM (VALUES
            (N'ADMIN', N'hr.biometric.view'), (N'ADMIN', N'hr.biometric.manage'), (N'ADMIN', N'hr.biometric.sync'),
            (N'HR', N'hr.biometric.view'), (N'HR', N'hr.biometric.manage'), (N'HR', N'hr.biometric.sync')
        ) v([role_code], [permission_code])
        JOIN [core].[role] r ON r.[code] = v.[role_code]
        JOIN [core].[permission] p ON p.[code] = v.[permission_code]
        WHERE NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
        );
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'hr.biometric.view', N'hr.biometric.manage', N'hr.biometric.sync');
        DELETE FROM [core].[permission]
        WHERE [code] IN (N'hr.biometric.view', N'hr.biometric.manage', N'hr.biometric.sync');
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.biometric_punch_log', N'U') IS NOT NULL DROP TABLE hr.biometric_punch_log;
        IF OBJECT_ID(N'hr.biometric_employee_mapping', N'U') IS NOT NULL DROP TABLE hr.biometric_employee_mapping;
        IF OBJECT_ID(N'hr.biometric_sync_log', N'U') IS NOT NULL DROP TABLE hr.biometric_sync_log;
        IF OBJECT_ID(N'hr.biometric_device', N'U') IS NOT NULL DROP TABLE hr.biometric_device;
    """)
