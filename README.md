# Backend Documentation - Kopi Calf In-House API

**Project:** `backend-kopicalf-inhouse`
**Stack:** FastAPI · PostgreSQL (Supabase) · Redis · Celery · XlsxWriter
**Purpose:** Enterprise integration hub — syncs transactional data from ESB POS/ERP API, normalizes master data, computes COGS, and exposes reporting endpoints to the Next.js frontend.
**Backend URL:** `http://localhost:8005` (dev) · `http://187.52.114.14:8005` (VPS)

---

## 1. Project Structure

```
backend-kopicalf-inhouse/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app entry, CORS, lifespan, middleware
│   ├── core/
│   │   ├── db.py             # psycopg2 ThreadedConnectionPool (max 20 connections)
│   │   ├── redis.py          # Redis client + helpers
│   │   ├── config.py         # Pydantic BaseSettings (DATABASE_URL, ESB_*, REDIS_URL…)
│   │   ├── worker.py         # Celery app + beat schedule (8 periodic tasks)
│   │   └── auth.py           # PBKDF2-SHA256 session tokens, require_user()
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py           # POST /auth/login, GET /auth/me, POST /auth/logout
│   │   ├── approval_lines.py  # Approval workflow configurations & RBAC
│   │   ├── stock_waste.py    # Stock opname & waste form CRUD
│   │   ├── internal_admin.py  # Employee management endpoints
│   │   ├── reports.py        # Report registry (30+ reports, T1/T2 tiers)
│   │   └── ...               # Other routers for sales, COGS, etc.
│   ├── services/
│   │   ├── trx_engine.py     # Dual-lane TRX ingest (backfill + delta + realtime)
│   │   ├── master_sync.py    # Master data pull from ESB (branches, products, BOM…)
│   │   ├── reports.py        # Report registry (30+ reports, T1/T2 tiers)
│   │   ├── export_engine.py  # Async XLSX generation → Supabase Storage
│   │   ├── tasks.py          # Celery tasks: sync_master_data, dynamic_schedule_router…
│   │   └── aggregation.py     # Aggregation service
│   └── utils/
│       └── cogs_calculator.py # COGS metrics calculator with 65% estimation
├── migrations/              # SQL schema files
├── run_migration.py        # Migration runner script
├── create_admin_user.py    # Admin user creation script
├── start_server.py         # Server startup script with env vars
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## 2. Quick Start

### Start Backend Server
```bash
python start_server.py
```
Server will start at `http://localhost:8005`

### Run Migrations
```bash
python run_migration.py
```

### Create Admin User
```bash
python create_admin_user.py
```

---

## 3. Authentication & Users

