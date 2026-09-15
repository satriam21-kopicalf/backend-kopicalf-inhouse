# ESB API - Complete Endpoint Breakdown

**Document Version:** 1.1.0
**Last Updated:** September 2026 (v1.1: added engine sync-coverage cross-reference)
**Sources:** ESB Core API (developers.esb.co.id/esb-core/), ESB OMS API (developers.esb.co.id/esb-oms/)
**Base URLs:**
- Production: `https://services.esb.co.id/`
- Staging INT: `https://stg7.esb.co.id/core-int`
- Staging: `https://stg7.esb.co.id/core-stg`

---

## 0. Engine Sync Coverage (actual backend consumption) — v1.1

The "Already Synced" statuses in the tables below reflect **endpoint
availability in the API spec**, not what the backend consumes. The backend
(`app/services/tasks.py`, `trx_engine.py`, `reports.py`) actually consumes:

| Lane | Source | What the engine pulls |
|---|---|---|
| Master data | ESB Core | `/product/category`, `/product/sub-category`, `/units`, `/product/list`, `/product/{id}` (productDetails → `master_product_detail`), `/product/bom` + `/product/bom/{bomID}` (bomDetails → `master_bom_material`), `/supplier`, `/customer/list`, `/pricelist`, `/branch`, `/location` |
| Master data (OMS) | ESB OMS | `/external/general/get-menu`, `/external/general/get-branch`, `/external/general/get-payment-method`, `/external/general/get-visit-purpose`, `/external/general/stock-branch` |
| Transactions (index+view) | ESB Core | `TRX_INDEX_VIEW` in `trx_engine.py`: STOCK_OPNAME, PURCHASE_ORDER, PURCHASE_REQUEST, GOODS_RECEIPT, GOODS_DELIVERY, RECEIPT, MEMORIAL_JOURNAL, ADVANCE_SALES, SIMPLE_MANUFACTURING, DISBURSEMENT, PRODUCT_SALES, SALES_PAYMENT, PRODUCT_SALES_ACTUATION, AR_SUSPENSE, AP_SUSPENSE, EMPLOYEE_ADVANCE, BUDGET_DETAIL, BUDGET_REVISION, PURCHASE_INVOICE, PURCHASE_INVOICE_PAYMENT, PURCHASE_RETURN, GOODS_RECEIPT_RETURN, GOODS_DELIVERY_RETURN, BILL_OF_MATERIAL, ADVANCE_RECAP, ITEM_JOURNAL, PURCHASE_ORDER_ACTUATION (+ more) → `public.trx_raw_staging` |
| Direct reports | ESB Core | `RPT_DIRECT`: `/report/stock-movement` (T-7), `/report/sales-payment-summary` (T-2), `/report/goods-receipt-recapitulation` (T-2) → `public.report_raw_staging` |
| POS sales (OMS) | ESB OMS | `/external/general/sales-head` + `/external/general/sales-menu` → `esb_data.report_pos_sales_head` / `esb_data.report_pos_sales` (grouped, row_hash-keyed; void-aware; audited vs API per day) |

Known dead endpoints removed from the engine 2026-09-14 (404 since 2026-09-08):
`RPT_MENU_COGS`, `RPT_PURCHASE_RECAPITULATION` (report-shaped endpoints that no
longer resolve on production).

---

## Overview

This document provides a comprehensive breakdown of all available endpoints across ESB Core and ESB OMS APIs, organized by functional category.

| Category | Description | Source | Endpoint Count |
|----------|-------------|--------|----------------|
| **Category A** | Master Data (Read / Consume) | ESB Core + ESB OMS | ~113 endpoints |
| **Category B** | Transaction Operations (Write) | ESB Core | ~245 endpoints |
| **Category C** | Reports | ESB Core | 1 endpoint |
| **Authentication** | Login & Token Management | ESB Core + ESB OMS | 4 endpoints |
| **Other** | Uncategorized/External | Mixed | 7 endpoints |
| **Total** | All Endpoints | Combined | **401 endpoints** |

### Status Legend

| Symbol | Meaning |
|--------|---------|
| :white_check_mark: Already Synced | Endpoint is live and available for integration |
| :sparkles: New Opportunity | Endpoint exists in API but not yet in endpoint registry |
| :warning: Gap | Required by scope but no API equivalent exists |

### Priority Legend

| Priority | Description |
|----------|-------------|
| **P0** | Critical - must be implemented first; core business operations |
| **P1** | High - important for primary workflows |
| **P2** | Medium - needed for complete coverage but not blocking |
| **Restricted** | Not available via API - manual processing required |

---

## 1. Authentication (4 endpoints)

All API endpoints require Bearer token authentication obtained through the Login endpoint. Access tokens expire after 1 hour; refresh tokens expire after 24 hours.

### ESB Core - Authorization

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/auth/login` | Login | :white_check_mark: Already Synced |
| `GET` | `/auth/refresh` | Refresh Token | :white_check_mark: Already Synced |

### ESB OMS - Authorization

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/auth/login` | Login | :white_check_mark: Already Synced |
| `GET` | `/auth/refresh` | Refresh Token | :white_check_mark: Already Synced |

---

## 2. Category A - Master Data (Read / Consume)

Master data endpoints provide read-only access to reference data that is maintained in ESB Core. These endpoints are used to synchronize foundational data into the POS/OMS system.

### A1. Product Domain (ESB Core)

#### Product Category (2 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/product/category/{categoryID}` | Category Detail | :white_check_mark: Already Synced |
| `GET` | `/product/category` | Category List | :white_check_mark: Already Synced |

#### Product Sub-Category (2 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/product/sub-category/{subCategoryID}` | Sub Category Detail | :white_check_mark: Already Synced |
| `GET` | `/product/sub-category` | Sub Category List | :white_check_mark: Already Synced |

#### Unit of Measure (2 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/units/{uomID}` | Unit Detail | :white_check_mark: Already Synced |
| `GET` | `/units` | Unit List | :white_check_mark: Already Synced |

