-- Removes only the TrishulDev demo leave rows marked demo.leave / DEMO:.
-- Does not delete a balance that also has a non-demo transaction.
-- Does not delete 2026 attendance when that employee also has a non-demo row.
-- Does not delete the Present attendance class once any other class exists.
-- Run with a login that can write TrishulDev. Do not run against production.

IF DB_NAME() <> N'TrishulDev'
    THROW 51000, 'Refusing to roll back demo leave data because this is not TrishulDev.', 1;

BEGIN TRANSACTION;

DELETE r
FROM hr.leave_entitlement_run r
WHERE EXISTS (
    SELECT 1 FROM hr.leave_balance_transaction t
    WHERE t.source_type = N'demo.leave' AND t.employee_id = r.employee_id AND t.leave_year = r.leave_year
)
AND NOT EXISTS (
    SELECT 1 FROM hr.leave_balance_transaction t
    WHERE t.employee_id = r.employee_id AND t.leave_year = r.leave_year
      AND (t.source_type IS NULL OR t.source_type <> N'demo.leave')
);

DELETE a
FROM hr.attendance a
WHERE a.source = N'Manual'
  AND a.attendance_date >= '2026-01-01' AND a.attendance_date < '2027-01-01'
  AND EXISTS (
      SELECT 1 FROM hr.leave_balance_transaction t
      WHERE t.source_type = N'demo.leave' AND t.employee_id = a.employee_id
        AND t.created_by_user_id = a.created_by_user_id
  )
  AND NOT EXISTS (
      SELECT 1 FROM hr.attendance other
      WHERE other.employee_id = a.employee_id
        AND other.attendance_date >= '2026-01-01' AND other.attendance_date < '2027-01-01'
        AND (other.source <> N'Manual' OR other.created_by_user_id IS NULL
             OR other.created_by_user_id <> a.created_by_user_id)
  );

DELETE FROM hr.leave_attendance_class
WHERE attendance_status = N'Present' AND day_weight = 1.0
  AND (SELECT COUNT(*) FROM hr.leave_attendance_class) = 1
  AND created_by_user_id IN (
      SELECT DISTINCT created_by_user_id FROM hr.leave_balance_transaction WHERE source_type = N'demo.leave'
  );

DELETE FROM hr.leave_request WHERE reason LIKE N'DEMO:%';

SELECT leave_balance_id AS id
INTO #demo_balance
FROM hr.leave_balance_transaction
WHERE source_type = N'demo.leave' AND leave_balance_id IS NOT NULL
GROUP BY leave_balance_id;

DELETE FROM hr.leave_balance_transaction WHERE source_type = N'demo.leave';

DELETE b
FROM hr.leave_balance b
WHERE b.id IN (SELECT id FROM #demo_balance)
  AND NOT EXISTS (SELECT 1 FROM hr.leave_balance_transaction t WHERE t.leave_balance_id = b.id);

COMMIT TRANSACTION;
