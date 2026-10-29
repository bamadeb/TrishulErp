-- Service-call numbering (core.number_series, document_type = 'SERVICE_CALL').
--
-- next_document_no() needs a matching series row before any service call can be created (BYD import,
-- or the call form later). The lookup matches on company_id AND branch (specific branch, else a
-- company-wide NULL branch), preferring the branch-specific row.
--
-- IMPORTANT: the unique index UX_core_number_series_k1 is on
--   (branch_id, document_type, principal_id, fiscal_year_id)  -- company_id is NOT included.
-- So a company-wide (branch_id NULL) SERVICE_CALL series can exist only ONCE across all companies.
-- With more than one company that is unworkable, so this seeds ONE series PER ACTIVE BRANCH, which
-- also gives branch-wise call numbers (e.g. BBSR/SC/00001) that match the paper registers.
--
-- Idempotent: only inserts for branches that don't already have a SERVICE_CALL series.
-- Change the prefix ( b.[code] + N'/SC/' ) or padding below if you want a different format.

SET NOCOUNT ON;

INSERT INTO [core].[number_series]
    ([company_id], [document_type], [branch_id], [principal_id], [fiscal_year_id],
     [prefix], [next_number], [padding], [suffix])
SELECT
    b.[company_id], N'SERVICE_CALL', b.[id], NULL, NULL,
    b.[code] + N'/SC/', 1, 5, NULL
FROM [core].[branch] b
WHERE b.[is_active] = 1
  AND NOT EXISTS (
      SELECT 1 FROM [core].[number_series] ns
      WHERE ns.[document_type] = N'SERVICE_CALL'
        AND ns.[branch_id] = b.[id]
        AND ns.[principal_id] IS NULL
        AND ns.[fiscal_year_id] IS NULL
  );

-- Optional cleanup: remove the stray company-wide (branch NULL) SERVICE_CALL row created by the
-- earlier version of this script, but ONLY if it was never used (next_number still 1). Uncomment
-- to run it.
-- DELETE FROM [core].[number_series]
-- WHERE [document_type] = N'SERVICE_CALL' AND [branch_id] IS NULL AND [next_number] = 1;

-- Current SERVICE_CALL series, so you can confirm one row per branch:
SELECT ns.[id], co.[legal_name] AS company, br.[name] AS branch,
       ns.[prefix], ns.[next_number], ns.[padding], ns.[suffix], ns.[is_active]
FROM [core].[number_series] ns
JOIN [core].[company] co ON co.[id] = ns.[company_id]
LEFT JOIN [core].[branch] br ON br.[id] = ns.[branch_id]
WHERE ns.[document_type] = N'SERVICE_CALL'
ORDER BY co.[legal_name], br.[name];