#### Product - General (59 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/product/authorize` | Authorize Product | :white_check_mark: Already Synced |
| `GET` | `/product/browse-category` | Browse Category | :white_check_mark: Already Synced |
| `GET` | `/product/browse-sub-category` | Browse Sub Category | :white_check_mark: Already Synced |
| `POST` | `/product` | Create Product | :white_check_mark: Already Synced |
| `DELETE` | `/product/:productID/temp` | Delete Pending Product | :white_check_mark: Already Synced |
| `DELETE` | `/product/:productID` | Delete Product | :white_check_mark: Already Synced |
| `POST` | `/product/export/temp` | Export Pending Product | :white_check_mark: Already Synced |
| `POST` | `/product/export` | Export Product | :white_check_mark: Already Synced |
| `POST` | `/product/export-template` | Export Product Template | :white_check_mark: Already Synced |
| `GET` | `/product/{productID}` | Product Detail | :white_check_mark: Already Synced |
| `GET` | `/product` | Product Index | :white_check_mark: Already Synced |
| `GET` | `/product/list` | Product List | :white_check_mark: Already Synced |
| `GET` | `/product/:productID/temp` | Product Pending Detail | :white_check_mark: Already Synced |
| `GET` | `/product/temp` | Product Pending Index | :white_check_mark: Already Synced |
| `PUT` | `/product/pull` | Pull Product | :white_check_mark: Already Synced |
| `PUT` | `/product/push` | Push Product | :white_check_mark: Already Synced |
| `PATCH` | `/product/reject` | Reject Product | :white_check_mark: Already Synced |
| `PATCH` | `/product/:productID/restore` | Restore Product | :white_check_mark: Already Synced |
| `PUT` | `/product/:productID` | Update Product | :white_check_mark: Already Synced |
| `POST` | `/product/import` | Upload Create Product | :white_check_mark: Already Synced |
| `PUT` | `/product/import` | Upload Update Product | :white_check_mark: Already Synced |
| `GET` | `/product/validate-barcode-number` | Validate Barcode Number | :white_check_mark: Already Synced |
| `GET` | `/product/:productID/validate-delete` | Validate Delete Product | :white_check_mark: Already Synced |
| `GET` | `/product/detail/validate-delete` | Validate Delete Product Detail | :white_check_mark: Already Synced |
| `PATCH` | `/production/material-delivery/{materialDeliveryNum}/authorize` | Authorize Material Delivery | :white_check_mark: Already Synced |
| `POST` | `/production/material-delivery` | Create Material Delivery | :white_check_mark: Already Synced |
| `DELETE` | `/production/material-delivery/{materialDeliveryNum}` | Delete Material Delivery | :white_check_mark: Already Synced |
| `GET` | `/production/material-delivery` | Material Delivery Index | :white_check_mark: Already Synced |
| `PATCH` | `/production/material-delivery/{materialDeliveryNum}/reject` | Reject Material Delivery | :white_check_mark: Already Synced |
| `PUT` | `/production/material-delivery/{materialDeliveryNum}` | Update Material Delivery | :white_check_mark: Already Synced |
| `GET` | `/production/material-delivery/{materialDeliveryNum}` | View Material Delivery | :white_check_mark: Already Synced |
| `PATCH` | `/production/production-order/{productionOrderNum}/authorize` | Authorize Production Order | :white_check_mark: Already Synced |
| `POST` | `/production/production-order` | Create Production Order | :white_check_mark: Already Synced |
| `DELETE` | `/production/production-order/{productionOrderNum}` | Delete Production Order | :white_check_mark: Already Synced |
| `GET` | `/production/production-order` | Production Order Index | :white_check_mark: Already Synced |
| `PATCH` | `/production/production-order/{productionOrderNum}/reject` | Reject Production Order | :white_check_mark: Already Synced |
| `PUT` | `/production/production-order/{productionOrderNum}` | Update Production Order | :white_check_mark: Already Synced |
| `GET` | `/production/production-order/{productionOrderNum}` | View Production Order | :white_check_mark: Already Synced |
| `PATCH` | `/production/production-result/{productionResultNum}/authorize` | Authorize Production Result | :white_check_mark: Already Synced |
| `POST` | `/production/production-result` | Create Production Result | :white_check_mark: Already Synced |
| `DELETE` | `/production/production-result/{productionResultNum}` | Delete Production Result | :white_check_mark: Already Synced |
| `GET` | `/production/production-result` | Production Result Index | :white_check_mark: Already Synced |
| `PATCH` | `/production/production-result/{productionResultNum}/reject` | Reject Production Result | :white_check_mark: Already Synced |
| `PUT` | `/production/production-result/{productionResultNum}` | Update Production Result | :white_check_mark: Already Synced |
| `GET` | `/production/production-result/{productionResultNum}` | View Production Result | :white_check_mark: Already Synced |
| `PATCH` | `/production/simple-manufacturing/{simpleManufacturingNum}/authorize` | Authorize Simple Manufacturing | :white_check_mark: Already Synced |
| `POST` | `/production/simple-manufacturing/assembly-actual` | Create Simple Manufacturing Assembly Actual Costing | :white_check_mark: Already Synced |
| `POST` | `/production/simple-manufacturing/assembly` | Create Simple Manufacturing Assembly Standard Costing | :white_check_mark: Already Synced |
| `POST` | `/production/simple-manufacturing/disassembly-actual` | Create Simple Manufacturing Disassembly Actual Costing | :white_check_mark: Already Synced |
| `POST` | `/production/simple-manufacturing/disassembly` | Create Simple Manufacturing Disassembly Standard Costing | :white_check_mark: Already Synced |
| `DELETE` | `/production/simple-manufacturing/{simpleManufacturingNum}` | Delete Simple Manufacturing | :white_check_mark: Already Synced |
| `PATCH` | `/production/simple-manufacturing/{simpleManufacturingNum}/reject` | Reject Simple Manufacturing | :white_check_mark: Already Synced |
| `GET` | `/production/simple-manufacturing` | Simple Manufacturing Index | :white_check_mark: Already Synced |
| `PUT` | `/production/simple-manufacturing/assembly-actual/{simpleManufacturingNum}` | Update Simple Manufacturing Assembly Actual Costing | :white_check_mark: Already Synced |
| `PUT` | `/production/simple-manufacturing/disassembly-actual/{simpleManufacturingNum}` | Update Simple Manufacturing Disassembly Actual Costing | :white_check_mark: Already Synced |
| `PUT` | `/production/simple-manufacturing/disassembly/{simpleManufacturingNum}` | Update Simple Manufacturing Disassembly Standard Costing | :white_check_mark: Already Synced |
| `PUT` | `/production/simple-manufacturing/assembly/{simpleManufacturingNum}` | Update Simple Manufacturing Assembly Standard Costing | :white_check_mark: Already Synced |
| `POST` | `/production/simple-manufacturing/upload` | Upload Simple Manufacturing | :white_check_mark: Already Synced |
| `GET` | `/production/simple-manufacturing/{simpleManufacturingNum}` | View Simple Manufacturing | :white_check_mark: Already Synced |

#### Bill of Material (14 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/product/bom/browse` | Bill of Material Browse | :white_check_mark: Already Synced |
| `GET` | `/product/bom/{bomID}` | Bill of Material Detail | :white_check_mark: Already Synced |
| `GET` | `/product/bom/export` | Bill of Material Export | :white_check_mark: Already Synced |
| `GET` | `/product/bom/export` | Bill of Material Export Template | :white_check_mark: Already Synced |
| `GET` | `/product/bom` | Bill of Material List | :white_check_mark: Already Synced |
| `GET` | `/product/stock-location` | Browse Stock Location | :white_check_mark: Already Synced |
| `POST` | `/product/bom` | Create Bill of Material Assembly | :white_check_mark: Already Synced |
| `POST` | `/product/bom` | Create Bill of Material Disassembly | :white_check_mark: Already Synced |
| `POST` | `/product/bom` | Create Bill of Material Menu | :white_check_mark: Already Synced |
| `DELETE` | `/product/bom/{bomID}` | Delete Bill of Material | :white_check_mark: Already Synced |
| `PATCH` | `/product/bom/{bomID}/restore` | Restore Bill of Material | :white_check_mark: Already Synced |
| `PUT` | `/product/bom/{bomID}` | Update Bill of Material | :white_check_mark: Already Synced |
| `POST` | `/product/bom/upload` | Upload Bill of Material | :white_check_mark: Already Synced |
| `POST` | `/product/bom/upload/template` | Upload Update Bill of Material | :white_check_mark: Already Synced |

### A2. Partner Domain (ESB Core)

