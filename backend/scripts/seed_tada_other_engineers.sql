/*
    Adds TA/DA test trips for active Service engineers who have no trips yet.
    Existing trk.trip rows are not updated or deleted.

    Marker: source_table = tada_seed, route_polyline = TADA-SEED,
            status_history.remarks = TADA-SEED.
    Safe to run again: each row is skipped when its client_uuid already exists.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @actor BIGINT = (
        SELECT TOP (1) [id] FROM [core].[app_user] WHERE [is_active] = 1 ORDER BY [id]
    );
    IF @actor IS NULL
        THROW 50002, 'No active app user to sign the distance-adjustment audit.', 1;

    DECLARE @now DATETIME2(0) = SYSUTCDATETIME();
    DECLARE @month0 DATE = DATEFROMPARTS(YEAR(@now), MONTH(@now), 1);

    IF OBJECT_ID('tempdb..#plan') IS NOT NULL DROP TABLE #plan;

    ;WITH [months] AS (
        SELECT 0 AS [month_offset], @month0 AS [month_start]
        UNION ALL SELECT 1, DATEADD(MONTH, -1, @month0)
        UNION ALL SELECT 2, DATEADD(MONTH, -2, @month0)
    ),
    [people] AS (
        SELECT
            e.[id] AS [employee_id],
            e.[employee_code],
            COALESCE(b.[latitude], 20.296059) AS [start_latitude],
            COALESCE(b.[longitude], 85.824539) AS [start_longitude],
            dev.[user_device_id],
            CASE e.[employee_code]
                WHEN N'EMP0002' THEN N'Approved'
                WHEN N'EMP0004' THEN N'Rejected'
                WHEN N'EMP0005' THEN N'Sent'
                ELSE N'Pending'
            END AS [decision]
        FROM [core].[employee] e
        JOIN [hr].[department] d ON d.[id] = e.[department_id]
        LEFT JOIN [core].[branch] b ON b.[id] = e.[branch_id]
        OUTER APPLY (
            SELECT TOP (1) ud.[id] AS [user_device_id]
            FROM [core].[app_user] u
            JOIN [core].[user_device] ud ON ud.[app_user_id] = u.[id] AND ud.[is_active] = 1
            WHERE u.[employee_id] = e.[id] AND u.[is_active] = 1
            ORDER BY ud.[last_seen_at] DESC, ud.[id] DESC
        ) dev
        WHERE e.[is_active] = 1
          AND e.[status] = N'Active'
          AND (d.[code] IN (N'SERVICE', N'SVC') OR d.[name] LIKE N'%Service%')
          AND NOT EXISTS (
              SELECT 1 FROM [trk].[trip] t WHERE t.[employee_id] = e.[id] AND t.[is_active] = 1
          )
    ),
    [slots] AS (
        SELECT *
        FROM (VALUES
            (1, N'To site',      N'Own bike', N'Completed',   CAST(18.40 AS DECIMAL(8, 2)), CAST(17.80 AS DECIMAL(8, 2)), CAST(NULL AS DECIMAL(8, 2)), 0, N'Cuttack',  CAST(20.462521 AS DECIMAL(9, 6)), CAST(85.882988 AS DECIMAL(9, 6))),
            (2, N'Return',       N'Own bike', N'Completed',   CAST(22.10 AS DECIMAL(8, 2)), CAST(21.40 AS DECIMAL(8, 2)), CAST(NULL AS DECIMAL(8, 2)), 0, N'Bhadrak',  CAST(21.054480 AS DECIMAL(9, 6)), CAST(86.515602 AS DECIMAL(9, 6))),
            (3, N'To site',      N'Own car',  N'Completed',   CAST(46.20 AS DECIMAL(8, 2)), CAST(44.50 AS DECIMAL(8, 2)), CAST(42.00 AS DECIMAL(8, 2)), 1, N'Angul',    CAST(20.840046 AS DECIMAL(9, 6)), CAST(85.101780 AS DECIMAL(9, 6))),
            (4, N'Site to site', N'Own bike', N'Auto closed', CAST(15.60 AS DECIMAL(8, 2)), CAST(NULL AS DECIMAL(8, 2)), CAST(NULL AS DECIMAL(8, 2)), 0, N'Puri',     CAST(19.813382 AS DECIMAL(9, 6)), CAST(85.831465 AS DECIMAL(9, 6))),
            (5, N'Return',       N'Own car',  N'Completed',   CAST(31.00 AS DECIMAL(8, 2)), CAST(30.20 AS DECIMAL(8, 2)), CAST(28.00 AS DECIMAL(8, 2)), 0, N'Balasore', CAST(21.494980 AS DECIMAL(9, 6)), CAST(86.931664 AS DECIMAL(9, 6)))
        ) v([trip_no], [trip_type], [vehicle_type], [status], [gps_km], [map_km], [adjusted_km], [is_adjusted], [place], [end_latitude], [end_longitude])
    )
    SELECT
        p.[employee_id],
        p.[employee_code],
        p.[decision],
        m.[month_offset],
        m.[month_start],
        CONVERT(CHAR(7), m.[month_start], 23) AS [month_key],
        s.[trip_no],
        s.[trip_type],
        s.[vehicle_type],
        s.[status],
        s.[gps_km],
        s.[map_km],
        s.[adjusted_km],
        s.[is_adjusted],
        s.[place],
        p.[start_latitude],
        p.[start_longitude],
        s.[end_latitude],
        s.[end_longitude],
        DATEADD(HOUR, 8 + s.[trip_no], DATEADD(DAY, 2 + s.[trip_no] * 4, CAST(m.[month_start] AS DATETIME2(0)))) AS [start_at],
        CAST(ROUND(COALESCE(s.[map_km], s.[gps_km]) * 2.2 + 12, 0) AS INT) AS [duration_minutes],
        p.[user_device_id],
        CONVERT(UNIQUEIDENTIFIER, HASHBYTES('MD5', CONCAT(N'TADA-SEED-ACT|', p.[employee_id], N'|', CONVERT(CHAR(7), m.[month_start], 23), N'|', s.[trip_no]))) AS [activity_uuid],
        CONVERT(UNIQUEIDENTIFIER, HASHBYTES('MD5', CONCAT(N'TADA-SEED-TRIP|', p.[employee_id], N'|', CONVERT(CHAR(7), m.[month_start], 23), N'|', s.[trip_no]))) AS [trip_uuid]
    INTO #plan
    FROM [people] p
    CROSS JOIN [months] m
    CROSS JOIN [slots] s;

    IF NOT EXISTS (SELECT 1 FROM #plan)
        THROW 50003, 'No Service engineer without trips was found.', 1;

    ALTER TABLE #plan ADD [end_at] DATETIME2(0) NULL;
    UPDATE #plan SET [end_at] = DATEADD(MINUTE, [duration_minutes], [start_at]);

    INSERT INTO [trk].[trackable_activity] (
        [module_code], [activity_kind], [source_schema], [source_table], [source_id],
        [employee_id], [title], [target_latitude], [target_longitude],
        [client_uuid], [created_by_user_id], [is_active]
    )
    SELECT
        N'SVC', N'TADA seed', N'trk', N'tada_seed',
        p.[employee_id] * 1000 + p.[month_offset] * 10 + p.[trip_no],
        p.[employee_id],
        CONCAT(N'TADA-SEED ', p.[place]),
        p.[end_latitude], p.[end_longitude],
        p.[activity_uuid], @actor, 1
    FROM #plan p
    WHERE NOT EXISTS (
        SELECT 1 FROM [trk].[trackable_activity] a WHERE a.[client_uuid] = p.[activity_uuid]
    );

    INSERT INTO [trk].[trip] (
        [trackable_activity_id], [employee_id], [user_device_id], [client_uuid],
        [trip_type], [start_at], [start_latitude], [start_longitude],
        [end_at], [end_latitude], [end_longitude],
        [gps_distance_km], [map_distance_km], [adjusted_distance_km], [is_distance_adjusted],
        [duration_minutes], [vehicle_type], [status], [route_polyline],
        [created_by_user_id], [is_active]
    )
    SELECT
        a.[id], p.[employee_id], p.[user_device_id], p.[trip_uuid],
        p.[trip_type], p.[start_at], p.[start_latitude], p.[start_longitude],
        p.[end_at], p.[end_latitude], p.[end_longitude],
        p.[gps_km], p.[map_km], p.[adjusted_km], p.[is_adjusted],
        p.[duration_minutes], p.[vehicle_type], p.[status], N'TADA-SEED',
        @actor, 1
    FROM #plan p
    JOIN [trk].[trackable_activity] a ON a.[client_uuid] = p.[activity_uuid]
    WHERE NOT EXISTS (
        SELECT 1 FROM [trk].[trip] t WHERE t.[client_uuid] = p.[trip_uuid]
    );

    DECLARE @open_employee BIGINT = (
        SELECT TOP (1) [employee_id] FROM #plan WHERE [employee_code] = N'EMP0001'
    );
    DECLARE @open_uuid UNIQUEIDENTIFIER = CONVERT(UNIQUEIDENTIFIER, HASHBYTES('MD5', CONCAT(N'TADA-SEED-OPEN|', @open_employee)));
    DECLARE @open_activity UNIQUEIDENTIFIER = CONVERT(UNIQUEIDENTIFIER, HASHBYTES('MD5', CONCAT(N'TADA-SEED-OPEN-ACT|', @open_employee)));

    IF @open_employee IS NOT NULL
       AND NOT EXISTS (
            SELECT 1 FROM [trk].[trip]
            WHERE [employee_id] = @open_employee AND [status] = N'In progress' AND [is_active] = 1
       )
       AND NOT EXISTS (SELECT 1 FROM [trk].[trip] WHERE [client_uuid] = @open_uuid)
    BEGIN
        INSERT INTO [trk].[trackable_activity] (
            [module_code], [activity_kind], [source_schema], [source_table], [source_id],
            [employee_id], [title], [client_uuid], [created_by_user_id], [is_active]
        )
        SELECT N'SVC', N'TADA seed', N'trk', N'tada_seed', @open_employee * 1000 + 9,
               @open_employee, N'TADA-SEED open trip', @open_activity, @actor, 1
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[trackable_activity] WHERE [client_uuid] = @open_activity);

        INSERT INTO [trk].[trip] (
            [trackable_activity_id], [employee_id], [user_device_id], [client_uuid],
            [trip_type], [start_at], [start_latitude], [start_longitude],
            [gps_distance_km], [duration_minutes], [vehicle_type], [status], [route_polyline],
            [created_by_user_id], [is_active]
        )
        SELECT a.[id], p.[employee_id], p.[user_device_id], @open_uuid,
               N'To site', DATEADD(HOUR, 16, CAST(@month0 AS DATETIME2(0))),
               p.[start_latitude], p.[start_longitude],
               6.50, 20, N'Own bike', N'In progress', N'TADA-SEED',
               @actor, 1
        FROM (SELECT TOP (1) * FROM #plan WHERE [employee_id] = @open_employee) p
        JOIN [trk].[trackable_activity] a ON a.[client_uuid] = @open_activity;
    END

    INSERT INTO [trk].[trip_gps_point] (
        [trip_id], [recorded_at], [latitude], [longitude], [accuracy_m], [speed_kmph], [is_mock_location]
    )
    SELECT t.[id], t.[start_at], t.[start_latitude], t.[start_longitude], 12.0, 28.0, 0
    FROM [trk].[trip] t
    JOIN [trk].[trackable_activity] a ON a.[id] = t.[trackable_activity_id]
    WHERE a.[source_table] = N'tada_seed'
      AND NOT EXISTS (
          SELECT 1 FROM [trk].[trip_gps_point] g
          WHERE g.[trip_id] = t.[id] AND g.[recorded_at] = t.[start_at]
      );

    INSERT INTO [trk].[trip_gps_point] (
        [trip_id], [recorded_at], [latitude], [longitude], [accuracy_m], [speed_kmph], [is_mock_location]
    )
    SELECT t.[id], t.[end_at], t.[end_latitude], t.[end_longitude], 15.0, 0.0, 0
    FROM [trk].[trip] t
    JOIN [trk].[trackable_activity] a ON a.[id] = t.[trackable_activity_id]
    WHERE a.[source_table] = N'tada_seed'
      AND t.[end_at] IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM [trk].[trip_gps_point] g
          WHERE g.[trip_id] = t.[id] AND g.[recorded_at] = t.[end_at]
      );

    INSERT INTO [trk].[trip_distance_adjustment] (
        [trip_id], [previous_distance_km], [new_distance_km], [gps_distance_km_at_adjustment],
        [reason], [adjusted_by_user_id]
    )
    SELECT t.[id], t.[map_distance_km], t.[adjusted_distance_km], t.[gps_distance_km],
           N'TADA-SEED manual distance for payroll testing', @actor
    FROM [trk].[trip] t
    JOIN [trk].[trackable_activity] a ON a.[id] = t.[trackable_activity_id]
    WHERE a.[source_table] = N'tada_seed'
      AND t.[is_distance_adjusted] = 1
      AND t.[adjusted_distance_km] IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM [trk].[trip_distance_adjustment] adj
          WHERE adj.[trip_id] = t.[id] AND adj.[reason] LIKE N'TADA-SEED%'
      );

    INSERT INTO [core].[status_history] (
        [entity_type], [entity_id], [from_status], [to_status],
        [changed_by_user_id], [changed_at], [remarks]
    )
    SELECT DISTINCT
        CONCAT(N'tada-', p.[month_key]),
        p.[employee_id],
        N'Pending',
        p.[decision],
        @actor,
        @now,
        N'TADA-SEED'
    FROM #plan p
    WHERE p.[decision] <> N'Pending'
      AND NOT EXISTS (
          SELECT 1
          FROM [core].[status_history] h
          WHERE h.[entity_type] = CONCAT(N'tada-', p.[month_key])
            AND h.[entity_id] = p.[employee_id]
      );

    COMMIT TRANSACTION;

    SELECT
        p.[employee_code],
        p.[month_key],
        COUNT(*) AS [finished_trips],
        MAX(p.[decision]) AS [approval]
    FROM #plan p
    GROUP BY p.[employee_code], p.[month_key]
    ORDER BY p.[employee_code], p.[month_key];
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
