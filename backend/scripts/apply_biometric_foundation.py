"""Create biometric foundation tables on TrishulDev (does not run alembic upgrade).

Applies the same SQL as migration 0043_biometric_foundation. Refuses every database
except TrishulDev. Do not run automatically — invoke only when approved:

    uv run --no-sync python scripts/apply_biometric_foundation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from trishul_api.config import get_settings  # noqa: E402
from trishul_api.db.engine import create_db_engine  # noqa: E402
from trishul_api.secrets import create_secret_provider  # noqa: E402

REVISION = "0043_biometric_foundation"


def _engine():
    settings = get_settings()
    if settings.migration_db_secret_id:
        settings = settings.model_copy(update={"db_secret_id": settings.migration_db_secret_id})
        return create_db_engine(settings, create_secret_provider(settings))
    if settings.migration_db_user:
        settings = settings.model_copy(
            update={
                "db_user": settings.migration_db_user,
                "db_password": settings.migration_db_password,
                "db_secret_id": None,
            }
        )
        return create_db_engine(settings, None)
    secrets = create_secret_provider(settings) if settings.db_secret_id else None
    return create_db_engine(settings, secrets)


def main() -> None:
    engine = _engine()
    with Session(engine) as db:
        name = db.execute(text("SELECT DB_NAME()")).scalar()
        print(f"database {name}", flush=True)
        if name != "TrishulDev":
            raise SystemExit("Refusing to apply biometric foundation because this is not TrishulDev.")

        statements = [
            """
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
            """,
            """
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
            """,
            """
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
                CREATE UNIQUE INDEX UX_hr_biometric_employee_mapping_active
                    ON hr.biometric_employee_mapping(biometric_user_id, device_id)
                    WHERE is_active = 1 AND device_id IS NOT NULL;
                CREATE UNIQUE INDEX UX_hr_biometric_employee_mapping_active_global
                    ON hr.biometric_employee_mapping(biometric_user_id)
                    WHERE is_active = 1 AND device_id IS NULL;
            END
            """,
            """
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
                CREATE UNIQUE INDEX UX_hr_biometric_punch_external
                    ON hr.biometric_punch_log(device_id, external_punch_id)
                    WHERE external_punch_id IS NOT NULL AND is_active = 1;
                CREATE UNIQUE INDEX UX_hr_biometric_punch_composite
                    ON hr.biometric_punch_log(device_id, biometric_user_id, punched_at)
                    WHERE external_punch_id IS NULL AND is_active = 1;
                CREATE INDEX IX_hr_biometric_punch_employee ON hr.biometric_punch_log(employee_id, punched_at);
                CREATE INDEX IX_hr_biometric_punch_device_time ON hr.biometric_punch_log(device_id, punched_at DESC);
            END
            """,
            """
            INSERT INTO [core].[permission] ([code], [module], [description])
            SELECT v.[code], N'HR', v.[description]
            FROM (VALUES
                (N'hr.biometric.view', N'See biometric devices, employee mappings, punch logs and sync history'),
                (N'hr.biometric.manage', N'Register and update biometric devices and employee mappings'),
                (N'hr.biometric.sync', N'Run manual biometric synchronization')
            ) v([code], [description])
            WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
            """,
            """
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
            """,
            f"""
            IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = N'{REVISION}')
                INSERT INTO alembic_version (version_num) VALUES (N'{REVISION}')
            """,
        ]
        for sql in statements:
            db.execute(text(sql))
        present = {
            table: db.execute(text(f"SELECT OBJECT_ID(N'hr.{table}', N'U')")).scalar()
            for table in (
                "biometric_device",
                "biometric_employee_mapping",
                "biometric_punch_log",
                "biometric_sync_log",
            )
        }
        db.commit()
    print(f"biometric tables {present}", flush=True)


if __name__ == "__main__":
    main()
