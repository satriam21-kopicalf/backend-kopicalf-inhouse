# Backend Project Analysis Documentation

**Project:** `backend-kopicalf-inhouse`
**Last Updated:** 2026-09-16
**Stack:** FastAPI · PostgreSQL (Supabase) · Redis · Celery · XlsxWriter · psycopg2

---

## 1. Project Overview

Enterprise integration hub for Kopi Calf. Syncs transactional data from ESB POS/ERP API, normalizes master data, computes COGS, and exposes reporting endpoints to the Next.js frontend.

**Backend URL:** `http://localhost:8000` (dev) · `http://187.52.114.14:8000` (VPS)

---

## 2. Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| API Framework | FastAPI | REST endpoints |
| Database | PostgreSQL (Supabase) | esb_data + public schemas |
| Connection Pool | psycopg2 ThreadedConnectionPool | DB access (min 2, max 20) |
| Cache | Redis | Session, lock, TTL cache |
| Task Queue | Celery + Beat | Background sync tasks |
| Export | XlsxWriter | Async XLSX generation |
| HTTP Client | httpx | ESB API calls |

---

## 3. Project Structure

```
backend-kopicalf-inhouse/
├── app/
│   ├── main.py                  # FastAPI app, CORS, lifespan
│   ├── core/
│   │   ├── db.py               # psycopg2 pool, RealDictCursor
│   │   ├── config.py           # Pydantic BaseSettings
│   │   └── worker.py           # Celery app, beat schedule
│   ├── routers/
│   │   ├── auth.py             # /auth/* endpoints
│   │   ├── reports.py          # /reports/* endpoints
│   │   ├── sales.py            # /sales/* endpoints
│   │   ├── cogs.py             # /cogs-ratio endpoint
│   │   ├── master.py           # /master/* endpoints
│   │   ├── stock.py            # /stock/* endpoints
│   │   ├── waste.py            # /waste/* endpoints
│   │   └── internal_admin.py    # /internal/* CRUD
│   ├── services/
│   │   ├── trx_engine.py       # Dual-lane TRX sync
│   │   ├── tasks.py            # Celery tasks, ESBClient
│   │   ├── master_sync.py      # Master data sync
│   │   ├── reports.py          # Report registry (30+ reports)
│   │   ├── export_engine.py    # XLSX generation
│   │   ├── aggregation.py      # Data aggregation
│   │   └── operational_window.py # 03:00-08:00 WIB gate
│   └── utils/
│       └── cogs_calculator.py   # COGS with 65% estimation
├── docs/
│   ├── audit_final.py          # Data comparison (final)
│   ├── audit_compare.py        # Data comparison (interim)
│   └── ESB_ANALYSIS_INFRASTRUCTURE.md
├── migrations/                  # SQL schema (backup)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## 4. Database Schema

### Connection
```python
from app.core.db import get_db_connection
conn = get_db_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)
```

### Schemas

**`internal`** — Authentication & RBAC
```
users, roles, permissions, role_permissions,
employees, employee_shifts, employee_deductions
```

**`esb_data`** — Master data normalized from ESB
```
master_branch, master_product, master_product_detail,
master_category, master_supplier, master_customer,
master_bill_of_material, master_bom_material,
master_pricelist, master_unit, master_sub_category,
master_customer_category, master_supplier_category,
master_customer_pricelist, master_purpose,
master_cost_center, master_charts_of_account,
master_project, master_user, master_document_template,
master_tax, master_cashflow_category, master_approval_flow,
endpoint_registry, sync_schedules, company_configs
```

**`public`** — Transactional staging & reports
```
esb_raw_staging, trx_raw_staging, report_raw_staging,
sync_history, dlq_logs, stock_opname, waste
```

---

## 5. ESB API Integration

### Base Configuration
```
ESB_CORE_URL = https://services.esb.co.id/core
ESB_FALLBACK_USERNAME = CALFSUPERADMINOPS
```

### Auth Flow (per company)
1. `POST /auth/login` → base JWT
2. `POST /auth/login/company` with base JWT + companyCode → scoped JWT
3. Scoped JWT used for all subsequent requests

### Circuit Breaker
- Class: `ESBCircuitBreaker` (closed/open/half-open)
- Threshold: 3 failures → OPEN
- Reset timeout: 60 seconds → HALF_OPEN
- Test request on half-open → CLOSED or re-OPEN

### Redis Lock
- Lock key: `esb_auth_lock:<company_code>`
- TTL: 30 seconds
- Prevents concurrent logins invalidating each other's base JWT

---

## 6. Sync Engine

### Dual-Lane TRX Sync (`trx_engine.py`)

**Lane 1: Backfill**
- Historical date range sync
- Parallel fan-out per date
- Page-overlap guard (100+ pages = warning)

**Lane 2: Delta + Realtime**
- `last_sync_time` based delta
- Realtime polling on configured interval

### Key Features
- `row_hash` deduplication key: `(company_id, entity_type, doc_num, doc_date, branch_esb_id, product_esb_id)`
- `qty` grouped on duplicate rows
- Upsert logic per entity type

### Row Hash Mapping
```python
'PRODUCT_SALES': ('company_id', 'entity_type', 'doc_num', 'doc_date',
                  'branch_esb_id', 'product_esb_id'),