#### Supplier (11 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/supplier` | Create Supplier | :white_check_mark: Already Synced |
| `DELETE` | `/supplier/{supplierID}` | Delete Supplier | :white_check_mark: Already Synced |
| `GET` | `/supplier/export/BANK` | Export Supplier | :white_check_mark: Already Synced |
| `PATCH` | `/supplier/{supplierID}/restore` | Restore Supplier | :white_check_mark: Already Synced |
| `GET` | `/supplier/category/list` | Supplier Category List | :white_check_mark: Already Synced |
| `GET` | `/supplier/{supplierID}` | Supplier Detail | :white_check_mark: Already Synced |
| `GET` | `/supplier` | Supplier List | :white_check_mark: Already Synced |
| `PATCH` | `/supplier/{supplierID}` | Update Supplier | :white_check_mark: Already Synced |
| `POST` | `/supplier/upload` | Upload Supplier | :white_check_mark: Already Synced |
| `PATCH` | `/supplier/upload` | Upload Update Supplier | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/supplier-invoice/availability` | Check Supplier Invoice Number Availability | :white_check_mark: Already Synced |

#### Customer (10 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/customer` | Create Customer | :white_check_mark: Already Synced |
| `GET` | `/customer/{customerID}` | View Customer | :white_check_mark: Already Synced |
| `GET` | `/customer/list` | Customer Find All | :white_check_mark: Already Synced |
| `GET` | `/customer` | Customer Index | :white_check_mark: Already Synced |
| `DELETE` | `/customer/{customerID}` | Delete Customer | :white_check_mark: Already Synced |
| `GET` | `/customer/export` | Export Customer | :white_check_mark: Already Synced |
| `PATCH` | `/customer/{customerID}/restore` | Restore Customer | :white_check_mark: Already Synced |
| `PUT` | `/customer/{customerID}` | Update Customer | :white_check_mark: Already Synced |
| `POST` | `/customer/upload` | Upload Customer | :white_check_mark: Already Synced |
| `POST` | `/customer/{customerID}/validation-before-delete` | Customer Validation Before Delete | :white_check_mark: Already Synced |

#### Customer Pricelist (21 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/customer-pricelist` | Create Customer Pricelist | :white_check_mark: Already Synced |
| `GET` | `/customer-pricelist` | Customer Pricelist Index | :white_check_mark: Already Synced |
| `DELETE` | `/customer-pricelist/:customerPricelistID` | Delete Customer Pricelist | :white_check_mark: Already Synced |
| `GET` | `/customer-pricelist/export` | Export Customer Pricelist | :white_check_mark: Already Synced |
| `PATCH` | `/customer-pricelist/:customerPricelistID` | Update Customer Pricelist | :white_check_mark: Already Synced |
| `POST` | `/customer-pricelist/import` | Upload Customer Pricelist | :white_check_mark: Already Synced |
| `GET` | `/customer-pricelist/:customerPricelistID` | View Customer Pricelist | :white_check_mark: Already Synced |
| `PATCH` | `/pricelist/temp/:pricelistNum/authorize` | Authorize Waiting For Approval Pricelist | :white_check_mark: Already Synced |
| `POST` | `/pricelist` | Create Pricelist | :white_check_mark: Already Synced |
| `DELETE` | `/pricelist/:pricelistID` | Delete Pricelist | :white_check_mark: Already Synced |
| `DELETE` | `/pricelist/temp/:pricelistNum` | Delete Waiting For Approval Pricelist | :white_check_mark: Already Synced |
| `GET` | `/pricelist/export` | Export Pricelist | :white_check_mark: Already Synced |
| `GET` | `/pricelist/temp/export` | Export Waiting For Approval Pricelist | :white_check_mark: Already Synced |
| `GET` | `/pricelist` | Pricelist Index | :white_check_mark: Already Synced |
| `PATCH` | `/pricelist/temp/:pricelistNum/reject` | Reject Waiting For Approval Pricelist | :white_check_mark: Already Synced |
| `PUT` | `/pricelist/:pricelistID` | Update Pricelist | :white_check_mark: Already Synced |
| `PUT` | `/pricelist/temp/:pricelistNum` | Update Waiting For Approval Pricelist | :white_check_mark: Already Synced |
| `POST` | `/pricelist/import` | Upload Pricelist | :white_check_mark: Already Synced |
| `GET` | `/pricelist/:pricelistID` | View Pricelist | :white_check_mark: Already Synced |
| `GET` | `/pricelist/temp/:pricelistNum` | View Waiting For Approval Pricelist | :white_check_mark: Already Synced |
| `GET` | `/pricelist/temp` | Waiting For Approval Pricelist Index | :white_check_mark: Already Synced |

### A3. Company Domain (ESB Core)

#### Branch & Location (7 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/budget-plan/:budgetPlanNum/branches` | Get Budget Plan Branches | :white_check_mark: Already Synced |
| `GET` | `/budget-plan/:budgetPlanNum/branches/details` | Get Budget Plan Detail by Branch | :white_check_mark: Already Synced |
| `GET` | `/branch` | Branch List | :white_check_mark: Already Synced |
| `GET` | `/location/{locationID}` | Location Detail | :white_check_mark: Already Synced |
| `GET` | `/location` | Location List | :white_check_mark: Already Synced |
| `GET` | `/branch/user` | User Access List | :white_check_mark: Already Synced |
| `GET` | `/location/user` | User Access Location | :white_check_mark: Already Synced |

#### Document Template (2 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/document-template/[requestTemplateID]` | Document Template Detail | :white_check_mark: Already Synced |
| `GET` | `/document-template` | Document Template List | :white_check_mark: Already Synced |

### A4. Accounting Domain (ESB Core)

#### Purpose (2 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/purpose/[purposeID]` | Purpose Detail | :white_check_mark: Already Synced |
| `GET` | `/purpose` | Purpose List | :white_check_mark: Already Synced |

#### Cost Center (2 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/cost-center` | Cost Center Index | :white_check_mark: Already Synced |
| `GET` | `//cost-center/user` | User Cost Center | :white_check_mark: Already Synced |

### A6. POS / OMS Domain (ESB OMS)

#### Member (1 endpoint)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/extv1/member` | Get Member | :white_check_mark: Already Synced |

#### Menu Category (3 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/corev1/master/create-menu-category` | Create Menu Category | :white_check_mark: Already Synced |
| `GET` | `/corev1/master/get-menu-category` | Get Menu Category | :white_check_mark: Already Synced |
| `POST` | `/corev1/master/update-menu-category` | Update Menu Category | :white_check_mark: Already Synced |

#### Menu Template (3 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/corev1/master/create-menu-template` | Create Menu Template | :white_check_mark: Already Synced |
| `GET` | `/corev1/master/get-menu-template?page=1` | Get Menu Template | :white_check_mark: Already Synced |
| `POST` | `/corev1/master/update-menu-template` | Update Menu Template | :white_check_mark: Already Synced |

#### Menu (3 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/corev1/master/create-menu` | Create Menu | :white_check_mark: Already Synced |
| `GET` | `/corev1/master/get-menu` | Get Menu | :white_check_mark: Already Synced |
| `POST` | `/web/corev1/master/update-menu` | Update Menu | :white_check_mark: Already Synced |

#### Promotion (6 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/corev1/promotion/` | Discount (RP) ESO | :white_check_mark: Already Synced |
| `POST` | `/corev1/promotion/` | Discount Limit (%) | :white_check_mark: Already Synced |
| `POST` | `/corev1/promotion/` | Discount (%) | :white_check_mark: Already Synced |
| `POST` | `/corev1/promotion/` | Discount (%) ESO | :white_check_mark: Already Synced |
| `POST` | `/corev1/promotion/` | Free Item | :white_check_mark: Already Synced |
| `GET` | `/extv1/promotion` | Promotion List | :white_check_mark: Already Synced |

#### POS General (1 endpoint)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/external/general/stock-branch` | Stock Branch | :white_check_mark: Already Synced |

---

## 3. Category B - Transaction Operations (Write)

Transaction endpoints allow creating, updating, and managing business transactions. These are the operational endpoints that record financial and inventory movements.

### B1. Purchase (ESB Core)

