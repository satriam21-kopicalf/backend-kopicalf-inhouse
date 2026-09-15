# ESB Data Pipeline: Analysis Infrastructure Roadmap
## COGS Ratio & Usage Ratio Analysis Readiness

> **STATUS UPDATE 2026-09-15** — audited against the running backend. Items
> resolved since this document was written are marked here; sections below are
> kept for history where still accurate.
>
> | Item in this doc | Actual status |
> |---|---|
> | Bug #1 `_sync_product_details()` wrong schema | ✅ FIXED — `tasks.py::_sync_product_details` reads `esb_data.master_product` / writes `esb_data.master_product_detail` (1230 rows live) |
> | Bug #2 sub-category `category_esb_id` NULL | 🟡 MOSTLY FIXED 2026-09-15 — upsert now uses `COALESCE(EXCLUDED, existing)` so re-syncs stop NULLing the link; backfilled 25/166 from `master_product.raw_data` (`subCategoryID`→`categoryID`). Remaining 141 have **no products at all** (no analysis impact). Full close needs probing `/product/sub-category/{id}` detail with valid Core credentials — `company_configs.esb_username/password` are rejected by `/core/auth/login` (EC03100032); engine core creds live elsewhere |
> | Gap #1 `master_bom_material` missing | ✅ IMPLEMENTED — table live (2368 material lines / 337 BOM headers) + `tasks.py::_sync_bom_materials` fetches `/product/bom/{bomID}` per header, wired into the `BOM` entity sync |
> | Gap #2 `ITEM_JOURNAL` not in priority_entities | ✅ FIXED — priority list now also includes `PURCHASE_INVOICE`, `GOODS_DELIVERY`, `STOCK_OPNAME`, `SIMPLE_MANUFACTURING`, `GOODS_RECEIPT_RETURN`, `GOODS_RECEIPT` (trx_engine.py `backfill_entity`); ITEM_JOURNAL staging flowing (history backfill still pending for pre-window dates) |
> | `PRODUCTION_ORDER` / `PRODUCTION_MATERIAL` missing from `TRX_INDEX_VIEW` | 🔴 STILL OPEN |
> | `trx_raw_staging` / `report_raw_staging` schema | ⚠️ Doc says `esb_data` — both staging tables actually live in `public` |
> | New 2026-09-14/15: POS sales pipeline rebuilt | ✅ `report_pos_sales` now keyed by `(company_id, row_hash)` with in-memory qty grouping, rebuild mode, per-day completeness audit (count/qty 1%, total 3%), page-boundary overlap dedupe, parallel per-chunk backfill fan-out — see `reports.py::sync_pos_sales` / `sync_pos_sales_backfill` |
> | 2026-09-15 DB cleanup | ✅ 18 tabel di-drop (semua 0 baris, 0 referensi kode: `analysis_cogs_snapshot`, `analysis_usage_ratio`, `master_approval_flow`, `master_customer_pricelist`, `master_normalization`, `product_material_override`, `report_bill_of_material`, `report_daily_sales_payment_recapitulation`, `report_menu_cogs`, `report_purchase_recapitulation`, `report_sales_payment_summary`, `report_stock_opname`, `report_transfer`, `stock_opname_detail`, `waste_detail`, `esb_data.company_configs`, `public.branch_normalizations`, `public.company_normalizations`). Kode mati dihapus: 3 task Celery di `aggregation.py` + 3 entri `beat_schedule` di `worker.py`. `waste_header`/`stock_opname_header`/`stock_system_adjustment` DIPERTAHANKAN (dipakai `stock_waste.py` router yang live) |

**Tujuan akhir**: Membangun pipeline data yang akurat untuk mendukung analisis **COGS ratio** dan **usage ratio** — serta analisis analitis lainnya — dari data ESB yang sudah berhasil di-consume.

**Ruang lingkup**: `esb_data` schema, engine di `app/services/`, dan API endpoint ESB.

---

## 1. Bug Fixes — Perlu Perbaikan Segera

### Bug #1: `_sync_product_details()` Reference Schema Salah

**Lokasi**: `app/services/tasks.py` lines 729–734

**Masalah**: Fungsi ini masih mereferensikan tabel schema lama (public) alih-alih `esb_data`.