'PURCHASE_INVOICE': ('company_id', 'entity_type', 'doc_num', 'doc_date',
                     'branch_esb_id', 'product_esb_id'),
'STOCK_OPNAME': ('company_id', 'entity_type', 'doc_num', 'doc_date',
                 'branch_esb_id', 'product_esb_id'),
'WASTE': ('company_id', 'entity_type', 'doc_num', 'doc_date',
          'branch_esb_id', 'product_esb_id'),
```

---

## 7. Sync Status (2026-09-16)

### POS Sales Sync — ✅ SUCCESS
| Metric | Value |
|--------|-------|
| Total Records | 611,829 |
| report_pos_sales rows | 2,583,064 |
| DLQ Entries | 0 |
| Last Sync | 2026-09-15 |

### Master Data — ✅ COMPLETE
| Entity | Status | Records |
|--------|--------|---------|
| master_branch | ✅ Synced | ~25 outlets |
| master_product | ✅ Synced | ~350 products |
| master_bill_of_material | ✅ Synced | 2368 material lines |
| master_bom_material | ✅ Implemented | BOM line items |
| master_category | ✅ Synced | Categories |
| master_supplier | ✅ Synced | Suppliers |
| master_customer | ✅ Synced | Customers |

### Failed/Not Synced Entities
| Entity | Status | Notes |
|--------|--------|-------|
| TRX_ITEM_JOURNAL | ❌ Failed | POS journal detail |
| TRX_PURCHASE_INVOICE | ❌ Failed | Purchase transactions |
| TRX_STOCK_OPNAME | ❌ Failed | Stock opname entries |
| TRX_WASTE | ❌ Failed | Waste transactions |
| TRX_SALES_RETURN | ❌ Failed | Sales returns |

---

## 8. Data Comparison (2026-08-01 to 2026-09-13)

### Audit Results (`audit_final.py`)
- **Excel files analyzed:** 35 dates
- **Missing dates:** 0
- **Excess dates:** 0
- **Row grouping effect:** 3-6% (expected, by design)
  - ERP export contains ALL raw lines including duplicate identical menu items
  - DB pipeline groups (merges) identical items within same order by summing qty

### Validation Summary
| Metric | Excel Total | API/DB Total | Diff |
|--------|-------------|--------------|------|
| Total Lines | ~1.9M | ~1.85M | -3.2% |

### Key Findings
- ✅ NO missing data — all 35 sample dates have matching DB records
- ✅ NO duplicates/excess — all dates have FEWER DB rows (grouping effect)
- ✅ Nett sales totals within 3% tolerance
- ⚠️ Aug 27 backfill completed (56,448 lines synced)

---

## 9. API Endpoints

### Authentication
```
POST /auth/login              # User login
POST /auth/logout             # User logout
GET  /auth/me                 # Current user
```

### Reports
```
GET  /reports                          # List reports
GET  /reports/{slug}                   # Report data
GET  /reports/{slug}/metadata          # Report metadata
```

### Sales
```
GET  /sales/recap                      # Sales summary
GET  /sales/recap-detail              # Detailed sales (date range)
     ?start_date=YYYY-MM-DD
     &end_date=YYYY-MM-DD
     &branch_id=optional