#### Purchase Order (16 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/purchase/purchase-order/{purchaseNum}/authorize` | Authorize Purchase Order | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-order/{purchaseNum}/close` | Close Purchase Order | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-order/draft` | Create Draft Purchase Order | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-order` | Create Purchase Order | :white_check_mark: Already Synced |
| `DELETE` | `/purchase/purchase-order/{purchaseNum}` | Delete Purchase Order | :white_check_mark: Already Synced |
| `GET` | `|` | Flow Purchase Order | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-order/{purchaseNum}/print` | Print Purchase Order | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-order` | Purchase Order Index | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-order/{{purchaseNum}}/reject` | Reject Purchase Order | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-order/{purchaseNum}/unclose` | Unclose Purchase Order | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-order/{purchaseNum}/unfinish` | Unfinish Purchase Order | :white_check_mark: Already Synced |
| `PUT` | `/purchase/purchase-order/{{purchaseNum}}/draft` | Update Draft Purchase Order | :white_check_mark: Already Synced |
| `PUT` | `/purchase/purchase-order/{{purchaseNum}}` | Update Purchase Order | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-order/{purchaseNum}/asset-images` | Upload Asset Image Purchase Order | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-order/upload` | Upload Purchase Order | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-order/{purchaseNum}` | View Purchase Order | :white_check_mark: Already Synced |

#### Purchase Invoice (23 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/purchase/purchase-invoices/:purchaseInvoiceNum/authorize` | Authorize Purchase Invoice | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/browse-data-details` | Browse Data Details | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/browse-data-heads` | Browse Data Heads | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/browse-references` | Browse References | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/browse-return` | Browse Return | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-invoices` | Create Purchase Invoice | :white_check_mark: Already Synced |
| `DELETE` | `/purchase/purchase-invoices/:purchaseInvoiceNum` | Delete Purchase Invoice | :white_check_mark: Already Synced |
| `DELETE` | `/purchase/purchase-invoices/:purchaseInvoiceNum/attachment` | Delete Attachment Purchase Invoice | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-invoices/export-csv` | Export CSV Purchase Invoice | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/:purchaseInvoiceNum/payable-settlements` | Fetch Payable Settlements | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/:purchaseInvoiceNum/purchase-payments` | Fetch Purchase Payments | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/:purchaseInvoiceNum` | Get Data Purchase Invoice | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-invoices/return-details` | Get Purchase Invoice Return Details | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices` | Get All Data Purchase Invoice | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/product-price` | Product Price | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/product-price-history` | Product Price History | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-invoices/:purchaseInvoiceNum/reject` | Reject Purchase Invoice | :white_check_mark: Already Synced |
| `PUT` | `/purchase/purchase-invoices/:purchaseInvoiceNum` | Update Purchase Invoice | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-invoices/:purchaseInvoiceNum/attachment` | Upload Attachment Purchase Invoice | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/:purchaseInvoiceNum/validate-adjustment` | Validate Purchase Invoice Adjustment | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/:purchaseInvoiceNum/validate-payment` | Validate Purchase Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/validate-references-budget` | Validate References Budget | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-invoices/:purchaseInvoiceNum/validate-return` | Validate Purchase Return | :white_check_mark: Already Synced |

#### Purchase Return (7 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/purchases/purchase-return/:purchaseReturnNum/authorize` | Authorize Purchase Return | :white_check_mark: Already Synced |
| `POST` | `/purchases/purchase-return` | Create Purchase Return | :white_check_mark: Already Synced |
| `DELETE` | `/purchases/purchase-return/:purchaseReturnNum` | Delete Purchase Return | :white_check_mark: Already Synced |
| `GET` | `/purchases/purchase-return/:purchaseReturnNum` | Get Data Purchase Return | :white_check_mark: Already Synced |
| `GET` | `/purchases/purchase-return` | Get All Data Purchase Return | :white_check_mark: Already Synced |
| `PATCH` | `/purchases/purchase-return/:purchaseReturnNum/reject` | Reject Purchase Return | :white_check_mark: Already Synced |
| `PUT` | `/purchases/purchase-return/:purchaseReturnNum` | Update Purchase Return | :white_check_mark: Already Synced |

#### Advance Payment (24 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/purchase/advance-payment/:advancePaymentNum/authorize` | Authorize Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment/available-amount` | Get Available Advance Amount Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment/current-settlement-available-amount` | Get Available Advance Amount By Settlement Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment/browse-purchase` | Browse Purchase Reference Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment/browse-reference` | Browse Reference Advance Payment | :white_check_mark: Already Synced |
| `POST` | `/purchase/advance-payment` | Create Advance Payment | :white_check_mark: Already Synced |
| `DELETE` | `/purchase/advance-payment/:advancePaymentNum` | Delete Advance Payment | :white_check_mark: Already Synced |
| `DELETE` | `/purchase/advance-payment/:advancePaymentNum/attachment` | Delete Attachment Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment` | Index Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment/purchase-advance-amount` | Get Purchase Advance Amount Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment/:advancePaymentNum/references` | Get References Advance Payment | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/advance-payment/:advancePaymentNum/reject` | Reject Advance Payment | :white_check_mark: Already Synced |
| `PUT` | `/purchase/advance-payment/:advancePaymentNum` | Update Advance Payment | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/advance-payment/:advancePaymentNum/attachment` | Upload Attachment Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/purchase/advance-payment/:advancePaymentNum` | View Advance Payment | :white_check_mark: Already Synced |
| `PATCH` | `/employee/employee-advance-payment/:employeeAdvanceNum/authorize` | Authorize Employee Advance Payment | :white_check_mark: Already Synced |
| `POST` | `/employee/employee-advance-payment` | Create Employee Advance Payment | :white_check_mark: Already Synced |
| `DELETE` | `/employee/employee-advance-payment/:employeeAdvanceNum` | Delete Employee Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/employee/employee-advance-payment` | Index Employee Advance Payment | :white_check_mark: Already Synced |
| `PATCH` | `/employee/employee-advance-payment/:employeeAdvanceNum/reject` | Reject Employee Advance Payment | :white_check_mark: Already Synced |
| `PUT` | `/employee/employee-advance-payment/:employeeAdvanceNum` | Update Employee Advance Payment | :white_check_mark: Already Synced |
| `POST` | `/employee/employee-advance-payment/upload` | Upload Employee Advance Payment | :white_check_mark: Already Synced |
| `POST` | `/employee/employee-advance-payment/:refNum/asset-images` | Upload Asset Images Employee Advance Payment | :white_check_mark: Already Synced |
| `GET` | `/employee/employee-advance-payment/:employeeAdvanceNum` | View Employee Advance Payment | :white_check_mark: Already Synced |

#### Simple Purchase (8 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/purchase/simple-purchase/{cashPurchaseNum}/authorize` | Authorize Simple Purchase | :white_check_mark: Already Synced |
| `POST` | `/purchase/simple-purchase` | Create Simple Purchase | :white_check_mark: Already Synced |
| `DELETE` | `/purchase/simple-purchase/{cashPurchaseNum}` | Delete Simple Purchase | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/simple-purchase/{cashPurchaseNum}/reject` | Reject Simple Purchase | :white_check_mark: Already Synced |
| `GET` | `/purchase/simple-purchase` | Simple Purchase Index | :white_check_mark: Already Synced |
| `PUT` | `/purchase/simple-purchase/{cashPurchaseNum}` | Update Simple Purchase | :white_check_mark: Already Synced |
| `POST` | `/purchase/simple-purchase/upload` | Upload Simple Purchase | :white_check_mark: Already Synced |
| `GET` | `/purchase/simple-purchase/{simplePurchaseNum}` | View Simple Purchase | :white_check_mark: Already Synced |

#### Purchase Request (7 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/purchase/purchase-request/{purchaseRequestNum}/authorize` | Authorize Purchase Request | :white_check_mark: Already Synced |
| `POST` | `/purchase/purchase-request` | Create Purchase Request | :white_check_mark: Already Synced |
| `DELETE` | `/purchase/purchase-request/{purchaseRequestNum}` | Delete Purchase Request | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-request` | Purchase Request Index | :white_check_mark: Already Synced |
| `PATCH` | `/purchase/purchase-request/{purchaseRequestNum}/reject` | Reject Purchase Request | :white_check_mark: Already Synced |
| `PUT` | `/purchase/purchase-request/{{purchaseRequestNum}}` | Update Purchase Request | :white_check_mark: Already Synced |
| `GET` | `/purchase/purchase-request/{purchaseRequestNum}` | View Purchase Request | :white_check_mark: Already Synced |

### B2. Sales (ESB Core)

#### Sales Order (11 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/sales/product-sales/{productSalesNum}/authorize` | Authorize Sales Order | :white_check_mark: Already Synced |
| `PATCH` | `/sales/product-sales/{productSalesNum}/finish` | Close Sales Order | :white_check_mark: Already Synced |
| `POST` | `/sales/product-sales` | Create Sales Order | :white_check_mark: Already Synced |
| `DELETE` | `/sales/product-sales/{productSalesNum}` | Delete Sales Order | :white_check_mark: Already Synced |
| `GET` | `/sales/product-sales/{productSalesNum}/export` | Export Sales Order | :white_check_mark: Already Synced |
| `PATCH` | `/sales/product-sales/{{productSalesNum}}/reject` | Reject Sales Order | :white_check_mark: Already Synced |
| `GET` | `/sales/product-sales` | Sales Order Index | :white_check_mark: Already Synced |
| `PATCH` | `/sales/product-sales/{productSalesNum}/unfinished` | Unclose Sales Order | :white_check_mark: Already Synced |
| `PUT` | `/sales/product-sales/{productSalesNum}` | Update Sales Order | :white_check_mark: Already Synced |
| `POST` | `/sales/product-sales/upload` | Upload Sales Order | :white_check_mark: Already Synced |
| `GET` | `/sales/product-sales/{productSalesNum}` | View Sales Order | :white_check_mark: Already Synced |