### Login Endpoint
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@kopicalf.com",
  "password": "Admin@123"
}
```

### Response
```json
{
  "token": "vG_uZSL3TPMrCIfe...",
  "expiresAt": "2026-09-17T06:47:08.217072+00:00",
  "user": {
    "id": 1,
    "email": "admin@kopicalf.com",
    "username": "admin",
    "full_name": "System Administrator",
    "role_code": "ADMIN",
    "role_name": "Administrator",
    "permissions": ["dashboard.view", "users.view", ...]
  }
}
```

### Default Users

| Username | Email | Password | Role |
|----------|-------|----------|------|
| admin | admin@kopicalf.com | Admin@123 | ADMIN |
| manager | manager@kopicalf.com | Manager@123 | MANAGER |
| staff | staff@kopicalf.com | Staff@123 | STAFF |

---

## 4. Database Schema

### Connection
- **Driver:** `psycopg2` with `ThreadedConnectionPool` (min 2, max 20 connections)
- **Connection function:** `get_db_connection()` → `psycopg2.pool.ThreadedConnectionPool.getconn()`
- **Dict cursor:** All routers use `cursor_factory=RealDictCursor` for column-name access
- **Search path:** `esb_data,public` (set in connection options)

### Schemas

| Schema | Purpose | Key Tables |
|--------|---------|-----------|
| `internal` | Auth, users, RBAC | `users`, `roles`, `permissions`, `role_permissions`, `sessions` |
| `esb_data` | Master data normalized from ESB | `master_division`, `master_department`, `master_employee`, `master_branch`, `master_product`, `master_bill_of_material`, `master_bom_material`, `sync_schedules`, etc. |
| `public` | Transactional staging + reports | `esb_raw_staging`, `trx_raw_staging`, `report_raw_staging`, `sync_history`, `dlq_logs`, `stock_opname`, `waste` |

### Master Tables (esb_data)

**`esb_data.master_division`** — Organizational divisions
- `id`, `code`, `name`, `manager_name`, `department_count`, `total_headcount`, `is_active`

**`esb_data.master_department`** — Departments under divisions
- `id`, `code`, `name`, `division_id`, `division_name`, `manager_name`, `employee_count`, `is_active`

**`esb_data.master_role`** — RBAC roles
- `id`, `code`, `name`, `description`, `is_system`

**`esb_data.master_permission`** — RBAC permissions
- `id`, `code`, `name`, `module`

### Auth Tables (internal)

**`internal.users`** — User accounts
- `id`, `username`, `email`, `password_hash`, `full_name`, `role_id`, `is_active`, `last_login_at`

**`internal.roles`** — User roles
- `id`, `code`, `name`, `description`, `is_system`

**`internal.permissions`** — Role permissions
- `id`, `code`, `name`, `module`

**`internal.sessions`** — Active sessions
- `id`, `token`, `user_id`, `expires_at`

### Key Tables Detail

**`esb_data.master_product`** — Product catalog
- `esb_id, company_id` → composite PK (unique per company)
- `bom_name` — BOM name if manufactured
- `category_name, sub_category_name, category_type_name` — denormalized for fast reporting

**`esb_data.master_bill_of_material`** — BOM header
- `product_esb_id` — links to `master_product`
- `bom_type_id, bom_type_name` — BOM classification

**`esb_data.master_bom_material`** — BOM line items (per-company, per-BOM)
- `company_id, bom_esb_id, line_num` → composite PK
- `material_product_esb_id` — component ingredient
- `hpp` — last HPP from ESB; `standard_cost = SUM(line.qty * line.hpp)`
- `qty, uom_qty, conversion_qty` — recipe quantities
- `yield_percent, weight_factor` — production yield parameters

**`esb_data.master_product_detail`** — Product variant (UOM/stock/purchase/sales flags)
- `company_id, esb_id` → composite PK
- `uom_name, qty, base_price, sku, is_base, is_stock, is_purchase, is_sales`

**`esb_raw_staging`** — Raw JSON from ESB per entity
- `(company_id, entity_type, esb_id)` → upsert key
- `raw_data` (JSONB) — full ESB response snapshot

**`trx_raw_staging`** — Transactional records (PRODUCT_SALES, PURCHASE_INVOICE, etc.)
- Row-level detail from POS and backfill lanes
- Key columns: `company_id, entity_type, doc_num, doc_date, branch_esb_id, product_esb_id, qty, unit_price, grand_total`

**`report_raw_staging`** — Aggregated/pre-computed report rows
- `(company_id, report_type, period_key, branch_esb_id)` → upsert key
- Persisted for fast retrieval, TTL cache

**`esb_data.sync_schedules`** — Per-company, per-endpoint cron schedule
- `company_id, endpoint_id, module ('master'|'report'|'pos')`
- `cron_expr` — e.g. `'0 3 * * *'` for 3 AM daily
- `last_run, next_run, enabled`

**`esb_data.endpoint_registry`** — All known ESB endpoints
- `entity, path, id_field, response_shape, category, module, is_documented`
- `response_shape`: `'array'` or `'envelope'` (dict with `data`/`count`)

**`esb_data.company_configs`** — Per-company ESB credentials
- `esb_company_code, esb_username, esb_password, static_token`

---

## 3. Authentication & Authorization

### Session Tokens
- Algorithm: **PBKDF2-SHA256**, 100,000 iterations, 16-byte random salt
- Format stored in DB: `pbkdf2_sha256$100000$<salt_hex>$<digest_hex>`
- Token in DB: 64-char hex (securerandom), 12-hour expiry
- Header: `Authorization: Bearer <token>`

### Users Table
```sql
users (id, email, username, password_hash, full_name, role_id,
       employee_id, is_active, token, token_expires_at, created_at)