```

### COGS
```
GET  /cogs-ratio                       # COGS ratio analysis
     ?period=YYYY-MM
     &trend=optional
     &per_branch=optional
```

### Master Data
```
GET  /master/{entity}/rows            # Entity rows (product, branch, etc.)
GET  /master/summary                   # Master data summary
GET  /master/bom-materials            # Bill of materials
```

### Stock & Waste
```
GET  /stock/system                    # System stock
GET  /stock-opname                    # Stock opname
GET  /stock-opname/summary           # Opname summary
GET  /waste                          # Waste data
GET  /waste/summary                 # Waste summary
```

### Internal Admin
```
GET/POST/PUT/DELETE /internal/employees
GET/POST/PUT/DELETE /internal/users
GET/POST/PUT/DELETE /internal/roles
```

---

## 10. Celery Tasks

### Beat Schedule (8 Periodic Tasks)
```
sync_master_data          # Master data sync
sync_pos_sales            # POS sales sync
sync_daily_delta          # Daily delta sync
sync_realtime             # Realtime sync
export_report             # Async export
sync_aggregations         # Aggregation refresh
cleanup_dlq               # DLQ cleanup
health_check              # System health
```

### Operational Window
- All sync tasks gated: **03:00 - 08:00 WIB**
- Prevents conflicts during business hours

---

## 11. Docker Services

Running on VPS `187.52.114.14`:
```
backend-kopicalf-inhouse-backend-1    ✅ running
backend-kopicalf-inhouse-redis-1      ✅ running
backend-kopicalf-inhouse-celery-1     ✅ running
backend-kopicalf-inhouse-celery-beat-1 ✅ running
nginx-proxy                          ✅ running
certbot                              ✅ running
```

---

## 12. Known Issues & Roadmap

### Completed
- [x] POS sales pipeline rebuilt (row_hash dedup, grouped qty, parallel backfill)
- [x] master_bom_material implemented (2368 material lines)
- [x] COGS ratio endpoint implemented (65% estimation fallback)
- [x] Unused tables dropped (18 tables)
- [x] Aug 27 backfill completed
- [x] DLQ cleared (0 entries)

### In Progress
- [ ] TRX_ITEM_JOURNAL sync repair
- [ ] TRX_PURCHASE_INVOICE sync repair
- [ ] TRX_STOCK_OPNAME sync repair
- [ ] TRX_WASTE sync repair
- [ ] Real-time sales aggregation (need operational outlet data)

### Recommended
1. **Sales Return Tracking** — Implement TRX_SALES_RETURN sync
2. **COGS Improvement** — Replace 65% estimation with actual BOM-based calculation
3. **Outlet Operational Data** — Wire frontend to operational forms
4. **Dashboard KPIs** — Connect dashboard to actual API data
5. **Export Engine** — Complete async XLSX generation

---

## 13. VPS Access

```
Host: 187.52.114.14
User: root
Pass: Kopicalf2019#
SSH Port: 22

Database (via container):
  Host: db.hpbmalkmorjwvfrxgszl.supabase.co
  Port: 5432
  User: postgres
  Pooler: port 6543 (via container)
```

---

## 14. Related Documentation

- `docs/ESB_ANALYSIS_INFRASTRUCTURE.md` — Gap matrix, bug fixes, roadmap
- `docs/ESB_API_ENDPOINT_BREAKDOWN.md` — API endpoint details
- `docs/audit_final.py` — Data comparison script
- `docs/audit_compare.py` — Interim comparison script