#### Simple Sales (16 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/sales/simple-product-sales/:simpleProductSalesNum/authorize` | Authorize Simple Sales | :white_check_mark: Already Synced |
| `POST` | `/sales/simple-product-sales` | Create Simple Sales | :white_check_mark: Already Synced |
| `DELETE` | `/sales/simple-product-sales/:simpleProductSalesNum` | Delete Simple Sales | :white_check_mark: Already Synced |
| `POST` | `/sales/simple-product-sales/export-csv` | Export CSV by IDs | :white_check_mark: Already Synced |
| `GET` | `/sales/simple-product-sales/export-csv-all` | Export CSV All | :white_check_mark: Already Synced |
| `POST` | `/sales/simple-product-sales/export-xlsx` | Export XLSX by IDs | :white_check_mark: Already Synced |
| `GET` | `/sales/simple-product-sales/export-xlsx-all` | Export XLSX All | :white_check_mark: Already Synced |
| `POST` | `/sales/simple-product-sales/export-xml` | Export XML by IDs | :white_check_mark: Already Synced |
| `GET` | `/sales/simple-product-sales/export-xml-all` | Export XML All | :white_check_mark: Already Synced |
| `PATCH` | `/sales/simple-product-sales/:simpleProductSalesNum/reject` | Reject Simple Sales | :white_check_mark: Already Synced |
| `GET` | `/sales/simple-product-sales` | Simple Sales Index | :white_check_mark: Already Synced |
| `PUT` | `/sales/simple-product-sales/:simpleProductSalesNum` | Update Simple Sales | :white_check_mark: Already Synced |
| `POST` | `/sales/simple-product-sales/:simpleProductSalesNum/asset-images` | Upload Attachment Simple Sales | :white_check_mark: Already Synced |
| `POST` | `/sales/simple-product-sales/upload` | Upload Asset Image Simple Sales | :white_check_mark: Already Synced |
| `POST` | `/sales/simple-product-sales/:simpleProductSalesNum/validate` | Validate Before Save | :white_check_mark: Already Synced |
| `GET` | `/sales/simple-product-sales/:simpleProductSalesNum` | View Simple Sales | :white_check_mark: Already Synced |

### B3. Inventory (ESB Core)

#### Goods Receipt (12 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/inventory/goods-receipt/{goodsReceiptNum}/authorize` | Authorize Goods Receipt | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-receipt/browse-return` | Browse Return Goods Receipt | :white_check_mark: Already Synced |
| `POST` | `/inventory/goods-receipt/{refNum}` | Create Goods Receipt | :white_check_mark: Already Synced |
| `DELETE` | `/inventory/goods-receipt/{goodsReceiptNum}` | Delete Goods Receipt | :white_check_mark: Already Synced |
| `GET` | `|` | Flow Goods Receipt | :white_check_mark: Already Synced |
| `GET` | `corev1/goods-receipt/inquiry` | Get Goods Receipt | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-receipt` | Goods Receipt Index | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-receipt/initialize` | Initialize Goods Receipt Data | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/goods-receipt/{goodsReceiptNum}/reject` | Reject Goods Receipt | :white_check_mark: Already Synced |
| `POST` | `/inventory/goods-receipt/{goodsReceiptNum}/asset-imagesn` | Save Goods Receipt Attachments | :white_check_mark: Already Synced |
| `PUT` | `/inventory/goods-receipt/{goodsReceiptNum}` | Update Goods Receipt | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-receipt/{goodsReceiptNum}` | View Goods Receipt | :white_check_mark: Already Synced |

#### Goods Delivery (10 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/inventory/goods-delivery/{goodsDeliveryNum}/authorize` | Authorize Goods Delivery | :white_check_mark: Already Synced |
| `POST` | `/inventory/goods-delivery/{refNum}` | Create Goods Delivery | :white_check_mark: Already Synced |
| `DELETE` | `/inventory/goods-delivery/{goodsDeliveryNum}` | Delete Goods Delivery | :white_check_mark: Already Synced |
| `GET` | `|` | Flow Goods Delivery | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-delivery` | Goods Delivery Index | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-delivery/create/{refNum}` | Initialize Goods Delivery Data | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/goods-delivery/{goodsDeliveryNum}/reject` | Reject Goods Delivery | :white_check_mark: Already Synced |
| `PUT` | `/inventory/goods-delivery/{goodsDeliveryNum}` | Update Goods Delivery | :white_check_mark: Already Synced |
| `POST` | `/inventory/goods-delivery/{goodsDeliveryNum}/upload/attachment` | Upload Goods Delivery Attachment | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-delivery/{goodsDeliveryNum}` | View Goods Delivery | :white_check_mark: Already Synced |

#### Goods Transfer Request (10 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/inventory/goods-transfer-request/{transferNum}/authorize` | Authorize Goods Transfer Request | :white_check_mark: Already Synced |
| `POST` | `/inventory/goods-transfer-request` | Create Goods Transfer Request | :white_check_mark: Already Synced |
| `DELETE` | `/inventory/goods-transfer-request/{transferNum}` | Delete Goods Transfer Request | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/goods-transfer-request/{transferNum}/finish` | Finish Goods Transfer Request | :white_check_mark: Already Synced |
| `GET` | `|` | Flow Goods Transfer Request | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-transfer-request` | Goods Transfer Request Index | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/goods-transfer-request/{transferNum}/reject` | Reject Goods Transfer Request | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/goods-transfer-request/{transferNum}/unfinished` | Unfinish Goods Transfer Request | :white_check_mark: Already Synced |
| `PUT` | `/inventory/goods-transfer-request/{transferNum}` | Update Goods Transfer Request | :white_check_mark: Already Synced |
| `GET` | `/inventory/goods-transfer-request/{transferNum}` | View Goods Transfer Request | :white_check_mark: Already Synced |