```

### Roles & Permissions (RBAC)
- `roles` table: `id, code, name, is_system`
- `permissions` table: `id, code, module` (e.g. `admin.employees`, `report.sales`)
- `role_permissions` join table

### Permission Checks in Routers
- `require_user(authorization)` — decodes token, returns user dict
- `_require_perm(user, code)` — raises HTTP 403 if not present
- Internal admin endpoints require: `admin.employees`, `admin.users`, `admin.roles`

---

## 5. API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | User login |
| GET | `/api/v1/auth/me` | Get current user |
| POST | `/api/v1/auth/logout` | User logout |

### Master Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/divisions` | List all divisions |
| GET | `/api/v1/departments` | List all departments |
| GET | `/api/v1/departments?division_id=1` | Filter by division |
| GET | `/api/v1/branches` | List all branches |
| GET | `/api/v1/branches?branch_type=OUTLET` | Filter by type |

### Stock & Waste (Operational)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/stock-opname` | List stock opname records |
| GET | `/api/v1/stock-opname/{id}` | Get stock opname detail |
| POST | `/api/v1/stock-opname` | Create stock opname |
| PUT | `/api/v1/stock-opname/{id}` | Update stock opname |
| POST | `/api/v1/stock-opname/{id}/approve` | Approve stock opname |
| GET | `/api/v1/waste` | List waste forms |
| GET | `/api/v1/waste/{id}` | Get waste form detail |
| POST | `/api/v1/waste` | Create waste form |
| PUT | `/api/v1/waste/{id}` | Update waste form |
| POST | `/api/v1/waste/{id}/approve` | Approve waste form |

### Approval Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/approval-lines/configs` | List approval configurations |
| GET | `/api/v1/approval-lines/configs/{id}` | Get config detail |
| POST | `/api/v1/approval-lines/configs` | Create config |
| PUT | `/api/v1/approval-lines/configs/{id}` | Update config |
| DELETE | `/api/v1/approval-lines/configs/{id}` | Delete config |
| GET | `/api/v1/approval-lines/requests` | List approval requests |
| POST | `/api/v1/approval-lines/requests` | Create request |
| POST | `/api/v1/approval-lines/requests/{id}/approve` | Approve request |
| POST | `/api/v1/approval-lines/requests/{id}/reject` | Reject request |

### RBAC

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/roles` | List all roles |
| GET | `/api/v1/permissions` | List all permissions |
| GET | `/api/v1/roles/{id}/permissions` | Get role permissions |
| PUT | `/api/v1/roles/{id}/permissions` | Update role permissions |

### Internal Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/internal/employees` | List employees |
| GET | `/api/v1/internal/employees/{id}` | Get employee detail |
| POST | `/api/v1/internal/employees` | Create employee |
| PUT | `/api/v1/internal/employees/{id}` | Update employee |
| GET | `/api/v1/internal/users` | List users |
| POST | `/api/v1/internal/users` | Create user |
| PUT | `/api/v1/internal/users/{id}` | Update user |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/reports` | List all reports |
| GET | `/api/v1/reports/{slug}` | Get report data |
| GET | `/api/v1/reports/{slug}/metadata` | Get report metadata |
| GET | `/api/v1/dashboard/summary` | Dashboard summary |
| GET | `/api/v1/sales/recap-report` | Sales recap report |

### Example: List Divisions
```bash
curl -H "Authorization: Bearer <token>" \
     "http://localhost:8005/api/v1/divisions"
```

### Example: Create Approval Request
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"config_id": 1, "entity_type": "STOCK_OPNAME", "entity_id": 123}' \
  "http://localhost:8005/api/v1/approval-lines/requests"
```