```python
# ❌ SALAH (sekarang):
SELECT esb_id FROM md_products WHERE company_id = %s
  AND NOT EXISTS (
    SELECT 1 FROM md_product_details d WHERE ...

# ✅ SEHARUSNYA:
SELECT esb_id FROM esb_data.master_product WHERE company_id = %s
  AND NOT EXISTS (
    SELECT 1 FROM esb_data.master_product_detail d WHERE ...
```

**Dampak**: `master_product_detail` tidak pernah terisi secara otomatis oleh sync — harusnya sinkron dari API detail produk (UOM variant, base price, SKU). Perlu ditentukan API endpoint apa yang mengembalikan data ini.

---

### Bug #2: `PRODUCT_SUB_CATEGORY` Tidak Link ke Parent Category

**Lokasi**: `app/services/tasks.py` — `_normalize("PRODUCT_SUB_CATEGORY")`

**Masalah**: `category_esb_id` selalu NULL karena:
1. API response `/product/sub-category` **TIDAK mengembalikan** `categoryID` (confirmed dari `app/schemas/esb.py` lines 91–102)
2. Tidak ada lookup map dari `PRODUCT_CATEGORY` yang disimpan sebelumnya

**Solusi**: Simpan `category_esb_id` dari response `/product/list` (yang punya `categoryID`) ke `master_sub_category` secara batch:

```sql
-- Patch untuk populate category_esb_id dari master_product yang sudah sync:
UPDATE esb_data.master_sub_category s
SET category_esb_id = p.category_esb_id
FROM esb_data.master_product p
WHERE p.company_id = s.company_id
  AND p.sub_category_esb_id = s.esb_id
  AND s.category_esb_id IS NULL;
```

Alternatif jangka panjang: Ambil dari API detail sub-category jika endpoint tersebut mengembalikan `categoryID`.

---

## 2. Schema Gaps — Tabel yang Belum Ada

### Gap #1: `master_bom_material` — CRITICAL untuk COGS

**Kebutuhan COGS**: BOM tanpa material line items = tidak bisa hitung HPP (Harga Pokok Produksi).

**Status sekarang**: `master_bill_of_material` hanya menyimpan header BOM (output product, qty, bom_type). Tidak ada tabel untuk raw material consumption per BOM line.

**Analisis endpoint ESB**:

| Endpoint | Deskripsi | Kegunaan |
|---|---|---|
| `/product/bom` | List BOM header | Sudah di-sync via `tasks.py` |
| `/product/bom/:id` | Detail BOM + material lines? | BELUM ada engine yang fetch ini |
| `/production/simple-manufacturing` | Hasil produksi (output, actual material used) | Sudah di `trx_raw_staging` via `TRX_INDEX_VIEW` |

**Rekomendasi**: Cek apakah `/product/bom/:id` atau `/product/bom-detail` mengembalikan material lines. Jika ya, buat sync task baru:

```sql
-- Tabel baru: master_bom_material
CREATE TABLE esb_data.master_bom_material (
    id              BIGSERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL,
    bom_esb_id      INTEGER NOT NULL,     -- FK ke master_bill_of_material
    line_num        INTEGER DEFAULT 1,
    product_esb_id  INTEGER NOT NULL,     -- raw material
    qty             NUMERIC(18,4) NOT NULL,
    hpp             NUMERIC(18,4) DEFAULT 0,
    cost            NUMERIC(18,4) GENERATED ALWAYS AS (qty * hpp) STORED,
    uom_name        VARCHAR(100),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, bom_esb_id, line_num)
);

CREATE INDEX ON esb_data.master_bom_material (company_id, bom_esb_id);
CREATE INDEX ON esb_data.master_bom_material (company_id, product_esb_id);
```

---

### Gap #2: `trx_raw_staging` Sinkronisasi untuk ITEM_JOURNAL

**Kebutuhan Usage Ratio**: Item journal mencatat semua pergerakan inventory per line item — ini yang menunjukkan actual consumption (bukan hanya theoretical dari BOM).

**Status sekarang**: `ITEM_JOURNAL` ada di `TRX_INDEX_VIEW` (line 282–299) dengan:
- `index_path`: `/inventory/item-journal`
- `identity_fields`: `["itemJournalNum"]`
- `view`: True

**MASALAH BESAR**: `ITEM_JOURNAL` **tidak ada di priority_entities list** (line 761–764 `backfill_entity`):

