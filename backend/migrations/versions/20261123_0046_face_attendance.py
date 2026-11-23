"""Mobile face attendance (phase 1): tables and permissions.

  * hr.face_model                    face / anti-spoof model versions, so every score names its model
  * hr.employee_face                 registered face per employee with approval history
                                     (one Active row per employee, filtered unique index)
  * hr.work_location                 office geofences (default radius 150 m)
  * hr.attendance_policy             how strict attendance is (mode, challenge, thresholds, offline rules);
                                     seeded OFFICE and FIELD
  * hr.employee_attendance_policy    policy per employee from a date, with its work locations
    hr.employee_attendance_location  (child rows)
  * hr.attendance_challenge          one-time server nonce for an online punch (valid 2 minutes)
  * hr.attendance_punch              every check-in / check-out with its evidence (client_uuid unique)
  * hr.attendance_audit              append-only log of changes and photo / face-vector access
  * Permissions: hr.attendance.mark (every role), hr.attendance.view.team (TEAM_LEAD, MANAGEMENT),
    hr.attendance.manage, hr.attendance.photo.view, hr.face.register, hr.face.approve (ADMIN, HR)

Daily status stays computed by the Daily Attendance page (modules/hr/attendance), which reads these
punches next to the biometric ones; hr.attendance itself is not changed here.

Revision ID: 0046_face_attendance
Revises: 0043_biometric_foundation, 0045_max_pending_calls (joins the biometric and brand/service-settings lines)
Created: 2026-11-21 (renumbered 0045 on 2026-11-22, 0046 on 2026-11-23; applied to RDS on 2026-11-22 as 0045)
"""

from alembic import op

revision = "0046_face_attendance"
down_revision = ("0043_biometric_foundation", "0045_max_pending_calls")
branch_labels = None
depends_on = None

_STD = """
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_{t}_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_{t}_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL"""