---

## 6. ESB API Integration

### Base URL
```
ESB_CORE_URL = https://services.esb.co.id/core
ESB_FALLBACK_USERNAME = CALFSUPERADMINOPS
```

### Auth Flow (per company)
1. `POST /auth/login` with `username + password` → base JWT
2. `POST /auth/login/company` with base JWT + `companyCode` → scoped JWT
3. Scoped JWT used for all subsequent requests

### Circuit Breaker
- Class: `ESBCircuitBreaker` (closed/open/half-open states)
- Threshold: 3 failures → OPEN
- Reset timeout: 60 seconds → HALF_OPEN
- One test request → CLOSED if success, re-OPEN if fail

### Auth Serialization (Redis Lock)
- Lock key: `esb_auth_lock:<company_code>`
- TTL: 30 seconds
- Prevents concurrent logins invalidating each other's base JWT
- Function: `_auth_locked_company_token()` in `trx_engine.py`

### ESBClient (`tasks.py`)
- Wraps httpx.Client with token refresh and circuit breaker
- Auto-re-auth on 401 or `EC03100001` code
- `get(path, params)` → normalized JSON body

### Page Extraction (`_extract_page`)
- `shape='array'`: `body.result` is the list
- `shape='envelope'`: `body.result.data` + `body.result.count` → compute `total_pages`

---

## 7. Master Data Sync (`app/services/tasks.py`)

### Normalizers (`_normalize`)
Maps ESB entity → `(schema.table, tuple)` for upsert.

| Entity | Target Table | Key Fields |
|--------|-------------|-----------|
| `BRANCH` | `master_branch` | name, branch_code, is_active |
| `PRODUCT` | `master_product` | name, product_code, bom_name, category |
| `CATEGORY` | `master_category` | code, name, type_name |
| `PRODUCT_SUB_CATEGORY` | `master_sub_category` | category_esb_id, code, name |
| `PRODUCT_UNIT` | `master_unit` | code, name |
| `PRICELIST` | `master_pricelist` | product, branch, price, applicable_branch |
| `SUPPLIER` | `master_supplier` | name, category, status, due_date |
| `CUSTOMER` | `master_customer` | name, code, payment_due_days |
| `BOM` | `master_bill_of_material` | product, code, name, type |
| `PRODUCT_DETAIL` | `master_product_detail` | (via `/product/{id}`) |
| `BOM_MATERIAL` | `master_bom_material` | (via `/product/bom/{id}`) |
| `ACC_*` | `master_*` | (charts of account, taxes, cost centers, etc.) |

### Sync Functions

**`sync_endpoint_data()`**
- Paginated pull: `?page=N&limit=100`
- Batch upsert to `esb_raw_staging` (raw JSON)
- Deduplicate by `(company_id, entity_type, esb_id)`
- Normalize → upsert to target `master_*` table
- Error rows → `dlq_logs`

**`_sync_product_details()`**
- For each `master_product` without `master_product_detail` rows
- Fetch `/product/{esb_id}` → `productDetails[]` array
- Upsert variant rows

**`_sync_bom_materials()`**
- For each BOM header in `master_bill_of_material`
- Fetch `/product/bom/{esb_id}` → `bomDetails[]` array
- Standard cost = `SUM(line.qty * line.lastHpp)`

### Dynamic Scheduling
- Tables: `endpoint_registry` + `sync_schedules`
- `cron_expr` stored per schedule
- `dynamic_schedule_router()`: runs every minute, checks `next_run <= NOW()`
- Dispatches: `sync_company_data` (master), `sync_report` (report), `sync_pos_sales` (pos)
- `sync_master_data_router()`: older interval-based router, checks engine settings

---

## 8. TRX Engine (`app/services/trx_engine.py`)

### Dual-Lane Architecture