```python
priority_entities = (
    "PRODUCT_SALES", "RPT_GOODS_RECEIPT_RECAPITULATION"
)
```

→ `ITEM_JOURNAL` akan selalu di-skip di backfill (line 764: `if entity not in priority_entities`).

**Fix yang dibutuhkan**: Tambahkan `ITEM_JOURNAL` ke `priority_entities`.

---

### Gap #3: `master_product_variant` — Per-Branch Pricing

**Status sekarang**: `master_pricelist` punya `applicable_branch JSONB`, tapi tidak ada tabel untuk per-branch product variant pricing yang normalized.

**Rekomendasi**: Evaluasi apakah perlu. Untuk COGS ratio sederhana, `master_pricelist` sudah cukup.

---

## 3. Endpoint ESB — Belum Di-Wire ke Sync Task

### Belum Ada Engine Sync:

| Endpoint | Entity | Kebutuhan |
|---|---|---|
| `/corev1/sales/get-daily-sales-material-usage` (OMS) | MATERIAL_USAGE | **Usage ratio** — konsumsi material harian |
| `/report/item-journal-recap` | ITEM_JOURNAL_RPT | Report-shaped daily summary |
| `/report/production-recap` | PRODUCTION_RPT | Production recap |
| `/report/bom-usage` | BOM_USAGE_RPT | BOM actual usage |
| `/report/cogs-recap` | COGS_RPT | COGS summary (jika ESB menyediakan) |

### Sudah di `RPT_DIRECT` (trx_engine.py):

| Entity | Path | Window | Status |
|---|---|---|---|
| `RPT_STOCK_MOVEMENT` | `/report/stock-movement` | T-7 | ✅ Aktif |
| `RPT_SALES_PAYMENT_SUMMARY` | `/report/sales-payment-summary` | T-2 | ✅ Aktif |
| `RPT_GOODS_RECEIPT_RECAPITULATION` | `/report/goods-receipt-recapitulation` | T-2 | ✅ Aktif |

### Sudah di `TRX_INDEX_VIEW` (trx_engine.py) tapi Priority Issue:

| Entity | Path | Status |
|---|---|---|
| `BILL_OF_MATERIAL` | `/product/bom` | ⚠️ Ada index, tidak ada material lines |
| `ITEM_JOURNAL` | `/inventory/item-journal` | ⚠️ Tidak di priority_entities |
| `SIMPLE_MANUFACTURING` | `/production/simple-manufacturing` | ✅ Sudah di TRX sync |
| `PRODUCTION_ORDER` | `/production/production-order` | ❌ Tidak ada di TRX_INDEX_VIEW |
| `PRODUCTION_MATERIAL` | `/production/production-material` | ❌ Tidak ada di TRX_INDEX_VIEW |

---

## 4. COGS Ratio — Data Requirements & Gap Analysis

### Rumus COGS:

```
COGS = Σ (actual_material_cost) + Σ (production_overhead)
     = Σ (material_qty × material_hpp) dari ITEM_JOURNAL / PRODUCTION_MATERIAL
```

### Tabel yang Dibutuhkan:

```
analysis_cogs_snapshot
├── period_date          DATE
├── company_id           INTEGER
├── branch_esb_id        INTEGER
├── bom_esb_id          INTEGER         -- BOM yang digunakan
├── production_doc_num    VARCHAR(100)    -- Doc dari SIMPLE_MANUFACTURING
├── output_product_code   VARCHAR(50)
├── output_qty           NUMERIC(18,4)  -- Jumlah output produksi
├── standard_cogs        NUMERIC(18,4)  -- dari master_bom_material × master_pricelist
├── actual_cogs         NUMERIC(18,4)   -- dari ITEM_JOURNAL
├── cogs_variance        NUMERIC(18,4)  -- actual - standard
├── cogs_ratio          NUMERIC(8,4)    -- actual / standard (target = 1.0)
├── variance_reason      TEXT
├── created_at           TIMESTAMPTZ
```

### Pipeline yang Sudah Ada vs Belum:

| Komponen | Status | Keterangan |
|---|---|---|
| `master_bill_of_material` | ✅ Ada | Header BOM, tapi tanpa materials |
| `master_pricelist` | ✅ Ada | Standard cost per product |
| `trx_raw_staging: SIMPLE_MANUFACTURING` | ✅ Ada | Output produksi |
| `trx_raw_staging: ITEM_JOURNAL` | ⚠️ Ada, tidak sync | Entity ada, priority_entities perlu ditambah |
| `trx_raw_staging: GOODS_RECEIPT` | ✅ Ada | Input material |
| `master_bom_material` | ❌ Tidak ada | **CRITICAL GAP** |
| Sync task untuk `/product/bom/:id` | ❌ Tidak ada | Untuk fetch BOM material lines |

---

## 5. Usage Ratio — Data Requirements & Gap Analysis

### Rumus Usage Ratio:

```
Usage Ratio = Actual Usage / Standard Usage
Standard Usage = Σ (output_qty × bom_material_qty)
Actual Usage  = Σ ITEM_JOURNAL (consumption entries)
```

### Tabel yang Dibutuhkan:

```
analysis_usage_ratio
├── period_date          DATE
├── company_id           INTEGER
├── branch_esb_id        INTEGER
├── product_code         VARCHAR(50)
├── bom_esb_id          INTEGER
├── standard_usage_qty  NUMERIC(18,4)  -- dari BOM
├── actual_usage_qty    NUMERIC(18,4)  -- dari ITEM_JOURNAL
├── usage_ratio         NUMERIC(8,4)    -- actual / standard
├── variance_qty        NUMERIC(18,4)
├── variance_pct         NUMERIC(8,4)
├── status              VARCHAR(20)     -- EFFICIENT, OVER_USAGE, UNDER_USAGE
├── created_at           TIMESTAMPTZ
```

### Pipeline yang Sudah Ada vs Belum:

| Komponen | Status | Keterangan |
|---|---|---|
| `master_bill_of_material` | ✅ Ada | Standard usage per BOM |
| `master_bom_material` | ❌ Tidak ada | **CRITICAL GAP** |
| `trx_raw_staging: ITEM_JOURNAL` | ⚠️ Ada, tidak sync | Tidak di priority_entities |
| `trx_raw_staging: PRODUCTION_ORDER` | ❌ Tidak ada | `PRODUCTION_ORDER` tidak di TRX_INDEX_VIEW |
| `trx_raw_staging: PRODUCTION_MATERIAL` | ❌ Tidak ada | `PRODUCTION_MATERIAL` tidak di TRX_INDEX_VIEW |
| OMS `/corev1/sales/get-daily-sales-material-usage` | ❌ Tidak ada sync | **BELUM ADA ENGINE** |

---

## 6. Priority Implementation Roadmap

### Phase 1: Critical Bug Fixes (1–2 hari)

- [ ] Fix `_sync_product_details()` schema reference
- [ ] Run patch SQL untuk populate `category_esb_id` di sub_category
- [ ] Test: pastikan `master_product_detail` sync berjalan benar

### Phase 2: BOM Material Sync (2–3 hari)

- [ ] Buat `master_bom_material` table migration
- [ ] Audit API `/product/bom/:id` atau `/product/bom-detail` — apakah mengembalikan material lines?
- [ ] Buat sync task `_sync_bom_materials()`
- [ ] Wire ke `sync_master_data_router()` atau `sync_master_data_v2()`
- [ ] Test: verify BOM materials muncul di tabel

### Phase 3: ITEM_JOURNAL & Production Sync (2–3 hari)

- [ ] Tambahkan `ITEM_JOURNAL` ke `priority_entities` di `trx_engine.py`
- [ ] Tambahkan `PRODUCTION_ORDER` dan `PRODUCTION_MATERIAL` ke `TRX_INDEX_VIEW`
- [ ] Verifikasi data flowing ke `trx_raw_staging`
- [ ] Test: ITEM_JOURNAL rows masuk staging

### Phase 4: OMS Daily Material Usage (3–5 hari)

- [ ] Audit API `/corev1/sales/get-daily-sales-material-usage`
- [ ] Buat `esb_oms_raw_staging` atau reuse `report_raw_staging` dengan entity baru
- [ ] Buat sync task `sync_oms_daily_material_usage()`
- [ ] Wire ke scheduler
- [ ] Test: OMS data masuk staging

### Phase 5: Analysis Tables & Views (3–5 hari)