def _std(table: str) -> str:
    return _STD.format(t=table)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE [hr].[face_model] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_face_model] PRIMARY KEY,
            [code] NVARCHAR(40) NOT NULL,
            [kind] NVARCHAR(20) NOT NULL CONSTRAINT [CK_hr_face_model_kind] CHECK ([kind] IN (N'Face', N'Anti-spoof')),
            [version] NVARCHAR(40) NOT NULL,
            [file_sha256] NVARCHAR(64) NULL,
            [vector_size] SMALLINT NULL,
            [default_match_threshold] DECIMAL(5,4) NULL,
            [default_review_threshold] DECIMAL(5,4) NULL,
            [is_current] BIT NOT NULL CONSTRAINT [DF_hr_face_model_is_current] DEFAULT (0),
            [activated_at] DATETIME2(0) NULL,
            {_std("face_model")},
            CONSTRAINT [UQ_hr_face_model_code_version] UNIQUE ([code], [version])
        );
        CREATE UNIQUE INDEX [UX_hr_face_model_current_kind] ON [hr].[face_model] ([kind])
            WHERE [is_current] = 1 AND [is_active] = 1;
    """)
    # OpenCV Zoo SFace (Apache 2.0), chosen 2026-11-21. 0.363 is OpenCV's published cosine line for
    # "same person"; scores between 0.30 and 0.363 go to HR review. The pilot tunes both.
    op.execute("""
        INSERT INTO [hr].[face_model]
            ([code], [kind], [version], [file_sha256], [vector_size],
             [default_match_threshold], [default_review_threshold], [is_current], [activated_at])
        VALUES (N'sface', N'Face', N'2021dec',
                N'0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79', 128,
                0.3630, 0.3000, 1, SYSUTCDATETIME());
    """)
    op.execute(f"""
        CREATE TABLE [hr].[employee_face] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_face] PRIMARY KEY,
            [employee_id] BIGINT NOT NULL,
            [photo_s3_key] NVARCHAR(300) NULL,
            [photo_sha256] NVARCHAR(64) NULL,
            [face_vector] VARBINARY(MAX) NULL,
            [face_model_id] BIGINT NULL,
            [face_confidence] DECIMAL(5,4) NULL,
            [sharpness] DECIMAL(9,2) NULL,
            [brightness] DECIMAL(6,2) NULL,
            [face_count] SMALLINT NULL,
            [status] NVARCHAR(20) NOT NULL CONSTRAINT [DF_hr_employee_face_status] DEFAULT (N'Pending approval')
                CONSTRAINT [CK_hr_employee_face_status]
                CHECK ([status] IN (N'Pending approval', N'Active', N'Rejected', N'Superseded', N'Deleted')),
            [registered_by_user_id] BIGINT NULL,
            [approved_by_user_id] BIGINT NULL,
            [approved_at] DATETIME2(0) NULL,
            [rejection_reason] NVARCHAR(300) NULL,
            [consent_at] DATETIME2(0) NULL,
            [delete_after] DATE NULL,
            {_std("employee_face")},
            CONSTRAINT [FK_hr_employee_face_employee] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]),
            CONSTRAINT [FK_hr_employee_face_model] FOREIGN KEY ([face_model_id]) REFERENCES [hr].[face_model] ([id])
        );
        CREATE INDEX [IX_hr_employee_face_employee] ON [hr].[employee_face] ([employee_id]);
        CREATE INDEX [IX_hr_employee_face_status] ON [hr].[employee_face] ([status]);
        CREATE UNIQUE INDEX [UX_hr_employee_face_active] ON [hr].[employee_face] ([employee_id])
            WHERE [status] = N'Active' AND [is_active] = 1;
    """)
    op.execute(f"""
        CREATE TABLE [hr].[work_location] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_work_location] PRIMARY KEY,
            [branch_id] BIGINT NULL,
            [name] NVARCHAR(120) NOT NULL,
            [latitude] DECIMAL(9,6) NOT NULL,
            [longitude] DECIMAL(9,6) NOT NULL,
            [radius_m] INT NOT NULL CONSTRAINT [DF_hr_work_location_radius_m] DEFAULT (150)
                CONSTRAINT [CK_hr_work_location_radius_m] CHECK ([radius_m] BETWEEN 10 AND 5000),
            [address] NVARCHAR(300) NULL,
            {_std("work_location")},
            CONSTRAINT [FK_hr_work_location_branch] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id])
        );
        CREATE INDEX [IX_hr_work_location_branch] ON [hr].[work_location] ([branch_id]);
    """)
    op.execute(f"""
        CREATE TABLE [hr].[attendance_policy] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance_policy] PRIMARY KEY,
            [code] NVARCHAR(20) NOT NULL,
            [name] NVARCHAR(80) NOT NULL,
            [mode] NVARCHAR(10) NOT NULL
                CONSTRAINT [CK_hr_attendance_policy_mode] CHECK ([mode] IN (N'Office', N'Field', N'Hybrid')),
            [challenge] NVARCHAR(20) NOT NULL CONSTRAINT [DF_hr_attendance_policy_challenge] DEFAULT (N'Blink')
                CONSTRAINT [CK_hr_attendance_policy_challenge] CHECK ([challenge] IN (N'None', N'Blink', N'Blink and turn')),
            [challenge_on_check_out] BIT NOT NULL CONSTRAINT [DF_hr_attendance_policy_challenge_out] DEFAULT (0),
            [antispoof_required] BIT NOT NULL CONSTRAINT [DF_hr_attendance_policy_antispoof] DEFAULT (1),
            [match_threshold] DECIMAL(5,4) NULL,
            [review_threshold] DECIMAL(5,4) NULL,
            [max_score_gap] DECIMAL(5,4) NOT NULL CONSTRAINT [DF_hr_attendance_policy_max_score_gap] DEFAULT (0.1000),
            [max_gps_accuracy_m] INT NOT NULL CONSTRAINT [DF_hr_attendance_policy_max_gps_accuracy_m] DEFAULT (100),
            [allow_offline] BIT NOT NULL CONSTRAINT [DF_hr_attendance_policy_allow_offline] DEFAULT (1),
            [offline_auto_accept] BIT NOT NULL CONSTRAINT [DF_hr_attendance_policy_offline_auto_accept] DEFAULT (1),
            [max_offline_hours] INT NOT NULL CONSTRAINT [DF_hr_attendance_policy_max_offline_hours] DEFAULT (72),
            {_std("attendance_policy")},
            CONSTRAINT [UQ_hr_attendance_policy_code] UNIQUE ([code])
        );
    """)
    op.execute("""
        INSERT INTO [hr].[attendance_policy] ([code], [name], [mode], [challenge])
        VALUES (N'OFFICE', N'Office staff: punch inside an office geofence', N'Office', N'Blink'),
               (N'FIELD', N'Field staff: punch anywhere, location recorded', N'Field', N'Blink');
    """)
    op.execute(f"""
        CREATE TABLE [hr].[employee_attendance_policy] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_attendance_policy] PRIMARY KEY,
            [employee_id] BIGINT NOT NULL,
            [policy_id] BIGINT NOT NULL,
            [from_date] DATE NOT NULL,
            [to_date] DATE NULL,
            {_std("employee_attendance_policy")},
            CONSTRAINT [FK_hr_employee_attendance_policy_employee] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]),
            CONSTRAINT [FK_hr_employee_attendance_policy_policy] FOREIGN KEY ([policy_id]) REFERENCES [hr].[attendance_policy] ([id]),
            CONSTRAINT [CK_hr_employee_attendance_policy_dates] CHECK ([to_date] IS NULL OR [to_date] >= [from_date])
        );
        CREATE INDEX [IX_hr_employee_attendance_policy_employee]
            ON [hr].[employee_attendance_policy] ([employee_id], [from_date]);
    """)
    op.execute("""
        CREATE TABLE [hr].[employee_attendance_location] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_attendance_location] PRIMARY KEY,
            [employee_attendance_policy_id] BIGINT NOT NULL,
            [work_location_id] BIGINT NOT NULL,
            CONSTRAINT [FK_hr_employee_attendance_location_assignment] FOREIGN KEY ([employee_attendance_policy_id])
                REFERENCES [hr].[employee_attendance_policy] ([id]) ON DELETE CASCADE,
            CONSTRAINT [FK_hr_employee_attendance_location_location] FOREIGN KEY ([work_location_id])
                REFERENCES [hr].[work_location] ([id]),
            CONSTRAINT [UQ_hr_employee_attendance_location] UNIQUE ([employee_attendance_policy_id], [work_location_id])
        );
    """)
    op.execute("""
        CREATE TABLE [hr].[attendance_challenge] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance_challenge] PRIMARY KEY,
            [employee_id] BIGINT NOT NULL,
            [nonce] NVARCHAR(64) NOT NULL,
            [punch_type] NVARCHAR(3) NOT NULL CONSTRAINT [CK_hr_attendance_challenge_punch_type] CHECK ([punch_type] IN (N'In', N'Out')),
            [challenge] NVARCHAR(20) NOT NULL,
            [issued_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_attendance_challenge_issued_at] DEFAULT (SYSUTCDATETIME()),
            [expires_at] DATETIME2(0) NOT NULL,
            [used_at] DATETIME2(0) NULL,
            CONSTRAINT [FK_hr_attendance_challenge_employee] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]),
            CONSTRAINT [UQ_hr_attendance_challenge_nonce] UNIQUE ([nonce])
        );
        CREATE INDEX [IX_hr_attendance_challenge_employee] ON [hr].[attendance_challenge] ([employee_id], [issued_at]);
    """)
    op.execute(f"""
        CREATE TABLE [hr].[attendance_punch] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance_punch] PRIMARY KEY,
            [client_uuid] NVARCHAR(36) NOT NULL,
            [employee_id] BIGINT NOT NULL,
            [attendance_id] BIGINT NULL,
            [attendance_date] DATE NOT NULL,
            [punch_type] NVARCHAR(3) NOT NULL CONSTRAINT [CK_hr_attendance_punch_punch_type] CHECK ([punch_type] IN (N'In', N'Out')),
            -- time
            [device_captured_at] DATETIME2(0) NULL,
            [device_elapsed_ms] BIGINT NULL,
            [device_boot_id] NVARCHAR(64) NULL,
            [server_received_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_attendance_punch_server_received_at] DEFAULT (SYSUTCDATETIME()),
            [effective_at] DATETIME2(0) NOT NULL,
            [time_trust] NVARCHAR(20) NOT NULL
                CONSTRAINT [CK_hr_attendance_punch_time_trust] CHECK ([time_trust] IN (N'Server', N'Device verified', N'Device unverified')),
            -- face
            [photo_s3_key] NVARCHAR(300) NULL,
            [photo_sha256] NVARCHAR(64) NULL,
            [frame_hashes] NVARCHAR(1000) NULL,
            [employee_face_id] BIGINT NULL,
            [face_model_id] BIGINT NULL,
            [device_score] DECIMAL(5,4) NULL,
            [server_score] DECIMAL(5,4) NULL,
            [face_status] NVARCHAR(20) NOT NULL CONSTRAINT [DF_hr_attendance_punch_face_status] DEFAULT (N'Not checked')
                CONSTRAINT [CK_hr_attendance_punch_face_status]
                CHECK ([face_status] IN (N'Matched', N'Below threshold', N'No face', N'Several faces', N'Not checked')),
            [challenge] NVARCHAR(20) NULL,
            [challenge_nonce] NVARCHAR(64) NULL,
            [challenge_result] NVARCHAR(10) NULL
                CONSTRAINT [CK_hr_attendance_punch_challenge_result] CHECK ([challenge_result] IN (N'Passed', N'Failed', N'Not done')),
            [antispoof_score] DECIMAL(5,4) NULL,
            -- location
            [latitude] DECIMAL(9,6) NULL,
            [longitude] DECIMAL(9,6) NULL,
            [gps_accuracy_m] DECIMAL(9,2) NULL,
            [location_captured_at] DATETIME2(0) NULL,
            [is_mock_location] BIT NOT NULL CONSTRAINT [DF_hr_attendance_punch_is_mock_location] DEFAULT (0),
            [work_location_id] BIGINT NULL,
            [distance_m] DECIMAL(10,1) NULL,
            [inside_geofence] BIT NULL,
            [address] NVARCHAR(300) NULL,
            -- device
            [device_id] NVARCHAR(100) NULL,
            [platform] NVARCHAR(20) NULL,
            [os_version] NVARCHAR(40) NULL,
            [app_version] NVARCHAR(40) NULL,
            [integrity_verdict] NVARCHAR(60) NULL,
            [keystore_signature] NVARCHAR(600) NULL,
            [ip_address] NVARCHAR(45) NULL,
            [capture_mode] NVARCHAR(10) NOT NULL
                CONSTRAINT [CK_hr_attendance_punch_capture_mode] CHECK ([capture_mode] IN (N'Online', N'Offline')),
            -- outcome
            [status] NVARCHAR(10) NOT NULL
                CONSTRAINT [CK_hr_attendance_punch_status] CHECK ([status] IN (N'Present', N'Pending', N'Rejected')),
            [status_reason] NVARCHAR(300) NULL,
            [reviewed_by_user_id] BIGINT NULL,
            [reviewed_at] DATETIME2(0) NULL,
            [review_remarks] NVARCHAR(300) NULL,
            {_std("attendance_punch")},
            CONSTRAINT [UQ_hr_attendance_punch_client_uuid] UNIQUE ([client_uuid]),
            CONSTRAINT [FK_hr_attendance_punch_employee] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]),
            CONSTRAINT [FK_hr_attendance_punch_attendance] FOREIGN KEY ([attendance_id]) REFERENCES [hr].[attendance] ([id]),
            CONSTRAINT [FK_hr_attendance_punch_face] FOREIGN KEY ([employee_face_id]) REFERENCES [hr].[employee_face] ([id]),
            CONSTRAINT [FK_hr_attendance_punch_model] FOREIGN KEY ([face_model_id]) REFERENCES [hr].[face_model] ([id]),
            CONSTRAINT [FK_hr_attendance_punch_location] FOREIGN KEY ([work_location_id]) REFERENCES [hr].[work_location] ([id])
        );
        CREATE INDEX [IX_hr_attendance_punch_employee_date] ON [hr].[attendance_punch] ([employee_id], [attendance_date]);
        CREATE INDEX [IX_hr_attendance_punch_status_date] ON [hr].[attendance_punch] ([status], [attendance_date]);
        CREATE INDEX [IX_hr_attendance_punch_effective_at] ON [hr].[attendance_punch] ([effective_at]);
    """)
    op.execute("""
        CREATE TABLE [hr].[attendance_audit] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance_audit] PRIMARY KEY,
            [entity] NVARCHAR(20) NOT NULL,
            [entity_id] BIGINT NOT NULL,
            [action] NVARCHAR(40) NOT NULL,
            [old_json] NVARCHAR(MAX) NULL,
            [new_json] NVARCHAR(MAX) NULL,
            [by_user_id] BIGINT NULL,
            [at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_attendance_audit_at] DEFAULT (SYSUTCDATETIME()),
            [ip_address] NVARCHAR(45) NULL
        );
        CREATE INDEX [IX_hr_attendance_audit_entity] ON [hr].[attendance_audit] ([entity], [entity_id], [at]);
    """)
    for table, description in [
        ("face_model", "Face and anti-spoof model versions; every score names the model that made it"),
        ("employee_face", "Registered face per employee for attendance, with approval history"),
        ("work_location", "Office geofences for face attendance"),
        ("attendance_policy", "Face attendance rules per group of employees"),
        ("employee_attendance_policy", "Attendance policy per employee from a date"),
        ("employee_attendance_location", "Work locations allowed for an employee's attendance policy"),
        ("attendance_challenge", "One-time server nonce for an online face punch"),
        ("attendance_punch", "Every mobile face check-in and check-out with its evidence"),
        ("attendance_audit", "Append-only log of attendance changes and photo / face-vector access"),
    ]:
        op.execute(
            f"EXEC sys.sp_addextendedproperty N'MS_Description', N'{description.replace(chr(39), chr(39) * 2)}', "
            f"N'SCHEMA', N'hr', N'TABLE', N'{table}';"
        )

    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'HR', v.[description]
        FROM (VALUES
            (N'hr.attendance.mark', N'Mark own attendance with a face check in the mobile app'),
            (N'hr.attendance.view.team', N'See the attendance punches of the team'),
            (N'hr.attendance.manage', N'Set up work locations and attendance policies; review flagged punches'),
            (N'hr.attendance.photo.view', N'Open attendance punch photos (each view is audited)'),
            (N'hr.face.register', N'Register an employee''s face for attendance'),
            (N'hr.face.approve', N'Approve or reject a registered face (not one you registered yourself)')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM (VALUES
            (N'ADMIN', N'hr.attendance.view.team'), (N'ADMIN', N'hr.attendance.manage'),
            (N'ADMIN', N'hr.attendance.photo.view'), (N'ADMIN', N'hr.face.register'), (N'ADMIN', N'hr.face.approve'),
            (N'HR', N'hr.attendance.view.team'), (N'HR', N'hr.attendance.manage'),
            (N'HR', N'hr.attendance.photo.view'), (N'HR', N'hr.face.register'), (N'HR', N'hr.face.approve'),
            (N'TEAM_LEAD', N'hr.attendance.view.team'), (N'MANAGEMENT', N'hr.attendance.view.team')
        ) v([role_code], [permission_code])
        JOIN [core].[role] r ON r.[code] = v.[role_code]
        JOIN [core].[permission] p ON p.[code] = v.[permission_code]
        WHERE NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
        );
    """)
    # Every role marks its own attendance.
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'hr.attendance.mark'
        WHERE NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
        );
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'hr.attendance.mark', N'hr.attendance.view.team', N'hr.attendance.manage',
                           N'hr.attendance.photo.view', N'hr.face.register', N'hr.face.approve');
        DELETE FROM [core].[permission]
        WHERE [code] IN (N'hr.attendance.mark', N'hr.attendance.view.team', N'hr.attendance.manage',
                         N'hr.attendance.photo.view', N'hr.face.register', N'hr.face.approve');
    """)
    for table in [
        "attendance_audit",
        "attendance_punch",
        "attendance_challenge",
        "employee_attendance_location",
        "employee_attendance_policy",
        "attendance_policy",
        "work_location",
        "employee_face",
        "face_model",
    ]:
        op.execute(f"DROP TABLE [hr].[{table}];")