| Lane | Trigger | Window | Priority |
|------|---------|--------|----------|
| Lane A (Backfill) | `backfill_router()` beat | Historical range | Low (off-peak) |
| Lane B (Delta) | `delta_sync_trx()` beat | Watermark gap | Medium |
| Lane C (Realtime) | `backfill_router()` beat | Last 24h | High (every 5 min) |

### Entity Index (`TRX_INDEX_VIEW` — 30+ types)

| Entity | Priority | ESB Endpoint | Staging Table |
|--------|----------|-------------|--------------|
| `PRODUCT_SALES` | 1 | `/report/product-sales-summary` | `trx_raw_staging` |
| `PURCHASE_INVOICE` | 2 | `/report/purchase-invoice` | `trx_raw_staging` |
| `PURCHASE_ORDER` | 3 | `/report/purchase-order` | `trx_raw_staging` |
| `GOODS_RECEIPT` | 4 | `/report/goods-receipt` | `trx_raw_staging` |
| `GOODS_DELIVERY` | 5 | `/report/goods-delivery` | `trx_raw_staging` |
| `STOCK_OPNAME` | 6 | `/report/stock-opname` | `stock_opname` |
| `PURCHASE_RETURN` | 7 | `/report/purchase-return` | `trx_raw_staging` |
| `ITEM_JOURNAL` | 8 | `/report/item-journal` | `trx_raw_staging` |
| `SIMPLE_MANUFACTURING` | 9 | `/report/simple-manufacturing` | `trx_raw_staging` |
| … | … | … | … |

### Key Functions

**`pull_trx_window(entity, company_id, date_from, date_to, client, shape)`**
- Paginated pull from ESB report endpoint
- `row_hash = MD5(company+entity+doc_num+doc_date)` as idempotency key
- Surrogate key: if `doc_num` is NULL/empty, derive from `hash(doc_date+product+branch+amount)`

**`delta_sync_trx()` — Lane B**
- `last_synced_at` watermark per entity per company
- Gap: `now - last_synced_at`
- Companies: only those with `company_configs.is_active = true`

**`realtime_sync_trx()` — Lane C**
- Last 24 hours from `now`
- Same watermark system, narrower window

**`backfill_entity(entity, company_id, client, date_from, date_to)`**
- Full historical backfill for one entity/company
- Redis lock: `backfill_lock:{company_id}` (5-min TTL, extensible)

**`backfill_router()` — Lane A**
- Beat task every 25 minutes
- Enqueues `backfill_entity` per company per entity in priority order
- Companies 1–8 tracked

**`completeness_audit(entity, company_id)`**
- Watermark-based self-healing
- Marks incomplete if: `(end_date - start_date) > 7 days AND record_count < threshold`
- Logs to `sync_history` with `status='INCOMPLETE'`

### Redis Keys
| Key | Purpose | TTL |
|-----|---------|-----|
| `backfill_lock:{company_id}` | Prevent concurrent backfill per company | 5 min (extensible) |
| `esb_auth_lock:{company_code}` | Serialize ESB login flow | 30s |

---

## 7. Reports (`app/services/reports.py`)

### Report Registry (`REPORTS` dict — 30+ reports)

#### T1 Reports (from `trx_raw_staging`)
| Slug | Category | Description |
|------|---------|-------------|
| `sales-daily` | sales | Daily sales by branch/product |
| `sales-by-branch` | sales | Branch performance summary |
| `sales-by-product` | sales | Top products by revenue |
| `purchase-order` | purchasing | PO summary by supplier/branch |
| `purchase-invoice` | purchasing | Invoices with payment status |
| `goods-receipt` | purchasing | GRN with PO linkage |
| `goods-delivery` | purchasing | Delivery notes |
| `stock-opname-report` | inventory | Stock take results |
| `stock-movement` | inventory | In/out movement log |
| `manufacturing-output` | manufacturing | Production output vs BOM |
| `item-journal` | financial | Journal entries |

#### T2 Reports (from `report_raw_staging`)
| Slug | Category | Description |
|------|---------|-------------|
| `cogs-summary` | financial | COGS by branch/period |
| `profit-loss` | financial | P&L by branch |
| `branch-summary` | operational | KPI summary per branch |