- [ ] Buat `analysis_cogs_snapshot` table
- [ ] Buat `analysis_usage_ratio` table
- [ ] Buat SQL view/materialized view untuk COGS ratio calculation
- [ ] Buat stored procedure `refresh_cogs_snapshot(company_id, period_date)`
- [ ] Buat stored procedure `refresh_usage_ratio(company_id, period_date)`
- [ ] Wire ke Celery task (daily after delta sync complete)

### Phase 6: Reporting & Dashboard (5–7 hari)

- [ ] Buat API endpoint `/api/v1/analysis/cogs-ratio`
- [ ] Buat API endpoint `/api/v1/analysis/usage-ratio`
- [ ] Buat dashboard page di frontend
- [ ] Alerting: usage ratio > 1.1 or < 0.9

---

## 7. Complete Gap Matrix

| Komponen | Pipeline Status | Engine Status | Priority |
|---|---|---|---|
| `master_product_detail` sync | ⚠️ Broken schema ref | tasks.py | 🔴 P1 |
| Sub-category → category link | ⚠️ NULL | tasks.py | 🔴 P1 |
| `master_bom_material` table | ❌ Tidak ada | ❌ Tidak ada | 🔴 P2 |
| BOM material lines fetch | ❌ Tidak ada | ❌ Tidak ada | 🔴 P2 |
| `ITEM_JOURNAL` priority | ⚠️ Defined, skipped | trx_engine.py | 🔴 P2 |
| `PRODUCTION_ORDER` TRX sync | ❌ Tidak ada | ❌ Tidak ada | 🟡 P3 |
| `PRODUCTION_MATERIAL` TRX sync | ❌ Tidak ada | ❌ Tidak ada | 🟡 P3 |
| OMS daily material usage | ❌ Tidak ada | ❌ Tidak ada | 🟡 P4 |
| `analysis_cogs_snapshot` | ✅ Dihapus 2026-09-15 | tabel + task Celery dihapus | ✅ Selesai |
| `analysis_usage_ratio` | ✅ Dihapus 2026-09-15 | tabel + task Celery dihapus | ✅ Selesai |
| `report_raw_staging` COGS report | ✅ Ada (goods receipt recap) | trx_engine.py | ✅ Selesai |
| `trx_raw_staging: SIMPLE_MANUFACTURING` | ✅ Ada | trx_engine.py | ✅ Selesai |
| `trx_raw_staging: GOODS_RECEIPT` | ✅ Ada | trx_engine.py | ✅ Selesai |
| `trx_raw_staging: PURCHASE_ORDER` | ✅ Ada | trx_engine.py | ✅ Selesai |
| `master_pricelist` | ✅ Ada | tasks.py | ✅ Selesai |
| `master_bill_of_material` (header) | ✅ Ada | tasks.py | ✅ Selesai |

---

## 8. Verifikasi Langkah

1. **Start backend**: `cd backend-kopicalf-inhouse && uvicorn app.main:app --reload`
2. **Check schema**: `psql` → `\dt esb_data.` → verify 22 master tables + 4 system tables
3. **Check running tasks**: `celery -A app.core.celery inspect active`
4. **Check sync history**: `SELECT entity_type, status, records_processed, completed_at FROM esb_data.sync_history ORDER BY completed_at DESC LIMIT 20;`
5. **Check ITEM_JOURNAL**: `SELECT COUNT(*) FROM esb_data.trx_raw_staging WHERE entity_type = 'ITEM_JOURNAL';`
6. **Check trx_engine status**: Look at Celery task logs for `backfill_entity` — ITEM_JOURNAL should appear after priority_entities fix

## 9. Ringkasan

Infrastruktur data ESB sudah cukup solid — dual-lane sync (backfill + delta + realtime), circuit breaker, completeness audit, dan report staging sudah berjalan. Untuk mendukung **COGS ratio** dan **usage ratio analysis**, ada **4 gap kritis**:

1. **`master_bom_material` tidak ada** — BOM tidak punya material lines, mustahil hitung standard cost
2. **`ITEM_JOURNAL` tidak di-priority** — tidak pernah ter-sync karena tidak ada di `priority_entities`
3. **BOM material fetch tidak ada** — tidak ada engine yang fetch material lines dari `/product/bom/:id`
4. **OMS daily material usage belum ada sync** — endpoint ESB OMS tersedia tapi belum ada engine

Fix dan implementasi bertahap dapat dimulai dari Phase 1 (bug fixes) tanpa mempengaruhi pipeline yang sudah berjalan.