#### Item Journal (9 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/inventory/item-journal/:itemJournalNum/authorize` | Authorize Item Journal | :white_check_mark: Already Synced |
| `POST` | `/inventory/item-journal` | Create Item Journal | :white_check_mark: Already Synced |
| `DELETE` | `/inventory/item-journal/:itemJournalNum` | Delete Item Journal | :white_check_mark: Already Synced |
| `DELETE` | `/inventory/item-journal/:itemJournalNum/attachment` | Delete Item Journal Attachment | :white_check_mark: Already Synced |
| `GET` | `/inventory/item-journal` | Item Journal Index | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/item-journal/:itemJournalNum/reject` | Reject Item Journal | :white_check_mark: Already Synced |
| `PUT` | `/inventory/item-journal/:itemJournalNum` | Update Item Journal | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/item-journal/:itemJournalNum/attachment` | Upload Item Journal Attachment | :white_check_mark: Already Synced |
| `GET` | `/inventory/item-journal/{itemJournalNum}` | View Item Journal | :white_check_mark: Already Synced |

#### Receipt (9 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/receipt/{receiptNum}/authorize` | Authorize Receipt | :white_check_mark: Already Synced |
| `POST` | `/receipt` | Create Receipt | :white_check_mark: Already Synced |
| `DELETE` | `/receipt/{receiptNum}` | Delete Receipt | :white_check_mark: Already Synced |
| `POST` | `/receipt/import` | Import Receipt | :white_check_mark: Already Synced |
| `GET` | `/receipt` | Receipt Index | :white_check_mark: Already Synced |
| `PATCH` | `/inventory/receipt/{receiptNum}/reject` | Reject Receipt | :white_check_mark: Already Synced |
| `PUT` | `/receipt/{receiptNum}` | Update Receipt | :white_check_mark: Already Synced |
| `POST` | `/receipt/{receiptNum}/attachment` | Upload Receipt Attachment | :white_check_mark: Already Synced |
| `GET` | `/receipt/{receiptNum}` | View Receipt | :white_check_mark: Already Synced |

### B4. Production (ESB Core)

#### Production Order (7 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|

#### Production Result (7 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|

#### Material Delivery (7 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|

#### Simple Manufacturing (14 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|

### B5. Accounting (ESB Core)

#### Memorial Journal (12 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/accounting/memorial-journal/:memorialJournalNum/authorize` | Authorize Memorial Journal | :white_check_mark: Already Synced |
| `POST` | `/accounting/memorial-journal` | Create Memorial Journal | :white_check_mark: Already Synced |
| `DELETE` | `/accounting/memorial-journal/:memorialJournalNum` | Delete Memorial Journal | :white_check_mark: Already Synced |
| `GET` | `/accounting/memorial-journal/export` | Export Memorial Journal | :white_check_mark: Already Synced |
| `POST` | `/accounting/memorial-journal/form-upload` | Form Upload Memorial Journal | :white_check_mark: Already Synced |
| `GET` | `/accounting/memorial-journal/access` | Check Access Memorial Journal | :white_check_mark: Already Synced |
| `GET` | `/accounting/memorial-journal` | Index Memorial Journal | :white_check_mark: Already Synced |
| `PATCH` | `/accounting/memorial-journal/:memorialJournalNum/reject` | Reject Memorial Journal | :white_check_mark: Already Synced |
| `PUT` | `/accounting/memorial-journal/:memorialJournalNum` | Update Memorial Journal | :white_check_mark: Already Synced |
| `POST` | `/accounting/memorial-journal/upload` | Upload Memorial Journal | :white_check_mark: Already Synced |
| `POST` | `/accounting/memorial-journal/:memorialJournalNum/asset-images` | Upload Asset Images Memorial Journal | :white_check_mark: Already Synced |
| `GET` | `/accounting/memorial-journal/:memorialJournalNum` | View Memorial Journal | :white_check_mark: Already Synced |

#### Budget (37 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/budget/budget-adjustment/:budgetAdjustmentNum/authorize` | Authorize Budget Adjustment | :white_check_mark: Already Synced |
| `POST` | `/budget/budget-adjustment` | Create Budget Adjustment | :white_check_mark: Already Synced |
| `DELETE` | `/budget/budget-adjustment/:budgetAdjustmentNum` | Delete Budget Adjustment | :white_check_mark: Already Synced |
| `GET` | `/budget/budget-adjustment` | Get All Data Budget Adjustment | :white_check_mark: Already Synced |
| `GET` | `/budget/budget-adjustment/:budgetAdjustmentNum` | Get Budget Adjustment | :white_check_mark: Already Synced |
| `PATCH` | `/budget/budget-adjustment/:budgetAdjustmentNum/reject` | Reject Budget Adjustment | :white_check_mark: Already Synced |
| `PUT` | `/budget/budget-adjustment/:budgetAdjustmentNum` | Update Budget Adjustment | :white_check_mark: Already Synced |
| `PATCH` | `/budget/budget-allocate/:budgetAdjustmentNum/authorize` | Authorize Budget Allocate | :white_check_mark: Already Synced |
| `POST` | `/budget/budget-allocate` | Create Budget Allocate | :white_check_mark: Already Synced |
| `DELETE` | `/budget/budget-allocate/:budgetAdjustmentNum` | Delete Budget Allocate | :white_check_mark: Already Synced |
| `GET` | `/budget/budget-allocate` | Get All Data Budget Allocate | :white_check_mark: Already Synced |
| `GET` | `/budget/budget-allocate/:budgetAdjustmentNum` | Get Budget Allocate | :white_check_mark: Already Synced |
| `PATCH` | `/budget/budget-allocate/:budgetAdjustmentNum/reject` | Reject Budget Allocate | :white_check_mark: Already Synced |
| `PUT` | `/budget/budget-allocate/:budgetAdjustmentNum` | Update Budget Allocate | :white_check_mark: Already Synced |
| `POST` | `/budgets/amount` | Get Budget Detail Amount | :white_check_mark: Already Synced |
| `PATCH` | `/budgets/:budgetNum/authorize` | Authorize Budget Detail | :white_check_mark: Already Synced |
| `GET` | `/budgets/browse` | Browse Budget Detail | :white_check_mark: Already Synced |
| `GET` | `/budgets/browse/detail` | Browse Budget Detail Data | :white_check_mark: Already Synced |
| `POST` | `/budgets` | Create Budget Detail | :white_check_mark: Already Synced |
| `DELETE` | `/budgets/:budgetNum` | Delete Budget Detail | :white_check_mark: Already Synced |
| `GET` | `/budgets/:budgetNum/dropdown` | Get Budget Dropdown | :white_check_mark: Already Synced |
| `POST` | `/budgets/export-form` | Export Budget Detail Form | :white_check_mark: Already Synced |
| `GET` | `/budgets/:budgetNum` | Get Budget Detail | :white_check_mark: Already Synced |
| `GET` | `/budgets` | Get All Data Budget Detail | :white_check_mark: Already Synced |
| `POST` | `/budgets/import-form` | Import Budget Detail Form | :white_check_mark: Already Synced |
| `PATCH` | `/budgets/:budgetNum/reject` | Reject Budget Detail | :white_check_mark: Already Synced |
| `PUT` | `/budgets/:budgetNum` | Update Budget Detail | :white_check_mark: Already Synced |
| `PATCH` | `/budget-plan/:budgetPlanNum/authorize` | Authorize Budget Plan | :white_check_mark: Already Synced |
| `GET` | `/budget-plan/browse` | Browse Budget Plan | :white_check_mark: Already Synced |
| `GET` | `/budget-plan/:budgetPlanNum/chart-of-accounts` | Get Budget Plan Chart of Accounts | :white_check_mark: Already Synced |
| `POST` | `/budget-plan` | Create Budget Plan | :white_check_mark: Already Synced |
| `DELETE` | `/budget-plan/:budgetPlanNum` | Delete Budget Plan | :white_check_mark: Already Synced |
| `GET` | `/budget-plan/:budgetPlanNum/chart-of-accounts/details` | Get Budget Plan Detail by COA | :white_check_mark: Already Synced |
| `GET` | `/budget-plan/:budgetPlanNum` | Get Budget Plan | :white_check_mark: Already Synced |
| `GET` | `/budget-plan` | Get All Data Budget Plan | :white_check_mark: Already Synced |
| `PATCH` | `/budget-plan/:budgetPlanNum/reject` | Reject Budget Plan | :white_check_mark: Already Synced |
| `PUT` | `/budget-plan/:budgetPlanNum` | Update Budget Plan | :white_check_mark: Already Synced |