### Query Pattern
- `iter_report_rows(slug, filters)` → generator yielding dict rows
- `_generic_trx_rows(entity, filters)` → common TRX query builder
- `_stock_opname_rows(filters)`, `_purchase_order_rows(filters)` → specialized
- `report_raw_staging` upsert with TTL metadata

### API Endpoints
```
GET /reports                        → list all reports with metadata
GET /reports/{slug}                → run report, return rows
GET /reports/{slug}/metadata        → schema, parameters, last_run
GET /reports/sales-recap            → sales recap with pagination + filters
GET /reports/sales-recap-detail     → raw POS lines (20+ filters)
```

---

## 8. COGS Analysis (`app/utils/cogs_calculator.py`)

### Formula
```
Estimated COGS = grand_total × 0.65   (65% of revenue)
Usage Ratio    = (total_hpp_used / (grand_total × 0.65)) × 100
COGS Ratio     = (total_hpp_used / grand_total) × 100
Gap            = Estimated COGS − total_hpp_used
```

### Flagging Thresholds
- Branch flagged if: `usage_ratio > 105` OR `cogs_ratio > (target + 10)` (i.e., >75% for 65% target)
- `target_cogs` configurable per company

### Output Schema
```json
{
  "period": "YYYY-MM",
  "company_id": 1,
  "target_cogs": 0.65,
  "branches": [{
    "branch_id": 1,
    "branch_name": "Kopi Calf Cipete",
    "grand_total": 150000000,
    "total_hpp_used": 97500000,
    "estimated_cogs": 97500000,
    "cogs_ratio": 0.65,
    "usage_ratio": 100.0,
    "gap": 0,
    "flagged": false
  }]
}
```

---

## 9. Stock & Waste (`app/routers/stock.py`, `app/routers/waste.py`)

### Stock Opname
- `GET /stock-opname` → list with filters (branch, status, date range)
- `GET /stock-opname/summary` → KPI counts (total, pending, completed)
- `GET /stock-opname/pending-count` → count of pending opnames

### Waste Tracking
- `GET /waste` → list waste records with filters
- `GET /waste/summary` → aggregate KPIs

### System Stock
- `GET /stock/system` → product × branch matrix
- Shows: `available_stock` from `master_branch`

---

## 10. Export Engine (`app/services/export_engine.py`)

### Process
1. HTTP request: `POST /reports/{slug}/export`
2. Task queued: `generate_export()` → Celery queue_export
3. Worker fetches report rows
4. Writes XLSX with `xlsxwriter` constant_memory mode (streaming)
5. Uploads to Supabase Storage bucket `report-exports` (private)
6. Returns signed URL (24h expiry)

### Signed URL Flow
```
export_engine.py → supabase.storage.from_(bucket).upload(path, file)
                  → supabase.storage.from_(bucket).create_signed_url(path, 24*3600)
```

---

## 11. Celery Beat Schedule (`app/core/worker.py`)

| Task | Schedule | Queue | Purpose |
|------|----------|-------|---------|
| `trx-realtime-sync` | Every 5 min | queue_sync | Lane C realtime delta |
| `trx-backfill-router` | Every 25 min | queue_backfill | Lane A historical backfill |
| `trx-direct-reports-delta` | Every 15 min | queue_report | Direct TRX report delta |
| `trx-direct-reports` | 06:00 WIB daily | queue_report | Deep TRX report refresh |
| `trx-completeness-audit` | 06:00 WIB daily | queue_sync | Watermark self-heal |
| `pos-sales-recovery` | 07:00 WIB daily | queue_sync | POS gap recovery |
| `sync-master-data` | 03:00 WIB daily | queue_master | Master data sync |
| `dynamic-schedule-router` | Every 1 min | queue_master | Cron-based dynamic dispatch |

