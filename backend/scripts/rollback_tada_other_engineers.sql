/*
    Removes only the Service-engineer test trips marked tada_seed / TADA-SEED.
    Trips already in trk.trip before that load, including ids 1 to 13, stay in place.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    DELETE adj
    FROM [trk].[trip_distance_adjustment] adj
    JOIN [trk].[trip] t ON t.[id] = adj.[trip_id]
    JOIN [trk].[trackable_activity] a ON a.[id] = t.[trackable_activity_id]
    WHERE a.[source_table] = N'tada_seed';

    DELETE g
    FROM [trk].[trip_gps_point] g
    JOIN [trk].[trip] t ON t.[id] = g.[trip_id]
    JOIN [trk].[trackable_activity] a ON a.[id] = t.[trackable_activity_id]
    WHERE a.[source_table] = N'tada_seed';

    DELETE t
    FROM [trk].[trip] t
    JOIN [trk].[trackable_activity] a ON a.[id] = t.[trackable_activity_id]
    WHERE a.[source_table] = N'tada_seed';

    DELETE FROM [trk].[trackable_activity]
    WHERE [source_table] = N'tada_seed';

    DELETE FROM [core].[status_history]
    WHERE [remarks] = N'TADA-SEED'
      AND [entity_type] LIKE N'tada-[0-9][0-9][0-9][0-9]-[0-9][0-9]';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