#### General Ledger (2 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/corev1/general-ledger` | General Ledger | :white_check_mark: Already Synced |
| `POST` | `/accounting/general-ledger/summary` | Get Summary General Ledger | :white_check_mark: Already Synced |

### B6. Employee (ESB Core)

#### Employee Advance Payment (24 endpoints - counted in B1_Purchase_AdvancePayment)

Note: Employee Advance Payment endpoints are categorized under B1_Purchase_AdvancePayment with prefix `/employee/employee-advance-payment/`.

### B7. POS / OMS Transactions (ESB OMS)

#### Push Sales Data (13 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/corev1/sales/get-daily-sales-material-usage` | Daily Sales Material Usage | :white_check_mark: Already Synced |
| `POST` | `/external/general/sales-branch-summary` | Branch Sales Summary | :white_check_mark: Already Synced |
| `POST` | `https://int-erp.esb.co.id/external/push/sales-data` | Push Sales Data | :white_check_mark: Already Synced |
| `POST` | `/extv1/push/sales-data` | Push Sales Data V2 | :white_check_mark: Already Synced |
| `POST` | `https://int-erp.esb.co.id/external/push/shift-data` | Shift Data | :white_check_mark: Already Synced |
| `POST` | `/corev1/shift-data/push` | Shift Data V2 | :white_check_mark: Already Synced |
| `GET` | `/corev1/sales/sales-information` | Sales Information | :white_check_mark: Already Synced |
| `POST` | `https://int-erp.esb.co.id/external/sales/get-sales-information?page={i}` | Sales Information | :white_check_mark: Already Synced |
| `POST` | `/external/general/sales-head?page=x` | Sales Head | :white_check_mark: Already Synced |
| `POST` | `/external/general/sales-menu` | Sales Menu | :white_check_mark: Already Synced |
| `POST` | `/external/general/sales-menu-completion` | Sales Menu Completion | :white_check_mark: Already Synced |
| `GET` | `/extv1/sales/sales-menu-summary/` | Sales Menu Summary | :white_check_mark: Already Synced |
| `GET` | `/report/sales-payment-summary` | Sales Payment Summary | :white_check_mark: Already Synced |

### Other Transaction Endpoints (ESB Core)

#### Online Voucher (3 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `POST` | `/v1/online-voucher/burn` | Burn Online Voucher | :white_check_mark: Already Synced |
| `POST` | `/v1/online-voucher/` | Create Online Voucher (Multi Company) | :white_check_mark: Already Synced |
| `POST` | `/v1/online-voucher/validate` | Validate Online Voucher | :white_check_mark: Already Synced |

#### Simple Transfer (9 endpoints)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `PATCH` | `/simple-transfer/simpleTransferNum/authorize` | Authorize Simple Transfer | :white_check_mark: Already Synced |
| `POST` | `/simple-transfer` | Create Simple Transfer | :white_check_mark: Already Synced |
| `DELETE` | `/simple-transfer/{simpleTransferNum}` | Delete Simple Transfer | :white_check_mark: Already Synced |
| `POST` | `/simple-transfer/import` | Import Simple Transfer | :white_check_mark: Already Synced |
| `PATCH` | `/simple-transfer/simpleTransferNum/reject` | Reject Simple Transfer | :white_check_mark: Already Synced |
| `GET` | `/simple-transfer` | Simple Transfer Index | :white_check_mark: Already Synced |
| `PUT` | `/simple-transfer/{simpleTransferNum}` | Update Simple Transfer | :white_check_mark: Already Synced |
| `POST` | `/simple-transfer/simpleTransferNum/attachment` | Upload Simple Transfer Attachment | :white_check_mark: Already Synced |
| `GET` | `/simple-transfer/{simpleTransferNum}` | View Simple Transfer | :white_check_mark: Already Synced |

---

## 4. Category C - Reports (ESB Core)

Report endpoints provide analytical data and summaries for business intelligence.