### Queues
- `queue_master` — Master data (endpoints, product details, BOM)
- `queue_sync` — TRX realtime + completeness audit + POS recovery
- `queue_backfill` — Historical TRX backfill
- `queue_report` — Direct TRX reports (no staging, direct ESB query)
- `queue_export` — XLSX export generation

---

## 12. Operational Window (`app/services/operational_window.py`)

- **Window:** 03:00–08:00 WIB (Asia/Jakarta)
- **Override:** `ALLOW_OUTSIDE_WINDOW=1` env var bypasses gate
- All sync tasks check `is_within_operational_window()` before running
- `get_operational_window_status()` returns: `{in_window, next_open, next_close, timezone}`

---

## 13. Internal Admin API (`app/routers/internal_admin.py`)

### Endpoints (all require `Authorization: Bearer <token>`)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/api/v1/internal/employees` | admin.employees | List employees |
| GET | `/api/v1/internal/employees/{id}` | admin.employees | Get + shifts + deductions |
| POST | `/api/v1/internal/employees` | admin.employees | Create employee |
| PUT | `/api/v1/internal/employees/{id}` | admin.employees | Update employee |
| DELETE | `/api/v1/internal/employees/{id}` | admin.employees | Delete (no linked user) |
| POST | `/api/v1/internal/employees/{id}/shifts` | admin.employees | Add shift |
| DELETE | `/api/v1/internal/employees/{id}/shifts/{sid}` | admin.employees | Delete shift |
| POST | `/api/v1/internal/employees/{id}/deductions` | admin.employees | Add deduction |
| DELETE | `/api/v1/internal/employees/{id}/deductions/{did}` | admin.employees | Delete deduction |
| GET | `/api/v1/internal/users` | admin.users | List all users |
| POST | `/api/v1/internal/users` | admin.users | Create user |
| PUT | `/api/v1/internal/users/{id}` | admin.users | Update user |
| DELETE | `/api/v1/internal/users/{id}` | admin.users | Delete (not self) |
| GET | `/api/v1/internal/roles` | admin.roles | List roles + permission IDs |
| GET | `/api/v1/internal/permissions` | admin.roles | List all permissions |
| PUT | `/api/v1/internal/roles/{id}/permissions` | admin.roles | Update role permissions |

### Password Hashing
```python
salt = os.urandom(16)
digest = pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
# Stored as: pbkdf2_sha256$100000$<salt_hex>$<digest_hex>
```

---

## 14. Key API Endpoints Summary

### Authentication
```
POST /api/v1/auth/login        → {token, expires_at, user}
GET  /api/v1/auth/me          → current user + permissions
POST /api/v1/auth/logout      → invalidate token
```

### Reports
```
GET /api/v1/reports                        → report registry
GET /api/v1/reports/summary               → report staging stats
GET /api/v1/reports/{slug}                → run report
GET /api/v1/reports/{slug}/metadata       → report schema/params
GET /api/v1/reports/sales-recap           → paginated sales recap
GET /api/v1/reports/sales-recap-detail    → raw POS lines
```

### COGS
```
GET /api/v1/cogs-ratio                    → COGS for all branches (default: current month)
GET /api/v1/cogs-ratio?period=YYYY-MM    → specific period
GET /api/v1/cogs-ratio/trend              → multi-period trend
GET /api/v1/cogs-ratio/{branch_id}        → branch-specific
GET /api/v1/cogs-ratio/periods            → available periods
```

### Master Data
```
GET /api/v1/master/summary                → master data counts per entity
GET /api/v1/master/{entity}/rows         → paginated rows (product-uoms, bom-materials…)
GET /api/v1/master/product-uoms           → product variant rows
GET /api/v1/master/bom-materials          → BOM material line rows
```

### Stock & Waste
```
GET /api/v1/stock-opname                  → list opname records
GET /api/v1/stock-opname/summary          → KPI summary
GET /api/v1/stock-opname/pending-count    → pending count
GET /api/v1/waste                         → list waste records
GET /api/v1/waste/summary                → waste KPIs
GET /api/v1/stock/system                  → product × branch matrix
```

