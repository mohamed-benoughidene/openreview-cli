-- Migration 014: record the source document's filename on stored PII cache rows.
-- Without it the stored-PII surfaces could only identify a record by its hash.
ALTER TABLE pii_cache ADD COLUMN filename TEXT;