### Stock Movement Report (1 endpoint)

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/report/stock-movement` | Stock Movement Report | :white_check_mark: Already Synced |

### Additional Report Endpoints Used by the Engine (v1.1)

These are consumed by `RPT_DIRECT` / POS lanes but are missing from the
spec-derived list above:

| Method | Endpoint | Title | Engine Status |
|--------|----------|-------|---------------|
| `GET`/`POST` | `/report/goods-receipt-recapitulation` | Goods Receipt Recapitulation | :white_check_mark: Active (T-2 window) |
| `GET` | `/report/sales-payment-summary` | Sales Payment Summary | :white_check_mark: Active (T-2 window) |
| — | `/report/menu-cogs` | Menu COGS | :warning: Dead on production (404 since 2026-09-08), removed from engine |
| — | `/report/purchase-recapitulation` | Purchase Recapitulation | :warning: Dead on production (404 since 2026-09-08), removed from engine |

---

## 5. Other / External Endpoints (7 endpoints)

The following endpoints are available but not categorized in the standard groups.

| Method | Endpoint | Title | Status |
|--------|----------|-------|--------|
| `GET` | `/corev1/master/product` | Get Product | :white_check_mark: Already Synced |
| `POST` | `/external/general/get-branch` | Branch | :white_check_mark: Already Synced |
| `POST` | `/external/general/get-menu` | Menu | :white_check_mark: Already Synced |
| `POST` | `/external/general/get-payment-method` | Payment Method | :white_check_mark: Already Synced |
| `POST` | `/external/general/get-visit-purpose` | Visit Purpose | :white_check_mark: Already Synced |
| `POST` | `/external/general/get-sales` | Get Sales | :white_check_mark: Already Synced |
| `GET` | `|` | Flow Push Sales And Shift Data | :white_check_mark: Already Synced |

---

## 6. Cross-Reference: Scope Document vs Available Endpoints

This section maps the entities defined in the ESB Core Data Consumption Scope document against the actual API endpoints.

| Entity | Scope Priority | API Endpoint | Status |
|--------|---------------|--------------|--------|
| Product | P0 | `/product` | :white_check_mark: Available |
| Product Category | P0 | `/product/category` | :white_check_mark: Available |
| Product Sub-Category | P0 | `/product/sub-category` | :white_check_mark: Available |
| Unit of Measure | P0 | `/units` | :white_check_mark: Available |
| Bill of Material | P1 | `/product/bom` | :white_check_mark: Available |
| Supplier | P0 | `/supplier` | :white_check_mark: Available |
| Customer | P0 | `/customer` | :white_check_mark: Available |
| Customer Pricelist | P1 | `/customer-pricelist` | :white_check_mark: Available |
| Branch | P0 | `/branch` | :white_check_mark: Available |
| Location | P0 | `/location` | :white_check_mark: Available |
| Document Template | P2 | `/document-template` | :white_check_mark: Available |
| Purpose (Accounting) | P1 | `/purpose` | :white_check_mark: Available |
| Cost Center | P1 | `/cost-center` | :white_check_mark: Available |
| Purchase Order | P0 | `/purchase/purchase-order` | :white_check_mark: Available |
| Purchase Invoice | P0 | `/purchase/purchase-invoices` | :white_check_mark: Available |
| Purchase Return | P1 | `/purchases/purchase-return` | :white_check_mark: Available |
| Advance Payment | P1 | `/purchase/advance-payment` | :white_check_mark: Available |
| Sales Order | P0 | `/sales/product-sales` | :white_check_mark: Available |
| Goods Receipt | P0 | `/inventory/goods-receipt` | :white_check_mark: Available |
| Goods Delivery | P0 | `/inventory/goods-delivery` | :white_check_mark: Available |
| Goods Transfer Request | P1 | `/inventory/goods-transfer-request` | :white_check_mark: Available |
| Item Journal | P1 | `/inventory/item-journal` | :white_check_mark: Available |
| Production Order | P1 | `/production/production-order` | :white_check_mark: Available |
| Memorial Journal | P2 | `/accounting/memorial-journal` | :white_check_mark: Available |
| Budget | P2 | `/budgets` | :white_check_mark: Available |
| Employee Advance | P1 | `/employee/employee-advance-payment` | :white_check_mark: Available |
| Receipt | P1 | `/receipt` | :white_check_mark: Available |
| Stock Movement Report | P1 | `/report/stock-movement` | :white_check_mark: Available |

---

## 7. Implementation Priority Matrix

### P0 - Critical (Ready for Integration)

| Domain | Endpoint | Notes |
|--------|----------|-------|
| Product | `/product` | Core product master data |
| Product Category | `/product/category` | Category hierarchy |
| Product Sub-Category | `/product/sub-category` | Sub-category hierarchy |
| Unit of Measure | `/units` | UOM definitions |
| Supplier | `/supplier` | Vendor management |
| Customer | `/customer` | Customer master data |
| Branch | `/branch` | Organization structure |
| Location | `/location` | Warehouse/location data |
| Purchase Order | `/purchase/purchase-order` | PO creation and management |
| Purchase Invoice | `/purchase/purchase-invoices` | Vendor invoicing |
| Sales Order | `/sales/product-sales` | Customer order management |
| Goods Receipt | `/inventory/goods-receipt` | Inbound inventory |
| Goods Delivery | `/inventory/goods-delivery` | Outbound inventory |

### P1 - High Priority (Ready for Integration)

| Domain | Endpoint | Notes |
|--------|----------|-------|
| BOM | `/product/bom` | Bill of materials for manufacturing |
| Customer Pricelist | `/customer-pricelist` | Customer-specific pricing |
| Purchase Return | `/purchases/purchase-return` | Return processing |
| Advance Payment | `/purchase/advance-payment` | Prepaid vendor payments |
| Goods Transfer | `/inventory/goods-transfer-request` | Internal transfers |
| Item Journal | `/inventory/item-journal` | Inventory adjustments |
| Production Order | `/production/production-order` | Manufacturing orders |
| Employee Advance | `/employee/employee-advance-payment` | Staff advances |
| Receipt | `/receipt` | Payment receipts |
| Stock Movement Report | `/report/stock-movement` | Inventory analytics |
| Purpose | `/purpose` | Accounting purposes |
| Cost Center | `/cost-center` | Cost allocation |

### P2 - Medium Priority (Ready for Integration)

| Domain | Endpoint | Notes |
|--------|----------|-------|
| Document Template | `/document-template` | Print layouts |
| Purchase Request | `/purchase/purchase-request` | Internal requisitions |
| Simple Purchase | `/purchase/simple-purchase` | Quick purchases |
| Simple Sales | `/sales/simple-product-sales` | POS-style sales |
| Production Result | `/production/production-result` | Finished goods |
| Material Delivery | `/production/material-delivery` | Production materials |
| Simple Manufacturing | `/production/simple-manufacturing` | Basic production |
| Memorial Journal | `/accounting/memorial-journal` | Manual journal entries |
| Budget | `/budgets`, `/budget-plan` | Budget management |
| Simple Transfer | `/simple-transfer` | Quick inventory moves |
| Online Voucher | `/v1/online-voucher` | Promotional vouchers |

---

## 8. Critical Gaps & Open Questions

Based on the comprehensive review of the ESB Core and ESB OMS APIs, the following gaps and open questions have been identified:

### 8.1 Endpoints with No API Equivalent (Gaps)

| Entity | Gap Description | Workaround |
|--------|-----------------|------------|
| Chart of Accounts (COA) | No direct endpoint for COA master data | Memorial Journal uses COA but no standalone read |
| Currency | No currency master data endpoint | Assumed system-managed |
| Tax Rates | No tax configuration endpoint | Inferred from transactions |
| Payment Terms | No payment terms master | Inferred from transactions |
| Warehouse | No standalone warehouse endpoint | Location serves as warehouse |

### 8.2 Open Questions

1. **Approval Workflows**: How are approval hierarchies configured and triggered?

2. **Multi-Company Support**: How should transactions be routed across multiple company codes?

3. **Real-time vs Batch**: Are master data sync operations real-time or batch-oriented?

4. **OMS Menu Sync**: The `/corev1/master/get-menu` endpoint - what is the full data structure?

5. **Promotion Priority**: How are overlapping promotions evaluated?

6. **Shift Data Retention**: What is the retention policy for shift data?

7. **Sales Reporting**: Are there endpoints for sales analytics beyond the payment summary?

### 8.3 Authorization & Access Control

Several endpoints have authorization requirements that need clarification:

- **Authorize Endpoints**: Require user to have authorization access
- **Release Access**: Some authorize endpoints also require release payment journal access
- **Approval Flow**: If configured, authorization routes to designated approvers

---

## Appendix A: Complete Endpoint Summary

### By Category

| Category | Endpoint Count |
|----------|---------------|
| A1_Product | 59 |
| A1_Product_BOM | 14 |
| A1_Product_Category | 2 |
| A1_Product_SubCategory | 2 |
| A1_Unit | 2 |
| A2_Partner_Customer | 10 |
| A2_Partner_CustomerPricelist | 21 |
| A2_Partner_Supplier | 11 |
| A3_Company | 7 |
| A3_Company_DocTemplate | 2 |
| A4_Accounting_CostCenter | 2 |
| A4_Accounting_Purpose | 2 |
| A6_POS_OMS_Member | 1 |
| A6_POS_OMS_Menu | 3 |
| A6_POS_OMS_Menu_Category | 3 |
| A6_POS_OMS_Menu_Template | 3 |
| A6_POS_OMS_POS | 1 |
| A6_POS_OMS_Promotion | 6 |
| B1_Purchase_AdvancePayment | 24 |
| B1_Purchase_PurchaseInvoice | 23 |
| B1_Purchase_PurchaseOrder | 16 |
| B1_Purchase_PurchaseRequest | 7 |
| B1_Purchase_PurchaseReturn | 7 |
| B1_Purchase_SimplePurchase | 8 |
| B2_Sales_SalesOrder | 11 |
| B2_Sales_SimpleSales | 16 |
| B3_Inventory_GoodsDelivery | 10 |
| B3_Inventory_GoodsReceipt | 12 |
| B3_Inventory_GoodsTransferRequest | 10 |
| B3_Inventory_ItemJournal | 9 |
| B3_Inventory_Receipt | 9 |
| B5_Accounting_Budget | 37 |
| B5_Accounting_GeneralLedger | 2 |
| B5_Accounting_MemorialJournal | 12 |
| B7_POS_OMS_Transactions | 13 |
| B_Other_OnlineVoucher | 3 |
| B_Other_SimpleTransfer | 9 |
| C_Reports | 1 |
| Other | 7 |
| auth | 4 |

### By Source System

| System | Endpoint Count |
|--------|---------------|
| ESB Core | 363 |
| ESB OMS | 38 |

---

*Document generated from API specification files. Endpoint counts and availability subject to change.*
*Generated: September 2026*