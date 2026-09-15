-- 2026-09-14: Replace the POS sales line dedup key.
--
-- The sales-menu API endpoint returns NO unique per-line id (id_esb is NULL on
-- every stored row), so the old unique index
--   ux_pos_sales_line_dedup (company_id, sales_num, COALESCE(menu_code,''),
--   COALESCE(menu_name,''), COALESCE(menu_category_detail_name,''),
--   COALESCE(id_esb::text,''))
-- collapsed distinct instances of the same menu inside one order into a single
-- row, each upsert OVERWRITING qty of the previous one (~6% of lines/day;
-- 8331 orders on 2026-09-06 alone had head.payment_total != SUM(lines.total)).
--
-- New key: (company_id, row_hash) where row_hash = md5 of every distinguishing
-- line field (sales_num, bill_num, menu*, price/discount/tax fields, status,
-- notes, created_date) computed in app code. Identical instances merge with
-- qty SUMMED in the app before upsert; sync re-runs stay idempotent because
-- the upsert writes the absolute grouped qty.

DROP INDEX IF EXISTS esb_data.ux_pos_sales_line_dedup;

-- Old rows carry hashes from the previous (unused) row_hash scheme; clear them
-- so the unique index can be created. Hashes are re-derived by the sync's
-- row_hash upsert — the one-shot rebuild backfill regenerates every row.
UPDATE esb_data.report_pos_sales SET row_hash = NULL WHERE row_hash IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_pos_sales_line_hash
    ON esb_data.report_pos_sales USING btree (company_id, row_hash);