### Internal Admin
```
GET/POST/PUT/DELETE /api/v1/internal/employees[/{id}]
POST/DELETE        /api/v1/internal/employees/{id}/shifts[/{sid}]
POST/DELETE        /api/v1/internal/employees/{id}/deductions[/{did}]
GET/POST/PUT/DELETE /api/v1/internal/users[/{id}]
GET                /api/v1/internal/roles
GET                /api/v1/internal/permissions
PUT                /api/v1/internal/roles/{id}/permissions
```

---

## 15. Environment Variables

```env
# Database
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.hpbmalkmorjwvfrxgszl.supabase.co:5432/postgres

# Redis
REDIS_URL=redis://localhost:6379/0

# ESB API
ESB_CORE_URL=https://services.esb.co.id/core
ESB_CORE_USERNAME=CALFSUPERADMINOPS
ESB_CORE_PASSWORD=[password]

# Supabase
SUPABASE_URL=https://hpbmalkmorjwvfrxgszl.supabase.co
SUPABASE_SECRET_KEY=[secret_key]
SUPABASE_PUBLISHABLE_KEY=[publishable_key]

# Supabase Storage (for exports)
SUPABASE_STORAGE_BUCKET=report-exports

# Operational Window Override
ALLOW_OUTSIDE_WINDOW=0   # Set to 1 to bypass 03:00-08:00 WIB gate

# Circuit Breaker
CIRCUIT_BREAKER_THRESHOLD=3
CIRCUIT_BREAKER_RESET_TIMEOUT=60
```

---

## 16. Docker Deployment (VPS: 187.52.114.14)

### Services on VPS
- **Backend API:** FastAPI + Uvicorn (port 8000)
- **Celery Worker:** 4 parallel processes (`-c 4`)
- **Celery Beat:** Periodic scheduler
- **Redis:** Message broker + caching
- **PostgreSQL:** Managed by Supabase (external)

### Health Check
```
GET /health → { "status": "ok", "service": "calf-backend" }
```

### Accessing Supabase PostgreSQL
```bash
# Via psql (direct connection)
psql "postgresql://postgres:Kopicalf2019#@db.hpbmalkmorjwvfrxgszl.supabase.co:5432/postgres"

# Via Supabase Session Pooler (recommended for apps)
psql "postgresql://postgres.hpbmalkmorjwvfrxgszl:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
```

---

## 17. Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker (all queues)
celery -A app.core.worker worker -l INFO -c 4 -Q queue_master,queue_sync,queue_backfill,queue_report,queue_export

# Run Celery beat (periodic tasks)
celery -A app.core.worker beat -l INFO

# Run with Flower monitoring
celery -A app.core.worker flower --port=5555

# Run tests (if exists)
pytest
```

---

## 18. Known Limitations & Notes

1. **Inline Migrations:** Schema managed via `CREATE TABLE IF NOT EXISTS` in `app/core/migrations.py` — no Alembic. Run on startup.

2. **Row Hash Deduplication:** TRX staging uses `MD5(company+entity+doc_num+doc_date)` as idempotency key. Duplicate ESB records are silently deduplicated.

3. **Surrogate Keys:** Pending documents (no `doc_num`) use hash of `(doc_date+product+branch+amount)` as surrogate, preventing true duplicate detection for pending docs.

4. **Watermark Gap:** Lane B delta sync relies on `last_synced_at` per entity per company. If gap > 7 days and record_count is low, `completeness_audit` flags it INCOMPLETE.

5. **Supabase Storage:** `report-exports` bucket is private. Export signed URLs expire after 24 hours.

6. **8 Companies:** IDs 1–8 hardcoded in report layer. `company_configs.is_active` gates which companies sync.

7. **ESB Pagination:** `PAGE_SIZE = 100` (safe; `limit=10000` triggers Validation Error on some endpoints).

8. **No Alembic:** Schema changes must be applied manually via `migrations.py` or direct SQL. Plan to migrate to Alembic for production stability.
