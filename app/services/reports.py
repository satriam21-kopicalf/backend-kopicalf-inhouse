"""Report registry + query layer (Sprint 2).

Three Tier-1 reports live:
- stock-opname-report        <- trx_raw_staging STOCK_OPNAME (index->view, details)
- stock-movement-report      <- report_raw_staging RPT_STOCK_MOVEMENT (direct)
- daily-sales-payment-recapitulation-report <- report_raw_staging RPT_SALES_PAYMENT_SUMMARY (direct)

Columns mirror the ERP sample exports (SampleExport-ModuleReport), so output is
comparable 1:1 with ERP-generated XLSX.

Report Categories:
- sales: Daily sales, payment methods, customer orders
- inventory: Stock opname, stock movement, stock valuation
- purchasing: Purchase orders, goods receipts, supplier analysis
- manufacturing: Production orders, BOM usage, output
- financial: Disbursements, receipts, journals

Report Tiers:
- T1: Direct ERP data (trx_raw_staging) - real-time transactions
- T2: CALF-aggregated (report_raw_staging) - pre-computed reports
"""
import json
import re
import typing
from datetime import date

from app.core.db import get_db_connection

# Report Category Registry
REPORT_CATEGORIES = {
    "inventory": {
        "label": "Inventory",
        "icon": "Package",
        "description": "Stock management and movement reports",
        "tier": "T1",
    },
    "sales": {
        "label": "Sales",
        "icon": "TrendingUp",
        "description": "Sales and payment reports",
        "tier": "T2",
    },
    "purchasing": {
        "label": "Purchasing",
        "icon": "ShoppingCart",
        "description": "Purchase orders and goods receipts",
        "tier": "T1",
    },
    "manufacturing": {
        "label": "Manufacturing",
        "icon": "Factory",
        "description": "Production and BOM reports",
        "tier": "T1",
    },
    "financial": {
        "label": "Financial",
        "icon": "Wallet",
        "description": "Financial transaction reports",
        "tier": "T1",
    },
}

# Companies that have data for each report
REPORT_COMPANIES = {
    "stock-opname-report": [1, 2, 3, 4, 5, 6, 7, 8],
    "stock-movement-report": [1, 3, 4, 5, 6, 7, 8],
    "daily-sales-payment-recapitulation-report": [1, 8],
    # Priority Reports (Sprint 4)
    "sales-recapitulation-detail-report": [1, 2, 3, 4, 5, 6, 7, 8],
    "goods-receipt-recap-report": [1, 2, 3, 4, 5, 6, 7, 8],
}

REPORTS: typing.Dict[str, dict] = {
    "stock-opname-report": {
        "title": "Stock Opname Report",
        "title_id": "Laporan Stok Opname",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "STOCK_OPNAME",
        "description": "Stock opname comparison between system and physical count",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "stockOpnameNum", "label": "Stock Opname Number"},
            {"key": "stockOpnameDate", "label": "Stock Opname date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "locationName", "label": "Location"},
            {"key": "purposeName", "label": "Purpose"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "categoryName", "label": "Category"},
            {"key": "subCategoryName", "label": "Subcategory"},
            {"key": "uomName", "label": "Unit"},
            {"key": "stockQty", "label": "Period System Stock", "numeric": True},
            {"key": "qty", "label": "Opname Stock", "numeric": True},
            {"key": "diffQty", "label": "Difference Qty", "numeric": True},
            {"key": "hpp", "label": "Value per Unit", "numeric": True},
            {"key": "diffValue", "label": "Difference Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "additionalInfo", "label": "Additional Information"},
        ],
    },
    "stock-movement-report": {
        "title": "Stock Movement Report",
        "title_id": "Laporan Pergerakan Stok",
        "category": "inventory",
        "tier": "T2",
        "source": "rpt",
        "entity": "RPT_STOCK_MOVEMENT",
        "description": "Stock in/out movement by product and branch",
        "companies": [1, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "productCode", "label": "Product Code"},
            {"key": "productName", "label": "Product Name"},
            {"key": "branchName", "label": "Branch"},
            {"key": "location", "label": "Location"},
            {"key": "uomName", "label": "UoM"},
            {"key": "transactionType", "label": "Transaction Type"},
            {"key": "referenceNumber", "label": "Reference Number"},
            {"key": "documentCode", "label": "Document Code"},
            {"key": "documentDate", "label": "Document Date"},
            {"key": "valuePerUnit", "label": "Value Per Unit", "numeric": True},
            {"key": "qtyIn", "label": "Qty In", "numeric": True},
            {"key": "amountIn", "label": "Amount In", "numeric": True},
            {"key": "qtyOut", "label": "Qty Out", "numeric": True},
            {"key": "amountOut", "label": "Amount Out", "numeric": True},
            {"key": "qtyBalance", "label": "Qty Balance", "numeric": True},
            {"key": "amountBalance", "label": "Amount Balance", "numeric": True},
        ],
    },
    "daily-sales-payment-recapitulation-report": {
        "title": "Daily Sales Payment Recapitulation Report",
        "title_id": "Laporan Rekapitulasi Pembayaran Penjualan Harian",
        "category": "sales",
        "tier": "T2",
        "source": "rpt",
        "entity": "RPT_SALES_PAYMENT_SUMMARY",
        "description": "Daily sales summary by payment method",
        "companies": [1, 8],
        "columns": [
            {"key": "branchName", "label": "Branch"},
            {"key": "paymentMethodTypeName", "label": "Payment Method Type"},
            {"key": "paymentMethodName", "label": "Payment Method Name"},
            {"key": "transactionType", "label": "Transaction Type"},
            {"key": "paymentCount", "label": "Payment Count", "numeric": True},
            {"key": "paymentAmount", "label": "Payment Amount", "numeric": True},
            {"key": "mdr", "label": "MDR", "numeric": True},
            {"key": "netAfterMDR", "label": "Net After MDR", "numeric": True},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # PURCHASING REPORTS (T1 - Direct Transaction)
    # ─────────────────────────────────────────────────────────────────────────────
    "purchase-order-report": {
        "title": "Purchase Order Report",
        "title_id": "Laporan Purchase Order",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "PURCHASE_ORDER",
        "description": "Purchase order transactions by supplier and branch",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "purchaseOrderNum", "label": "PO Number"},
            {"key": "purchaseOrderDate", "label": "PO Date"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "discountPercent", "label": "Discount %", "numeric": True},
            {"key": "subTotal", "label": "Sub Total", "numeric": True},
            {"key": "taxPercent", "label": "Tax %", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "goods-receipt-report": {
        "title": "Goods Receipt Report",
        "title_id": "Laporan Penerimaan Barang",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "GOODS_RECEIPT",
        "description": "Goods receipt from suppliers",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "goodsReceiptNum", "label": "GR Number"},
            {"key": "goodsReceiptDate", "label": "GR Date"},
            {"key": "purchaseOrderNum", "label": "PO Reference"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "branchName", "label": "Branch"},
            {"key": "warehouseName", "label": "Warehouse"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qtyOrder", "label": "Qty Order", "numeric": True},
            {"key": "qtyReceive", "label": "Qty Received", "numeric": True},
            {"key": "qtyReject", "label": "Qty Rejected", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "totalReceive", "label": "Total Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "purchase-request-report": {
        "title": "Purchase Request Report",
        "title_id": "Laporan Purchase Request",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "PURCHASE_REQUEST",
        "description": "Purchase request for procurement",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "purchaseRequestNum", "label": "PR Number"},
            {"key": "purchaseRequestDate", "label": "PR Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "departmentName", "label": "Department"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "estimatedPrice", "label": "Est. Price", "numeric": True},
            {"key": "estimatedTotal", "label": "Est. Total", "numeric": True},
            {"key": "purposeName", "label": "Purpose"},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # INVENTORY REPORTS (T1 - Direct Transaction)
    # ─────────────────────────────────────────────────────────────────────────────
    "goods-delivery-report": {
        "title": "Goods Delivery Report",
        "title_id": "Laporan Pengeluaran Barang",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "GOODS_DELIVERY",
        "description": "Goods delivery to branches/customers",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "goodsDeliveryNum", "label": "GD Number"},
            {"key": "goodsDeliveryDate", "label": "GD Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "destinationName", "label": "Destination"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # MANUFACTURING REPORTS (T1 - Direct Transaction)
    # ─────────────────────────────────────────────────────────────────────────────
    "manufacturing-report": {
        "title": "Manufacturing Report",
        "title_id": "Laporan Produksi",
        "category": "manufacturing",
        "tier": "T1",
        "source": "trx",
        "entity": "SIMPLE_MANUFACTURING",
        "description": "Production output and BOM usage",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "manufacturingNum", "label": "Manufacturing Number"},
            {"key": "manufacturingDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "bomName", "label": "BOM Name"},
            {"key": "productName", "label": "Output Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "outputQty", "label": "Output Qty", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "totalOutput", "label": "Total Output Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # FINANCIAL REPORTS (T1 - Direct Transaction)
    # ─────────────────────────────────────────────────────────────────────────────
    "disbursement-report": {
        "title": "Disbursement Report",
        "title_id": "Laporan Pengeluaran Kas",
        "category": "financial",
        "tier": "T1",
        "source": "trx",
        "entity": "DISBURSEMENT",
        "description": "Cash/bank disbursement transactions",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "disbursementNum", "label": "Disbursement Number"},
            {"key": "disbursementDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "accountName", "label": "Account"},
            {"key": "paymentMethodName", "label": "Payment Method"},
            {"key": "partnerName", "label": "Partner"},
            {"key": "purposeName", "label": "Purpose"},
            {"key": "description", "label": "Description"},
            {"key": "amount", "label": "Amount", "numeric": True},
            {"key": "coaNo", "label": "COA Number"},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "receipt-report": {
        "title": "Receipt Report",
        "title_id": "Laporan Penerimaan Kas",
        "category": "financial",
        "tier": "T1",
        "source": "trx",
        "entity": "RECEIPT",
        "description": "Cash/bank receipt transactions",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "receiptNum", "label": "Receipt Number"},
            {"key": "receiptDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "accountName", "label": "Account"},
            {"key": "paymentMethodName", "label": "Payment Method"},
            {"key": "partnerName", "label": "Partner"},
            {"key": "purposeName", "label": "Purpose"},
            {"key": "description", "label": "Description"},
            {"key": "amount", "label": "Amount", "numeric": True},
            {"key": "coaNo", "label": "COA Number"},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "advance-sales-report": {
        "title": "Advance Sales Report",
        "title_id": "Laporan Penjualan Advance",
        "category": "sales",
        "tier": "T1",
        "source": "trx",
        "entity": "ADVANCE_SALES",
        "description": "Advance sales transactions",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "advanceSalesNum", "label": "Advance Sales Number"},
            {"key": "advanceSalesDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "customerName", "label": "Customer"},
            {"key": "productName", "label": "Product"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "memorial-journal-report": {
        "title": "Memorial Journal Report",
        "title_id": "Laporan Jurnal Memorial",
        "category": "financial",
        "tier": "T1",
        "source": "trx",
        "entity": "MEMORIAL_JOURNAL",
        "description": "Memorial journal entries",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "journalNum", "label": "Journal Number"},
            {"key": "journalDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "accountName", "label": "Account"},
            {"key": "accountNo", "label": "Account No"},
            {"key": "description", "label": "Description"},
            {"key": "debit", "label": "Debit", "numeric": True},
            {"key": "credit", "label": "Credit", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # ADDITIONAL INVENTORY REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "inventory-variance-opname-report": {
        "title": "Inventory Variance Opname Report",
        "title_id": "Laporan Varians Opname Inventori",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "STOCK_OPNAME",
        "description": "Stock opname variance analysis",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "stockOpnameNum", "label": "Opname Number"},
            {"key": "stockOpnameDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "locationName", "label": "Location"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "stockQty", "label": "Stock Qty", "numeric": True},
            {"key": "qty", "label": "Counted Qty", "numeric": True},
            {"key": "diffQty", "label": "Variance Qty", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "diffValue", "label": "Variance Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "transfer-report": {
        "title": "Transfer Report",
        "title_id": "Laporan Transfer",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "TRANSFER",
        "description": "Inventory transfer between warehouses",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "transferNum", "label": "Transfer Number"},
            {"key": "transferDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "sourceWarehouse", "label": "Source Warehouse"},
            {"key": "destinationWarehouse", "label": "Destination Warehouse"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "item-journal-report": {
        "title": "Item Journal Report",
        "title_id": "Laporan Jurnal Barang",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "ITEM_JOURNAL",
        "description": "Item movement journal",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "journalNum", "label": "Journal Number"},
            {"key": "journalDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "transactionType", "label": "Transaction Type"},
            {"key": "inQty", "label": "In Qty", "numeric": True},
            {"key": "outQty", "label": "Out Qty", "numeric": True},
            {"key": "balanceQty", "label": "Balance Qty", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "reference", "label": "Reference"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # PRODUCTION REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "production-order-report": {
        "title": "Production Order Report",
        "title_id": "Laporan Order Produksi",
        "category": "production",
        "tier": "T1",
        "source": "trx",
        "entity": "PRODUCTION_ORDER",
        "description": "Production order details",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "productionOrderNum", "label": "PO Number"},
            {"key": "productionOrderDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "dueDate", "label": "Due Date"},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "production-material-report": {
        "title": "Production Material Report",
        "title_id": "Laporan Material Produksi",
        "category": "production",
        "tier": "T1",
        "source": "trx",
        "entity": "PRODUCTION_MATERIAL",
        "description": "Production material consumption",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "materialIssueNum", "label": "Issue Number"},
            {"key": "materialIssueDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productionOrderNum", "label": "Production Order"},
            {"key": "productName", "label": "Output Product"},
            {"key": "materialName", "label": "Material"},
            {"key": "materialCode", "label": "Material Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # SALES REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "sales-payment-summary-report": {
        "title": "Sales Payment Summary Report",
        "title_id": "Laporan Ringkasan Pembayaran Penjualan",
        "category": "sales",
        "tier": "T1",
        "source": "trx",
        "entity": "SALES_PAYMENT",
        "description": "Sales payment by method summary",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "paymentNum", "label": "Payment Number"},
            {"key": "paymentDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "salesNum", "label": "Sales Number"},
            {"key": "paymentMethodTypeName", "label": "Payment Type"},
            {"key": "paymentMethodName", "label": "Payment Method"},
            {"key": "amount", "label": "Amount", "numeric": True},
            {"key": "cardNumber", "label": "Card Number"},
            {"key": "cardHolder", "label": "Card Holder"},
            {"key": "approvalCode", "label": "Approval Code"},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "sales-recapitulation-report": {
        "title": "Sales Recapitulation Report",
        "title_id": "Laporan Rekapitulasi Penjualan",
        "category": "sales",
        "tier": "T1",
        "source": "trx",
        "entity": "PRODUCT_SALES",
        "description": "Sales summary by product",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "salesNum", "label": "Sales Number"},
            {"key": "salesDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "customerName", "label": "Customer"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "discountPercent", "label": "Discount %", "numeric": True},
            {"key": "subTotal", "label": "Sub Total", "numeric": True},
            {"key": "taxPercent", "label": "Tax %", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "statusName", "label": "Status"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # POS SALES (bill-level summary; line-level lives in
    # sales-recapitulation-detail-report which joins head+lines ERP-identically)
    # ─────────────────────────────────────────────────────────────────────────────
    "pos-sales-summary-report": {
        "title": "POS Sales Summary by Bill",
        "title_id": "Laporan Rekap Penjualan POS (per Bill)",
        "category": "sales",
        "tier": "T1",
        "source": "table",
        "table": "report_pos_sales_head",
        "date_col": "sales_date",
        "branch_col": "branch_name",
        "order_col": "sales_date",
        "description": "POS sales bill headers with payment totals",
        "companies": [1],
        "columns": [
            {"key": "sales_num", "label": "Sales Number"},
            {"key": "bill_num", "label": "Bill Number"},
            {"key": "sales_date", "label": "Sales Date"},
            {"key": "branch_name", "label": "Branch"},
            {"key": "table_name", "label": "Table"},
            {"key": "member_name", "label": "Member"},
            {"key": "pax_total", "label": "Pax", "numeric": True},
            {"key": "subtotal", "label": "Sub Total", "numeric": True},
            {"key": "discount_total", "label": "Discount", "numeric": True},
            {"key": "vat_total", "label": "VAT", "numeric": True},
            {"key": "grand_total", "label": "Grand Total", "numeric": True},
            {"key": "status_name", "label": "Status"},
        ],
    },
    "goods-receipt-recap-report": {
        "title": "Goods Receipt Recapitulation Report",
        "title_id": "Laporan Rekapitulasi Penerimaan Barang",
        "category": "inventory",
        "tier": "T1",
        "source": "table",
        "table": "report_goods_receipt_recapitulation",
        "date_col": "report_date",
        "branch_col": "branch_name",
        "order_col": "report_date",
        "order_id_col": "id",
        "description": "Goods receipt line items (ERP-identical recapitulation)",
        "companies": [1],
        # Column order matches the ERP sample export
        "columns": [
            {"key": "receipt_number", "label": "Goods Receipt Number"},
            {"key": "receipt_date", "label": "Goods Receipt Date"},
            {"key": "reference_number", "label": "Reference Number"},
            {"key": "transaction_type", "label": "Transaction Type"},
            {"key": "origin_name", "label": "Origin"},
            {"key": "origin_location", "label": "Origin Location"},
            {"key": "destination_name", "label": "Destination"},
            {"key": "destination_location", "label": "Destination Location"},
            {"key": "cost_center_name", "label": "Cost Center"},
            {"key": "project_name", "label": "Project"},
            {"key": "category_name", "label": "Category"},
            {"key": "sub_category_name", "label": "Sub Category"},
            {"key": "product_name", "label": "Product Name"},
            {"key": "product_code", "label": "Product Code"},
            {"key": "uom_name", "label": "Unit"},
            {"key": "qty", "label": "Qty", "numeric": True},
            {"key": "converted_qty", "label": "Converted Qty", "numeric": True},
            {"key": "returned_qty", "label": "Returned Qty", "numeric": True},
            {"key": "expired_date", "label": "Expired Date"},
            {"key": "status_name", "label": "Status"},
            {"key": "additional_info", "label": "Add. Information"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # PRODUCT SALES REPORTS (T1) — recap line data is served by
    # sales-recapitulation-detail-report; only actuation is separate here
    # ─────────────────────────────────────────────────────────────────────────────
    "product-sales-actuation-report": {
        "title": "Product Sales Actuation Report",
        "title_id": "Laporan Aktuasi Penjualan Produk",
        "category": "product-sales",
        "tier": "T1",
        "source": "trx",
        "entity": "PRODUCT_SALES_ACTUATION",
        "description": "Product sales actuation details",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "actuationNum", "label": "Actuation Number"},
            {"key": "actuationDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productSalesNum", "label": "Sales Reference"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qtyOrdered", "label": "Qty Ordered", "numeric": True},
            {"key": "qtyDelivered", "label": "Qty Delivered", "numeric": True},
            {"key": "qtyInvoiced", "label": "Qty Invoiced", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # ACCOUNTING REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "account-receivable-suspense-report": {
        "title": "Account Receivable Suspense Report",
        "title_id": "Laporan Piutang Suspense",
        "category": "accounting",
        "tier": "T1",
        "source": "trx",
        "entity": "AR_SUSPENSE",
        "description": "Account receivable suspense entries",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "suspenseNum", "label": "Document Number"},
            {"key": "suspenseDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "customerName", "label": "Customer"},
            {"key": "accountName", "label": "Account"},
            {"key": "accountNo", "label": "Account No"},
            {"key": "description", "label": "Description"},
            {"key": "debit", "label": "Debit", "numeric": True},
            {"key": "credit", "label": "Credit", "numeric": True},
            {"key": "balance", "label": "Balance", "numeric": True},
            {"key": "dueDate", "label": "Due Date"},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "account-payable-suspense-report": {
        "title": "Account Payable Suspense Report",
        "title_id": "Laporan Hutang Suspense",
        "category": "accounting",
        "tier": "T1",
        "source": "trx",
        "entity": "AP_SUSPENSE",
        "description": "Account payable suspense entries",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "suspenseNum", "label": "Document Number"},
            {"key": "suspenseDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "accountName", "label": "Account"},
            {"key": "accountNo", "label": "Account No"},
            {"key": "description", "label": "Description"},
            {"key": "debit", "label": "Debit", "numeric": True},
            {"key": "credit", "label": "Credit", "numeric": True},
            {"key": "balance", "label": "Balance", "numeric": True},
            {"key": "dueDate", "label": "Due Date"},
            {"key": "statusName", "label": "Status"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # FINANCE REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "employee-advance-report": {
        "title": "Employee Advance Payment Report",
        "title_id": "Laporan Advance Karyawan",
        "category": "finance",
        "tier": "T1",
        "source": "trx",
        "entity": "EMPLOYEE_ADVANCE",
        "description": "Employee advance payments",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "advanceNum", "label": "Advance Number"},
            {"key": "advanceDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "employeeName", "label": "Employee"},
            {"key": "departmentName", "label": "Department"},
            {"key": "purposeName", "label": "Purpose"},
            {"key": "description", "label": "Description"},
            {"key": "amount", "label": "Amount", "numeric": True},
            {"key": "balance", "label": "Balance", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # BUDGETING REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "budget-detail-report": {
        "title": "Budget Detail Report",
        "title_id": "Laporan Detail Budget",
        "category": "budgeting",
        "tier": "T1",
        "source": "trx",
        "entity": "BUDGET_DETAIL",
        "description": "Budget detail by account",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "budgetNum", "label": "Budget Number"},
            {"key": "budgetDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "departmentName", "label": "Department"},
            {"key": "accountName", "label": "Account"},
            {"key": "accountNo", "label": "Account No"},
            {"key": "periodName", "label": "Period"},
            {"key": "budgetAmount", "label": "Budget Amount", "numeric": True},
            {"key": "realizedAmount", "label": "Realized", "numeric": True},
            {"key": "remainingAmount", "label": "Remaining", "numeric": True},
            {"key": "percentageUsed", "label": "Used %", "numeric": True},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "budget-increase-decrease-report": {
        "title": "Budget Increase/Decrease Report",
        "title_id": "Laporan Kenaikan/Penurunan Budget",
        "category": "budgeting",
        "tier": "T1",
        "source": "trx",
        "entity": "BUDGET_REVISION",
        "description": "Budget revision history",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "revisionNum", "label": "Revision Number"},
            {"key": "revisionDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "departmentName", "label": "Department"},
            {"key": "accountName", "label": "Account"},
            {"key": "periodName", "label": "Period"},
            {"key": "previousAmount", "label": "Previous Amount", "numeric": True},
            {"key": "changeAmount", "label": "Change", "numeric": True},
            {"key": "newAmount", "label": "New Amount", "numeric": True},
            {"key": "changeType", "label": "Change Type"},
            {"key": "reason", "label": "Reason"},
            {"key": "statusName", "label": "Status"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # ADDITIONAL PURCHASING REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "purchase-invoice-report": {
        "title": "Purchase Invoice Report",
        "title_id": "Laporan Invoice Pembelian",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "PURCHASE_INVOICE",
        "description": "Purchase invoice transactions",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "invoiceNum", "label": "Invoice Number"},
            {"key": "invoiceDate", "label": "Invoice Date"},
            {"key": "dueDate", "label": "Due Date"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "discountPercent", "label": "Discount %", "numeric": True},
            {"key": "subTotal", "label": "Sub Total", "numeric": True},
            {"key": "taxPercent", "label": "Tax %", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "purchase-invoice-payment-report": {
        "title": "Purchase Invoice Payment Report",
        "title_id": "Laporan Pembayaran Invoice Pembelian",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "PURCHASE_INVOICE_PAYMENT",
        "description": "Purchase invoice payment tracking",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "paymentNum", "label": "Payment Number"},
            {"key": "paymentDate", "label": "Payment Date"},
            {"key": "invoiceNum", "label": "Invoice Reference"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "branchName", "label": "Branch"},
            {"key": "accountName", "label": "Account"},
            {"key": "paymentMethodName", "label": "Payment Method"},
            {"key": "amount", "label": "Amount", "numeric": True},
            {"key": "reference", "label": "Reference"},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "purchase-return-report": {
        "title": "Purchase Return Report",
        "title_id": "Laporan Retur Pembelian",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "PURCHASE_RETURN",
        "description": "Purchase return transactions",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "returnNum", "label": "Return Number"},
            {"key": "returnDate", "label": "Return Date"},
            {"key": "invoiceNum", "label": "Invoice Reference"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "branchName", "label": "Branch"},
            {"key": "warehouseName", "label": "Warehouse"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "reason", "label": "Reason"},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "advance-recapitulation-report": {
        "title": "Advance Recapitulation Report",
        "title_id": "Laporan Rekapitulasi Advance",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "ADVANCE_RECAP",
        "description": "Advance payment recapitulation",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "advanceNum", "label": "Advance Number"},
            {"key": "advanceDate", "label": "Advance Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "employeeName", "label": "Employee"},
            {"key": "departmentName", "label": "Department"},
            {"key": "purposeName", "label": "Purpose"},
            {"key": "amount", "label": "Amount", "numeric": True},
            {"key": "realizedAmount", "label": "Realized", "numeric": True},
            {"key": "remainingAmount", "label": "Remaining", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────────
    # ADDITIONAL INVENTORY REPORTS (T1) — GR recap is served ERP-identically by
    # goods-receipt-recap-report (esb_data.report_goods_receipt_recapitulation)
    # ─────────────────────────────────────────────────────────────────────────────
    "goods-delivery-recapitulation-report": {
        "title": "Goods Delivery Recapitulation Report",
        "title_id": "Laporan Rekapitulasi Pengeluaran Barang",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "GOODS_DELIVERY",
        "description": "Goods delivery summary",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "goodsDeliveryNum", "label": "GD Number"},
            {"key": "goodsDeliveryDate", "label": "GD Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "destinationName", "label": "Destination"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "goods-receipt-return-report": {
        "title": "Goods Receipt Return Report",
        "title_id": "Laporan Retur Penerimaan Barang",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "GOODS_RECEIPT_RETURN",
        "description": "Goods receipt return transactions",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "returnNum", "label": "Return Number"},
            {"key": "returnDate", "label": "Return Date"},
            {"key": "goodsReceiptNum", "label": "GR Reference"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "branchName", "label": "Branch"},
            {"key": "warehouseName", "label": "Warehouse"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total Value", "numeric": True},
            {"key": "reason", "label": "Reason"},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "goods-delivery-return-report": {
        "title": "Goods Delivery Return Report",
        "title_id": "Laporan Retur Pengeluaran Barang",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "GOODS_DELIVERY_RETURN",
        "description": "Goods delivery return transactions",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "returnNum", "label": "Return Number"},
            {"key": "returnDate", "label": "Return Date"},
            {"key": "goodsDeliveryNum", "label": "GD Reference"},
            {"key": "branchName", "label": "Branch"},
            {"key": "destinationName", "label": "Destination"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total Value", "numeric": True},
            {"key": "reason", "label": "Reason"},
            {"key": "statusName", "label": "Status"},
            {"key": "notes", "label": "Notes"},
        ],
    },
    "bill-of-material-report": {
        "title": "Bill of Material Report",
        "title_id": "Laporan Bill of Material",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "BILL_OF_MATERIAL",
        "description": "BOM details",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "bomNum", "label": "BOM Number"},
            {"key": "bomDate", "label": "Date"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productName", "label": "Output Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "materialName", "label": "Material"},
            {"key": "materialCode", "label": "Material Code"},
            {"key": "materialUom", "label": "Material Unit"},
            {"key": "qty", "label": "Quantity", "numeric": True},
            {"key": "hpp", "label": "HPP", "numeric": True},
            {"key": "total", "label": "Total Value", "numeric": True},
            {"key": "statusName", "label": "Status"},
        ],
    },
    "purchase-order-actuation-report": {
        "title": "Purchase Order Actuation Report",
        "title_id": "Laporan Aktuasi Purchase Order",
        "category": "purchasing",
        "tier": "T1",
        "source": "trx",
        "entity": "PURCHASE_ORDER_ACTUATION",
        "description": "PO actuation tracking",
        "companies": [1, 2, 3, 4, 5, 6, 7, 8],
        "columns": [
            {"key": "actuationNum", "label": "Actuation Number"},
            {"key": "actuationDate", "label": "Date"},
            {"key": "purchaseOrderNum", "label": "PO Reference"},
            {"key": "supplierName", "label": "Supplier"},
            {"key": "branchName", "label": "Branch"},
            {"key": "productName", "label": "Product"},
            {"key": "productCode", "label": "Product Code"},
            {"key": "uomName", "label": "Unit"},
            {"key": "qtyOrder", "label": "Qty Order", "numeric": True},
            {"key": "qtyReceived", "label": "Qty Received", "numeric": True},
            {"key": "qtyInvoiced", "label": "Qty Invoiced", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "statusName", "label": "Status"},
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    # PRIORITY REPORTS (Sprint 4) - T2 Direct Reports from ESB
    # ─────────────────────────────────────────────────────────────────────────
    "sales-recapitulation-detail-report": {
        "title": "Sales Recapitulation Detail Report",
        "title_id": "Laporan Rekapitulasi Penjualan Detail",
        "category": "sales",
        "tier": "T1",
        # ERP-identical line-level view: report_pos_sales JOIN report_pos_sales_head
        "source": "table",
        "table": "v_sales_recap_detail",
        # view over report_pos_sales: catalog counts use the base table (much faster)
        "count_table": "report_pos_sales",
        "date_col": "sales_date",
        "branch_col": "branch_name",
        "order_col": "sales_date",
        "order_id_col": None,
        "description": "Sales Recapitulation Detail — line items joined with bill head (ERP column set)",
        "companies": [1],
        "columns": [
            {"key": "sales_num", "label": "Sales Number"},
            {"key": "bill_num", "label": "Bill Number"},
            {"key": "sales_type", "label": "Sales Type"},
            {"key": "batch_order", "label": "Batch Order"},
            {"key": "table_name", "label": "Table"},
            {"key": "sales_date", "label": "Sales Date"},
            {"key": "sales_date_in", "label": "Sales Date In"},
            {"key": "sales_date_out", "label": "Sales Date Out"},
            {"key": "branch_name", "label": "Branch"},
            {"key": "visit_purpose_name", "label": "Visit Purpose"},
            {"key": "regular_member_code", "label": "Member Code"},
            {"key": "regular_member_name", "label": "Member Name"},
            {"key": "payment_method", "label": "Payment Method"},
            {"key": "menu_category_name", "label": "Menu Category"},
            {"key": "menu_category_detail_name", "label": "Menu Category Detail"},
            {"key": "menu_name", "label": "Menu"},
            {"key": "menu_code", "label": "Menu Code"},
            {"key": "menu_notes", "label": "Menu Notes"},
            {"key": "order_mode", "label": "Order Mode"},
            {"key": "qty", "label": "Qty", "numeric": True},
            {"key": "price", "label": "Price", "numeric": True},
            {"key": "subtotal", "label": "Subtotal", "numeric": True},
            {"key": "discount_value", "label": "Discount", "numeric": True},
            {"key": "service_charge", "label": "Service Charge", "numeric": True},
            {"key": "tax", "label": "Tax", "numeric": True},
            {"key": "vat", "label": "VAT %", "numeric": True},
            {"key": "vat_amount", "label": "VAT Amount", "numeric": True},
            {"key": "other_tax_amount", "label": "Other Tax Amount", "numeric": True},
            {"key": "total", "label": "Total", "numeric": True},
            {"key": "nett_sales", "label": "Nett Sales", "numeric": True},
            {"key": "dpp", "label": "DPP", "numeric": True},
            {"key": "bill_discount", "label": "Bill Discount", "numeric": True},
            {"key": "total_after_bill_discount", "label": "Total After Bill Discount", "numeric": True},
            {"key": "waiter", "label": "Waiter"},
            {"key": "order_time", "label": "Order Time"},
            {"key": "status_name", "label": "Status"},
        ],
    },
}



def _flatten_row(header: dict, detail: dict, mapped: dict) -> dict:
    row = {**(header or {}), **(detail or {}), **mapped}
    for k in list(row.keys()):
        if isinstance(row[k], (list, dict)):
            del row[k]
    return row

def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return v


def _stock_opname_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                       date_from: date, date_to: date):
    """Explode header+details into report rows; category via product lookup map."""
    cur.execute("SELECT product_code, category_name, sub_category_name FROM md_products "
                "WHERE company_id = %s AND product_code IS NOT NULL AND product_code <> ''",
                (company_id,))
    prod_map = {r["product_code"]: (r["category_name"] or "", r["sub_category_name"] or "")
                for r in cur.fetchall()}

    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'STOCK_OPNAME'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("stockOpnameDetails") or []:
            stock_qty = _num(d.get("stockQty"))
            qty = _num(d.get("qty"))
            hpp = _num(d.get("hpp"))
            diff_qty = (qty - stock_qty) if (qty is not None and stock_qty is not None) else None
            diff_value = (diff_qty * hpp) if (diff_qty is not None and hpp is not None) else None
            cat, subcat = prod_map.get(d.get("productCode") or "", ("", ""))
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "stockOpnameNum": payload.get("stockOpnameNum"),
                "stockOpnameDate": str(payload.get("stockOpnameDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "locationName": payload.get("locationName"),
                "purposeName": payload.get("purposeName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "categoryName": cat,
                "subCategoryName": subcat,
                "uomName": d.get("uomName"),
                "stockQty": stock_qty,
                "qty": qty,
                "diffQty": diff_qty,
                "hpp": hpp,
                "diffValue": diff_value,
                "statusName": payload.get("statusName"),
                "additionalInfo": payload.get("additionalInfo"),
            }))
    return rows


def _fetch_trx_rows(cur, entity_type: str, company_id: int, branch_esb_id: typing.Optional[str],
                    date_from: date, date_to: date):
    """Generic transaction row fetcher for T1 reports."""
    sql = f"""
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = %s
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, entity_type, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _purchase_order_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                        date_from: date, date_to: date):
    """Fetch purchase order rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PURCHASE_ORDER'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("purchaseDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "purchaseOrderNum": payload.get("refNum") or payload.get("purchaseOrderNum"),
                "purchaseOrderDate": str(payload.get("purchaseOrderDate") or "")[:10],
                "supplierName": payload.get("supplierName"),
                "branchName": payload.get("branchName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "price": _num(d.get("price")),
                "discountPercent": _num(d.get("discountPercent")),
                "subTotal": _num(d.get("subTotal")),
                "taxPercent": _num(d.get("taxPercent")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _goods_receipt_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                        date_from: date, date_to: date):
    """Fetch goods receipt rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'GOODS_RECEIPT'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("goodsReceiptDetail") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "goodsReceiptNum": payload.get("goodsReceiptNum"),
                "goodsReceiptDate": str(payload.get("goodsReceiptDate") or "")[:10],
                "purchaseOrderNum": payload.get("refNum") or payload.get("purchaseOrderNum"),
                "supplierCode": payload.get("supplierCode"),
                "supplierName": payload.get("supplierName"),
                "branchCode": payload.get("branchCode"),
                "branchName": payload.get("branchName"),
                "warehouseName": payload.get("locationName") or payload.get("warehouseName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qtyOrder": _num(d.get("outstandingResult", {}).get("sumQty") if d.get("outstandingResult") else d.get("qtyOrder")),
                "qtyReceive": _num(d.get("qty")),
                "qtyReject": _num(d.get("deviationVal") or d.get("qtyReject")),
                "hpp": _num(d.get("hpp")),
                "totalReceive": _num(d.get("totalReceive")),
                "statusName": payload.get("statusName"),
            }))
    return rows


def _purchase_request_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                         date_from: date, date_to: date):
    """Fetch purchase request rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PURCHASE_REQUEST'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("purchaseRequestDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "purchaseRequestNum": payload.get("purchaseRequestNum"),
                "purchaseRequestDate": str(payload.get("purchaseRequestDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "departmentName": payload.get("departmentName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "estimatedPrice": _num(d.get("estimatedPrice")),
                "estimatedTotal": _num(d.get("estimatedTotal")),
                "purposeName": payload.get("purposeName"),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _goods_delivery_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                        date_from: date, date_to: date):
    """Fetch goods delivery rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'GOODS_DELIVERY'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("goodsDeliveryDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "goodsDeliveryNum": payload.get("goodsDeliveryNum"),
                "goodsDeliveryDate": str(payload.get("goodsDeliveryDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "destinationName": payload.get("destinationName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _manufacturing_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                       date_from: date, date_to: date):
    """Fetch manufacturing/production rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'SIMPLE_MANUFACTURING'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in [payload]:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "manufacturingNum": payload.get("bomCode") or payload.get("manufacturingNum"),
                "manufacturingDate": str(payload.get("createdDate") or payload.get("manufacturingDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "bomName": payload.get("bomName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "outputQty": _num(d.get("outputQty")),
                "hpp": _num(d.get("hpp")),
                "totalOutput": _num(d.get("totalOutput")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _disbursement_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                       date_from: date, date_to: date):
    """Fetch disbursement rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'DISBURSEMENT'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in [payload]:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "disbursementNum": payload.get("disbursementNum"),
                "disbursementDate": str(payload.get("disbursementDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "accountName": payload.get("coaDescription") or payload.get("accountName"),
                "paymentMethodName": payload.get("paymentMethodName"),
                "partnerName": payload.get("supplierName") or payload.get("partnerName"),
                "purposeName": d.get("purposeName"),
                "description": d.get("description"),
                "amount": _num(d.get("amount")),
                "coaNo": d.get("coaNo"),
                "statusName": payload.get("statusName"),
            }))
    return rows


def _receipt_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                  date_from: date, date_to: date):
    """Fetch receipt rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'RECEIPT'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("receiptDetail") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "receiptNum": payload.get("reference") or payload.get("receiptNum"),
                "receiptDate": str(payload.get("receiptDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "accountName": payload.get("coaDescription") or payload.get("accountName"),
                "paymentMethodName": payload.get("paymentMethodName"),
                "partnerName": payload.get("supplierName") or payload.get("partnerName"),
                "purposeName": d.get("purposeName"),
                "description": d.get("description"),
                "amount": _num(d.get("amount")),
                "coaNo": d.get("coaNo"),
                "statusName": payload.get("statusName"),
            }))
    return rows


def _advance_sales_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                        date_from: date, date_to: date):
    """Fetch advance sales rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'ADVANCE_SALES'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in [payload]:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "advanceSalesNum": payload.get("linkAdvancePaymentNum") or payload.get("productSalesNum") or payload.get("advanceSalesNum"),
                "advanceSalesDate": str(payload.get("createdDate") or payload.get("advanceSalesDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "customerName": payload.get("customerName"),
                "productName": d.get("productName"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "price": _num(d.get("price")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _memorial_journal_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                           date_from: date, date_to: date):
    """Fetch memorial journal rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'MEMORIAL_JOURNAL'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("memorialJournalDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "journalNum": payload.get("memorialJournalNum") or payload.get("journalNum"),
                "journalDate": str(payload.get("memorialJournalDate") or payload.get("journalDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "accountName": d.get("description") or d.get("coaDescription") or d.get("accountName"),
                "accountNo": d.get("coaNo") or d.get("accountNo"),
                "description": d.get("description"),
                "debit": _num(d.get("drAmount") or d.get("debit")),
                "credit": _num(d.get("crAmount") or d.get("credit")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _generic_trx_rows(cur, entity_type: str, company_id: int, branch_esb_id: typing.Optional[str],
                      date_from: date, date_to: date, row_extractor: typing.Callable):
    """Generic transaction row fetcher for common entities."""
    sql = f"""
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = %s
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, entity_type, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        details_key = entity_type.lower() + "Details"
        for d in payload.get(details_key) or []:
            rows.append(row_extractor(payload, d))
    return rows


def _transfer_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                  date_from: date, date_to: date):
    """Fetch transfer rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'TRANSFER'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("transferDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "transferNum": payload.get("transferNum"),
                "transferDate": str(payload.get("transferDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "sourceWarehouse": payload.get("sourceWarehouseName"),
                "destinationWarehouse": payload.get("destinationWarehouseName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _production_order_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                           date_from: date, date_to: date):
    """Fetch production order rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PRODUCTION_ORDER'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("productionOrderDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "productionOrderNum": payload.get("productionOrderNum"),
                "productionOrderDate": str(payload.get("productionOrderDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "dueDate": str(d.get("dueDate") or "")[:10],
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _production_material_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                             date_from: date, date_to: date):
    """Fetch production material rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PRODUCTION_MATERIAL'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("materialDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "materialIssueNum": payload.get("materialIssueNum"),
                "materialIssueDate": str(payload.get("materialIssueDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "productionOrderNum": payload.get("productionOrderNum"),
                "productName": payload.get("productName"),
                "materialName": d.get("materialName"),
                "materialCode": d.get("materialCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _sales_payment_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                        date_from: date, date_to: date):
    """Fetch sales payment rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'SALES_PAYMENT'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("paymentDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "paymentNum": payload.get("paymentNum"),
                "paymentDate": str(payload.get("paymentDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "salesNum": payload.get("salesNum"),
                "paymentMethodTypeName": d.get("paymentMethodTypeName"),
                "paymentMethodName": d.get("paymentMethodName"),
                "amount": _num(d.get("amount")),
                "cardNumber": d.get("cardNumber"),
                "cardHolder": d.get("cardHolder"),
                "approvalCode": d.get("approvalCode"),
                "statusName": payload.get("statusName"),
            }))
    return rows


def _product_sales_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                        date_from: date, date_to: date):
    """Fetch product sales rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PRODUCT_SALES'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("productSalesDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "salesNum": payload.get("productSalesNum"),
                "salesDate": str(payload.get("productSalesDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "customerName": payload.get("customerName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "price": _num(d.get("price")),
                "discountPercent": _num(d.get("discountPercent")),
                "subTotal": _num(d.get("subTotal")),
                "taxPercent": _num(d.get("taxPercent")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
            }))
    return rows


def _ar_suspense_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                       date_from: date, date_to: date):
    """Fetch AR suspense rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'AR_SUSPENSE'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("suspenseDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "suspenseNum": payload.get("suspenseNum"),
                "suspenseDate": str(payload.get("suspenseDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "customerName": payload.get("customerName"),
                "accountName": d.get("description") or d.get("coaDescription") or d.get("accountName"),
                "accountNo": d.get("coaNo") or d.get("accountNo"),
                "description": d.get("description"),
                "debit": _num(d.get("drAmount") or d.get("debit")),
                "credit": _num(d.get("crAmount") or d.get("credit")),
                "balance": _num(d.get("balance")),
                "dueDate": str(d.get("dueDate") or "")[:10],
                "statusName": payload.get("statusName"),
            }))
    return rows


def _ap_suspense_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                       date_from: date, date_to: date):
    """Fetch AP suspense rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'AP_SUSPENSE'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("suspenseDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "suspenseNum": payload.get("suspenseNum"),
                "suspenseDate": str(payload.get("suspenseDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "supplierName": payload.get("supplierName"),
                "accountName": d.get("description") or d.get("coaDescription") or d.get("accountName"),
                "accountNo": d.get("coaNo") or d.get("accountNo"),
                "description": d.get("description"),
                "debit": _num(d.get("drAmount") or d.get("debit")),
                "credit": _num(d.get("crAmount") or d.get("credit")),
                "balance": _num(d.get("balance")),
                "dueDate": str(d.get("dueDate") or "")[:10],
                "statusName": payload.get("statusName"),
            }))
    return rows


def _employee_advance_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                            date_from: date, date_to: date):
    """Fetch employee advance rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'EMPLOYEE_ADVANCE'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("advanceDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "advanceNum": payload.get("advanceNum"),
                "advanceDate": str(payload.get("advanceDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "employeeName": payload.get("employeeName"),
                "departmentName": payload.get("departmentName"),
                "purposeName": d.get("purposeName"),
                "description": d.get("description"),
                "amount": _num(d.get("amount")),
                "balance": _num(d.get("balance")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _budget_detail_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                         date_from: date, date_to: date):
    """Fetch budget detail rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'BUDGET_DETAIL'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("budgetDetails") or []:
            budget_amount = _num(d.get("budgetAmount"))
            realized_amount = _num(d.get("realizedAmount"))
            remaining = (budget_amount - realized_amount) if (budget_amount is not None and realized_amount is not None) else None
            pct_used = ((realized_amount / budget_amount * 100) if (budget_amount and realized_amount and budget_amount != 0) else None)
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "budgetNum": payload.get("budgetNum"),
                "budgetDate": str(payload.get("budgetDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "departmentName": payload.get("departmentName"),
                "accountName": d.get("description") or d.get("coaDescription") or d.get("accountName"),
                "accountNo": d.get("coaNo") or d.get("accountNo"),
                "periodName": d.get("periodName"),
                "budgetAmount": budget_amount,
                "realizedAmount": realized_amount,
                "remainingAmount": remaining,
                "percentageUsed": pct_used,
                "statusName": payload.get("statusName"),
            }))
    return rows


def _budget_revision_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                           date_from: date, date_to: date):
    """Fetch budget revision rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'BUDGET_REVISION'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("revisionDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "revisionNum": payload.get("revisionNum"),
                "revisionDate": str(payload.get("revisionDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "departmentName": payload.get("departmentName"),
                "accountName": d.get("description") or d.get("coaDescription") or d.get("accountName"),
                "periodName": d.get("periodName"),
                "previousAmount": _num(d.get("previousAmount")),
                "changeAmount": _num(d.get("changeAmount")),
                "newAmount": _num(d.get("newAmount")),
                "changeType": d.get("changeType"),
                "reason": d.get("reason"),
                "statusName": payload.get("statusName"),
            }))
    return rows




def _purchase_invoice_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                           date_from: date, date_to: date):
    """Fetch purchase invoice rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PURCHASE_INVOICE'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("invoiceDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "invoiceNum": payload.get("invoiceNum"),
                "invoiceDate": str(payload.get("invoiceDate") or "")[:10],
                "dueDate": str(payload.get("dueDate") or "")[:10],
                "supplierName": payload.get("supplierName"),
                "branchName": payload.get("branchName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "price": _num(d.get("price")),
                "discountPercent": _num(d.get("discountPercent")),
                "subTotal": _num(d.get("subTotal")),
                "taxPercent": _num(d.get("taxPercent")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _purchase_return_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                          date_from: date, date_to: date):
    """Fetch purchase return rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PURCHASE_RETURN'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("returnDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "returnNum": payload.get("returnNum"),
                "returnDate": str(payload.get("returnDate") or "")[:10],
                "invoiceNum": payload.get("invoiceNum"),
                "supplierName": payload.get("supplierName"),
                "branchName": payload.get("branchName"),
                "warehouseName": payload.get("locationName") or payload.get("warehouseName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "price": _num(d.get("price")),
                "total": _num(d.get("total")),
                "reason": d.get("reason"),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _goods_receipt_return_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                               date_from: date, date_to: date):
    """Fetch goods receipt return rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'GOODS_RECEIPT_RETURN'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("returnDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "returnNum": payload.get("returnNum"),
                "returnDate": str(payload.get("returnDate") or "")[:10],
                "goodsReceiptNum": payload.get("goodsReceiptNum"),
                "supplierName": payload.get("supplierName"),
                "branchName": payload.get("branchName"),
                "warehouseName": payload.get("locationName") or payload.get("warehouseName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "reason": d.get("reason"),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _goods_delivery_return_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                                 date_from: date, date_to: date):
    """Fetch goods delivery return rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'GOODS_DELIVERY_RETURN'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("returnDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "returnNum": payload.get("returnNum"),
                "returnDate": str(payload.get("returnDate") or "")[:10],
                "goodsDeliveryNum": payload.get("goodsDeliveryNum"),
                "branchName": payload.get("branchName"),
                "destinationName": payload.get("destinationName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "reason": d.get("reason"),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes") or payload.get("additionalInfo"),
            }))
    return rows


def _bill_of_material_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                            date_from: date, date_to: date):
    """Fetch BOM rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'BILL_OF_MATERIAL'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("bomDetails") or []:
            rows.append(_flatten_row(payload, locals().get('d', {}), {
                "bomNum": payload.get("bomNum"),
                "bomDate": str(payload.get("bomDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "productName": payload.get("productName"),
                "productCode": payload.get("productCode"),
                "uomName": payload.get("uomName"),
                "materialName": d.get("materialName"),
                "materialCode": d.get("materialCode"),
                "materialUom": d.get("materialUom"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
            }))
    return rows


def _advance_recap_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                        date_from: date, date_to: date):
    """Fetch advance recapitulation rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'ADVANCE_RECAP'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append(_flatten_row(payload, locals().get('d', {}), {
            "advanceNum": payload.get("advanceNum"),
            "advanceDate": str(payload.get("advanceDate") or "")[:10],
            "branchName": payload.get("branchName"),
            "employeeName": payload.get("employeeName"),
            "departmentName": payload.get("departmentName"),
            "purposeName": payload.get("purposeName"),
            "amount": _num(payload.get("grandTotal") or payload.get("amount")),
            "realizedAmount": _num(payload.get("realizedAmount")),
            "remainingAmount": _num(payload.get("remainingAmount")),
            "statusName": payload.get("statusName"),
            "notes": payload.get("notes") or payload.get("additionalInfo"),
        }))
    return rows


def _item_journal_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                       date_from: date, date_to: date):
    """Fetch item journal rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'ITEM_JOURNAL'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append(_flatten_row(payload, locals().get('d', {}), {
            "journalNum": payload.get("memorialJournalNum") or payload.get("journalNum"),
            "journalDate": str(payload.get("memorialJournalDate") or payload.get("journalDate") or "")[:10],
            "branchName": payload.get("branchName"),
            "productName": payload.get("productName"),
            "productCode": payload.get("productCode"),
            "uomName": payload.get("uomName"),
            "transactionType": payload.get("transactionType"),
            "inQty": _num(payload.get("inQty")),
            "outQty": _num(payload.get("outQty")),
            "balanceQty": _num(payload.get("balanceQty")),
            "hpp": _num(payload.get("hpp")),
            "reference": payload.get("reference"),
            "notes": payload.get("notes") or payload.get("additionalInfo"),
        }))
    return rows


def _product_sales_actuation_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                                  date_from: date, date_to: date):
    """Fetch product sales actuation rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PRODUCT_SALES_ACTUATION'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append(_flatten_row(payload, locals().get('d', {}), {
            "actuationNum": payload.get("actuationNum"),
            "actuationDate": str(payload.get("actuationDate") or "")[:10],
            "branchName": payload.get("branchName"),
            "productSalesNum": payload.get("productSalesNum"),
            "productName": payload.get("productName"),
            "productCode": payload.get("productCode"),
            "uomName": payload.get("uomName"),
            "qtyOrdered": _num(payload.get("qtyOrdered")),
            "qtyDelivered": _num(payload.get("qtyDelivered")),
            "qtyInvoiced": _num(payload.get("qtyInvoiced")),
            "price": _num(payload.get("price")),
            "total": _num(payload.get("total")),
            "statusName": payload.get("statusName"),
            "notes": payload.get("notes") or payload.get("additionalInfo"),
        }))
    return rows


def _purchase_invoice_payment_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                                   date_from: date, date_to: date):
    """Fetch purchase invoice payment rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PURCHASE_INVOICE_PAYMENT'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append(_flatten_row(payload, locals().get('d', {}), {
            "paymentNum": payload.get("paymentNum"),
            "paymentDate": str(payload.get("paymentDate") or "")[:10],
            "invoiceNum": payload.get("invoiceNum"),
            "supplierName": payload.get("supplierName"),
            "branchName": payload.get("branchName"),
            "accountName": payload.get("coaDescription") or payload.get("accountName"),
            "paymentMethodName": payload.get("paymentMethodName"),
            "amount": _num(payload.get("grandTotal") or payload.get("amount")),
            "reference": payload.get("reference"),
            "statusName": payload.get("statusName"),
            "notes": payload.get("notes") or payload.get("additionalInfo"),
        }))
    return rows


def _purchase_order_actuation_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                                    date_from: date, date_to: date):
    """Fetch purchase order actuation rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PURCHASE_ORDER_ACTUATION'
          AND t.doc_date BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append(_flatten_row(payload, locals().get('d', {}), {
            "actuationNum": payload.get("actuationNum"),
            "actuationDate": str(payload.get("actuationDate") or "")[:10],
            "purchaseOrderNum": payload.get("refNum") or payload.get("purchaseOrderNum"),
            "supplierName": payload.get("supplierName"),
            "branchName": payload.get("branchName"),
            "productName": payload.get("productName"),
            "productCode": payload.get("productCode"),
            "uomName": payload.get("uomName"),
            "qtyOrder": _num(payload.get("qtyOrder")),
            "qtyReceived": _num(payload.get("qtyReceived")),
            "qtyInvoiced": _num(payload.get("qtyInvoiced")),
            "price": _num(payload.get("price")),
            "total": _num(payload.get("total")),
            "statusName": payload.get("statusName"),
        }))
    return rows


# ─── T1 Row Fetcher Registry ───────────────────────────────────────────────────
TRX_ROW_FETCHERS = {
    "STOCK_OPNAME": _stock_opname_rows,
    "PURCHASE_ORDER": _purchase_order_rows,
    "GOODS_RECEIPT": _goods_receipt_rows,
    "PURCHASE_REQUEST": _purchase_request_rows,
    "GOODS_DELIVERY": _goods_delivery_rows,
    "SIMPLE_MANUFACTURING": _manufacturing_rows,
    "DISBURSEMENT": _disbursement_rows,
    "RECEIPT": _receipt_rows,
    "ADVANCE_SALES": _advance_sales_rows,
    "MEMORIAL_JOURNAL": _memorial_journal_rows,
    "TRANSFER": _transfer_rows,
    "PRODUCTION_ORDER": _production_order_rows,
    "PRODUCTION_MATERIAL": _production_material_rows,
    "SALES_PAYMENT": _sales_payment_rows,
    "PRODUCT_SALES": _product_sales_rows,
    "AR_SUSPENSE": _ar_suspense_rows,
    "AP_SUSPENSE": _ap_suspense_rows,
    "EMPLOYEE_ADVANCE": _employee_advance_rows,
    "BUDGET_DETAIL": _budget_detail_rows,
    "BUDGET_REVISION": _budget_revision_rows,
    "PURCHASE_INVOICE": _purchase_invoice_rows,
    "PURCHASE_RETURN": _purchase_return_rows,
    "GOODS_RECEIPT_RETURN": _goods_receipt_return_rows,
    "GOODS_DELIVERY_RETURN": _goods_delivery_return_rows,
    "BILL_OF_MATERIAL": _bill_of_material_rows,
    # Missing row fetchers added in Phase 4
    "ADVANCE_RECAP": _advance_recap_rows,
    "ITEM_JOURNAL": _item_journal_rows,
    "PRODUCT_SALES_ACTUATION": _product_sales_actuation_rows,
    "PURCHASE_INVOICE_PAYMENT": _purchase_invoice_payment_rows,
    "PURCHASE_ORDER_ACTUATION": _purchase_order_actuation_rows,
}


def _rpt_rows(cur, company_id: int, report_key: str, entity: str,
              branch_esb_id: typing.Optional[str], date_from: date, date_to: date):
    """Rows from report_raw_staging: one stored row per branch/day with lines[]."""
    sql = """
        SELECT raw_data FROM report_raw_staging
        WHERE company_id = %s AND report_type = %s AND period_start BETWEEN %s AND %s
    """
    params: typing.List[typing.Any] = [company_id, entity, date_from, date_to]
    if branch_esb_id:
        sql += " AND branch_esb_id = %s"
        params.append(branch_esb_id)
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["raw_data"] if isinstance(r["raw_data"], dict) else json.loads(r["raw_data"])
        for line in payload.get("lines") or []:
            line = dict(line)
            # sales-payment-summary: branch object with nested payments[] -> flatten
            if isinstance(line.get("payments"), list):
                for pay in line["payments"]:
                    flat = {**pay}
                    flat.setdefault("branchCode", line.get("branchCode"))
                    flat.setdefault("branchName", line.get("branchName"))
                    flat.setdefault("salesDate", line.get("salesDate") or payload.get("salesDate"))
                    rows.append(_flatten_row(payload, flat, {}))
                continue
            for k, v in list(line.items()):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    line[k] = _num(v)
            rows.append(_flatten_row(payload, line, {}))
    return rows


def _table_rows(cur, spec: dict, company_id: int, branch_esb_id: typing.Optional[str],
                date_from: date, date_to: date, limit: int, offset: int):
    """Direct SQL query against an esb_data table (source="table").
    Returns (rows, total). Uses keyset-friendly LIMIT/OFFSET in SQL."""
    table = spec["table"]
    date_col = spec.get("date_col", "sales_date")
    sql = f"SELECT * FROM esb_data.{table} WHERE company_id = %s AND {date_col}::date BETWEEN %s AND %s"
    params: typing.List[typing.Any] = [company_id, date_from, date_to]
    if branch_esb_id and spec.get("branch_col"):
        sql += f" AND {spec['branch_col']} = %s"
        params.append(branch_esb_id)
    cur.execute(f"SELECT COUNT(*) AS n FROM ({sql}) sub", params)
    row = cur.fetchone()
    total = row["n"] if isinstance(row, dict) else row[0]
    order = spec.get("order_col", date_col)
    if spec.get("order_id_col", "id"):
        order += f", {spec['order_id_col']} DESC"
    sql += f" ORDER BY {order} LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        d = dict(r) if not isinstance(r, dict) else r
        d.pop("raw_data", None)
        d.pop("id", None)
        for k, v in list(d.items()):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                d[k] = _num(v)
        rows.append(d)
    return rows, total


def run_report(slug: str, company_id: int, branch_esb_id: typing.Optional[str],
               date_from: date, date_to: date, limit: int = 500, offset: int = 0):
    """Returns {title, columns, rows, total}. Full rows (pre-pagination) are
    capped at 200k for safety; exports use generate_export instead."""
    spec = REPORTS.get(slug)
    if not spec:
        raise ValueError(f"Unknown report: {slug}")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if spec["source"] == "table":
            rows, total = _table_rows(cur, spec, company_id, branch_esb_id, date_from, date_to, limit, offset)
            return {"slug": slug, "title": spec["title"], "columns": spec["columns"],
                    "rows": rows, "total": total, "limit": limit, "offset": offset}
        if spec["source"] == "trx":
            entity = spec["entity"]
            fetcher = TRX_ROW_FETCHERS.get(entity)
            if fetcher:
                rows = fetcher(cur, company_id, branch_esb_id, date_from, date_to)
            else:
                rows = []
        else:
            rows = _rpt_rows(cur, company_id, slug, spec["entity"], branch_esb_id, date_from, date_to)
        total = len(rows)
        rows = rows[offset:offset + limit]
        return {"slug": slug, "title": spec["title"], "columns": spec["columns"],
                "rows": rows, "total": total, "limit": limit, "offset": offset}
    finally:
        cur.close()
        conn.close()


def iter_report_rows(slug: str, company_id: int, branch_esb_id: typing.Optional[str],
                     date_from: date, date_to: date):
    """Unpaginated row iterator for exports (count-free paged fetches)."""
    spec = REPORTS.get(slug)
    if not spec:
        raise ValueError(f"Unknown report: {slug}")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if spec["source"] == "table":
            table = spec["table"]
            date_col = spec.get("date_col", "sales_date")
            sql = (f"SELECT * FROM esb_data.{table} WHERE company_id = %s "
                   f"AND {date_col}::date BETWEEN %s AND %s")
            params: typing.List[typing.Any] = [company_id, date_from, date_to]
            if branch_esb_id and spec.get("branch_col"):
                sql += f" AND {spec['branch_col']} = %s"
                params.append(branch_esb_id)
            order = spec.get("order_col", date_col)
            cur.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_schema='esb_data' "
                "AND table_name=%s AND column_name='id'", (table,))
            if cur.fetchone():
                order += ", id"
            sql += f" ORDER BY {order} LIMIT %s OFFSET %s"
            page = 20000
            offset = 0
            while True:
                cur.execute(sql, params + [page, offset])
                rows = cur.fetchall()
                for r in rows:
                    d = dict(r) if not isinstance(r, dict) else r
                    d.pop("raw_data", None)
                    d.pop("id", None)
                    for k, v in list(d.items()):
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            d[k] = _num(v)
                    yield d
                if len(rows) < page:
                    break
                offset += page
            return
        if spec["source"] == "trx":
            entity = spec["entity"]
            fetcher = TRX_ROW_FETCHERS.get(entity)
            rows = fetcher(cur, company_id, branch_esb_id, date_from, date_to) if fetcher else []
        else:
            rows = _rpt_rows(cur, company_id, slug, spec["entity"], branch_esb_id, date_from, date_to)
        for row in rows:
            yield row
    finally:
        cur.close()
        conn.close()


def list_reports_by_category() -> dict:
    """Group all reports by their category."""
    result = {}
    for category, info in REPORT_CATEGORIES.items():
        result[category] = {
            **info,
            "reports": []
        }
    for slug, spec in REPORTS.items():
        cat = spec.get("category", "other")
        if cat in result:
            result[cat]["reports"].append({
                "slug": slug,
                "title": spec.get("title", slug),
                "title_id": spec.get("title_id", ""),
                "description": spec.get("description", ""),
                "tier": spec.get("tier", "T1"),
                "companies": spec.get("companies", []),
            })
    return result


_available_cache: dict = {}


def available_reports(company_id: int = 1) -> dict:
    """Catalog of ONLY reports that actually hold consumed data right now.

    For each REPORTS spec we count real rows in its backing store
    (esb_data table / trx_raw_staging / report_raw_staging) and drop
    every report with zero rows, so the FE menu never shows empty or
    aspirational entries. Lightly cached (60s) to spare the DB.
    """
    import time as _time
    now = _time.time()
    cached = _available_cache.get(company_id)
    if cached and now - cached["ts"] < 60:
        return cached["data"]

    conn = get_db_connection()
    cur = conn.cursor()
    out = []
    try:
        for slug, spec in REPORTS.items():
            if company_id not in (spec.get("companies") or [company_id]):
                continue
            try:
                if spec.get("source") == "table":
                    count_table = spec.get("count_table") or spec["table"]
                    cur.execute(
                        f"SELECT COUNT(*) AS n, MIN({spec['date_col']}::date)::text AS mn, "
                        f"MAX({spec['date_col']}::date)::text AS mx "
                        f"FROM esb_data.{count_table} WHERE company_id = %s", (company_id,))
                elif spec.get("source") == "trx":
                    cur.execute(
                        "SELECT COUNT(*) AS n, MIN(doc_date)::text AS mn, MAX(doc_date)::text AS mx "
                        "FROM trx_raw_staging WHERE company_id = %s AND entity_type = %s",
                        (company_id, spec["entity"]))
                else:
                    cur.execute(
                        "SELECT COUNT(*) AS n, MIN(period_start)::text AS mn, MAX(period_start)::text AS mx "
                        "FROM report_raw_staging WHERE company_id = %s AND report_type = %s",
                        (company_id, spec["entity"]))
                r = cur.fetchone()
                rows = r["n"] or 0
            except Exception:
                conn.rollback()
                continue
            if rows <= 0:
                continue
            out.append({
                "slug": slug,
                "title": spec.get("title", slug),
                "category": spec.get("category", "other"),
                "tier": spec.get("tier", "T1"),
                "source": spec.get("source", "staging"),
                "rows": rows,
                "date_from": r["mn"],
                "date_to": r["mx"],
                "columns": len(spec.get("columns", [])),
            })
        out.sort(key=lambda x: (-x["rows"], x["title"]))
        data = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "company_id": company_id,
            "reports": out,
            "total_rows": sum(d["rows"] for d in out),
        }
        _available_cache[company_id] = {"ts": now, "data": data}
        return data
    finally:
        cur.close()
        conn.close()


def list_reports_by_tier() -> dict:
    """Group all reports by their tier (T1 = direct trx, T2 = aggregated)."""
    result = {"T1": [], "T2": []}
    for slug, spec in REPORTS.items():
        tier = spec.get("tier", "T1")
        if tier in result:
            result[tier].append({
                "slug": slug,
                "title": spec.get("title", slug),
                "category": spec.get("category", ""),
                "companies": spec.get("companies", []),
            })
    return result


def get_report_metadata(slug: str) -> typing.Optional[dict]:
    """Get full metadata for a report including category info."""
    spec = REPORTS.get(slug)
    if not spec:
        return None
    cat = spec.get("category", "other")
    return {
        **spec,
        "category_info": REPORT_CATEGORIES.get(cat, {}),
    }


# ─────────────────────────────────────────────────────────────────────────
# esb_data.report_* sync (structured tables, Sprint: dynamic restructure)
# ─────────────────────────────────────────────────────────────────────────

import os
import math
import time
import httpx
from datetime import datetime, timedelta, timezone

from app.core.worker import celery_app

ESB_API_BASE_URL = os.getenv("ESB_CORE_URL", "https://services.esb.co.id/core")
ESB_FALLBACK_USERNAME = os.getenv("ESB_CORE_USERNAME", "CALFSUPERADMINOPS")
ESB_FALLBACK_PASSWORD = os.getenv("ESB_CORE_PASSWORD", "")
PAGE_SIZE = 100
PAGE_SLEEP_SECONDS = 0.2

# entity -> sync config for esb_data.report_* tables
REPORT_SYNC_CONFIG = {
    "RPT_GOODS_RECEIPT_RECAPITULATION": {
        "path": "/report/goods-receipt-recapitulation",
        "params_for": lambda d: {"dateFrom": d.isoformat(), "dateTo": d.isoformat()},
        "params_for_range": lambda s, e: {"dateFrom": s.isoformat(), "dateTo": e.isoformat()},
        "window_days": 2,
        "mode": "goods_receipt",
    },
    "RPT_SALES_PAYMENT_SUMMARY": {
        "path": "/report/sales-payment-summary",
        "params_for": lambda d: {"salesDate": d.isoformat()},
        "window_days": 2,
        "mode": "sales_payment",
    },
    "RPT_STOCK_MOVEMENT": {
        "path": "/report/stock-movement",
        "params_for": lambda d: {"startPeriod": d.isoformat(), "endPeriod": d.isoformat()},
        "window_days": 7,
        "mode": "stock_movement",
    },
    "RPT_SALES_RECAPITULATION_DETAIL": {
        "path": "/sales/product-sales",
        "params_for": lambda d: {"salesDate": d.isoformat()},
        "window_days": 2,
        "mode": "product_sales",
    },
}


def _report_iter_rows(client, cfg: dict, d: date):
    """Yield rows of a direct report for one date bucket (envelope-paginated)."""
    page = 1
    total_pages = 1
    while page <= total_pages:
        params = {"page": page, "limit": PAGE_SIZE}
        params.update(cfg["params_for"](d))
        body = client.get(cfg["path"], params=params)
        result = body.get("result")
        if isinstance(result, dict):
            rows = result.get("data") or []
            count = result.get("count", 0)
            total_pages = max(1, math.ceil((count or len(rows)) / PAGE_SIZE))
        else:
            rows = result or []
            total_pages = 1
        for r in rows:
            yield r
        page += 1
        time.sleep(PAGE_SLEEP_SECONDS)


def _resolve_branch_esb_id(cur, company_id: int, branch_name: typing.Optional[str]) -> typing.Optional[str]:
    if not branch_name:
        return None
    cur.execute(
        "SELECT esb_id FROM esb_data.master_branch WHERE company_id = %s AND name ILIKE %s LIMIT 1",
        (company_id, branch_name),
    )
    row = cur.fetchone()
    return row["esb_id"] if row else (branch_name[:50] if branch_name else None)


def _safe_date(v):
    """ESB sometimes returns dirty dates like '08-23-2026 (1,7900)'; keep only
    the leading parseable YYYY-MM-DD or MM-DD-YYYY portion, else None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    return None


def _sync_goods_receipt(cur, conn, company_id: int, d: date, rows: list) -> int:
    """Upsert line-level GR rows (one row per product line, matches ERP export)."""
    written = 0
    for r in rows:
        rd = r.get("goodsReceiptDate")
        num = r.get("goodsReceiptNum")
        if not (rd and num):
            continue
        cur.execute("""
            INSERT INTO esb_data.report_goods_receipt_recapitulation
            (company_id, report_date, receipt_number, receipt_date, reference_number,
             transaction_type, origin_name, origin_location, destination_name,
             destination_location, cost_center_name, project_name, category_name,
             sub_category_name, product_name, product_code, uom_name, qty,
             converted_qty, returned_qty, expired_date, status_name, additional_info,
             branch_name, raw_data, synced_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            ON CONFLICT (company_id, report_date, receipt_number, product_code, sub_category_name) DO UPDATE SET
                qty = EXCLUDED.qty, converted_qty = EXCLUDED.converted_qty,
                returned_qty = EXCLUDED.returned_qty, status_name = EXCLUDED.status_name,
                additional_info = EXCLUDED.additional_info, raw_data = EXCLUDED.raw_data,
                updated_at = NOW()
        """, (
            company_id, rd, num, rd, r.get("refNum"),
            r.get("transType"), r.get("originName"), r.get("originLocation"),
            r.get("branchName"), r.get("destinationLocation"), r.get("costCenterName"),
            r.get("projectName"), r.get("categoryName"), r.get("subCategoryName"),
            r.get("productName"), r.get("productCode"), r.get("uomName"),
            r.get("qty") or 0, r.get("convertedQty") or 0, r.get("returnedQty") or 0,
            _safe_date(r.get("expiredDate")), r.get("statusName"), r.get("additionalInfo"),
            r.get("branchName"), json.dumps(r, default=str),
        ))
        written += 1
    conn.commit()
    return written


def _sync_sales_payment(cur, conn, company_id: int, d: date, rows: list) -> int:
    """Flatten per-branch rows with nested payments[] into payment-method rows."""
    written = 0
    for r in rows:
        rd = r.get("salesDate") or d.isoformat()
        branch_esb_id = r.get("branchCode")
        branch_name = r.get("branchName")
        # replace-existing semantics keeps re-runs idempotent (table has no unique key)
        cur.execute(
            "DELETE FROM esb_data.report_sales_payment_summary WHERE company_id = %s AND report_date = %s AND branch_esb_id = %s",
            (company_id, rd, branch_esb_id),
        )
        for p in r.get("payments") or []:
            cur.execute("""
                INSERT INTO esb_data.report_sales_payment_summary
                (company_id, report_date, branch_esb_id, branch_name, payment_method_type,
                 payment_method_name, transaction_type, payment_count, payment_amount, mdr,
                 net_after_mdr, raw_data, synced_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                company_id, rd, branch_esb_id, branch_name,
                p.get("paymentMethodTypeName"), p.get("paymentMethodName"),
                p.get("paymentCount") or 0, p.get("paymentAmount") or 0,
                p.get("mdr") or 0, p.get("netAfterMDR") or 0,
                json.dumps(p, default=str),
            ))
            written += 1
    conn.commit()
    return written


def _sync_stock_movement(cur, conn, company_id: int, d: date, rows: list) -> int:
    """Insert line-level stock movement rows (replace per company+date+product)."""
    written = 0
    for r in rows:
        rd = r.get("documentDate") or d.isoformat()
        cur.execute("""
            INSERT INTO esb_data.report_stock_movement
            (company_id, report_date, branch_esb_id, product_code, product_name, branch_name,
             location, uom_name, transaction_type, reference_number, document_code, document_date,
             value_per_unit, qty_in, amount_in, qty_out, amount_out, qty_balance, amount_balance,
             raw_data, synced_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            company_id, rd, str(r.get("branchID") or r.get("branchCode") or ""),
            r.get("productCode"), r.get("productName"), r.get("branchName"),
            r.get("location"), r.get("uomName"), r.get("transactionType"),
            r.get("referenceNumber"), r.get("documentCode"), rd,
            r.get("valuePerUnit") or 0, r.get("qtyIn") or 0, r.get("amountIn") or 0,
            r.get("qtyOut") or 0, r.get("amountOut") or 0, r.get("qtyBalance") or 0,
            r.get("amountBalance") or 0, json.dumps(r, default=str),
        ))
        written += 1
    conn.commit()
    return written


def _sync_product_sales(cur, conn, company_id: int, d: date, rows: list) -> int:
    """Upsert product-sales transaction headers into report_sales_recapitulation_detail."""
    written = 0
    for r in rows:
        rd = r.get("productSalesDate")
        if not (rd and r.get("productSalesNum")):
            continue
        cur.execute("""
            INSERT INTO esb_data.report_sales_recapitulation_detail
            (company_id, report_date, branch_esb_id, transaction_number, transaction_date,
             branch_name, customer_name, customer_code, salesperson_name, total_amount,
             item_count, status, status_name, order_type, notes, created_by, approved_by,
             approved_date, raw_data, synced_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (company_id, report_date, branch_esb_id, transaction_number) DO UPDATE SET
                branch_name = EXCLUDED.branch_name,
                customer_name = EXCLUDED.customer_name,
                salesperson_name = EXCLUDED.salesperson_name,
                total_amount = EXCLUDED.total_amount,
                item_count = EXCLUDED.item_count,
                status = EXCLUDED.status,
                status_name = EXCLUDED.status_name,
                order_type = EXCLUDED.order_type,
                raw_data = EXCLUDED.raw_data,
                updated_at = NOW()
        """, (
            company_id, rd, str(r.get("branchID") or ""),
            r["productSalesNum"], rd, r.get("branchName"),
            r.get("customerName"), str(r.get("customerID") or ""),
            r.get("salesRepName"), r.get("productSalesTotal") or 0,
            len(r.get("productSalesDetails") or []),
            str(r.get("statusID") or ""), r.get("printData", {}).get("statusName") if isinstance(r.get("printData"), dict) else None,
            r.get("productSalesTypeName"), r.get("additionalInfo"),
            r.get("createdBy"), r.get("authorizedBy"), r.get("authorizedDate"),
            json.dumps(r, default=str),
        ))
        written += 1
    conn.commit()
    return written


_SYNC_MODES = {
    "goods_receipt": _sync_goods_receipt,
    "sales_payment": _sync_sales_payment,
    "stock_movement": _sync_stock_movement,
    "product_sales": _sync_product_sales,
}


@celery_app.task(name="app.services.reports.sync_sales_recap_detail")
def sync_sales_recap_detail(company_id: int = None):
    """Transform staged PRODUCT_SALES payloads (trx_raw_staging) into the
    structured esb_data.report_sales_recapitulation_detail table.

    Idempotent: upserts on (company_id, report_date, branch_esb_id, transaction_number).
    This avoids re-pulling slow ESB endpoints for data already staged by the TRX lane.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM public.trx_raw_staging WHERE entity_type = 'PRODUCT_SALES'")
        staged = cur.fetchone()["count"]
        cur.execute("""
            INSERT INTO esb_data.report_sales_recapitulation_detail
            (company_id, report_date, branch_esb_id, transaction_number, transaction_date,
             branch_name, customer_name, customer_code, salesperson_name, total_amount,
             item_count, status, status_name, order_type, notes, created_by, approved_by,
             approved_date, raw_data, synced_at, updated_at)
            SELECT
                s.company_id,
                (s.payload->>'productSalesDate')::date,
                (s.payload->>'branchID')::text,
                s.payload->>'productSalesNum',
                (s.payload->>'productSalesDate')::date,
                s.payload->>'branchName',
                s.payload->>'customerName',
                (s.payload->>'customerID')::text,
                s.payload->>'salesRepName',
                COALESCE((s.payload->>'productSalesTotal')::numeric, 0),
                COALESCE(jsonb_array_length(s.payload->'productSalesDetails'), 0),
                (s.payload->>'statusID')::text,
                s.payload->'printData'->>'statusName',
                s.payload->>'productSalesTypeName',
                s.payload->>'additionalInfo',
                s.payload->>'createdBy',
                s.payload->>'authorizedBy',
                (s.payload->>'authorizedDate')::date,
                s.payload,
                s.synced_at,
                NOW()
            FROM public.trx_raw_staging s
            WHERE s.entity_type = 'PRODUCT_SALES'
              AND (s.company_id = %s OR %s IS NULL)
            ON CONFLICT (company_id, report_date, branch_esb_id, transaction_number) DO UPDATE SET
                branch_name = EXCLUDED.branch_name,
                customer_name = EXCLUDED.customer_name,
                salesperson_name = EXCLUDED.salesperson_name,
                total_amount = EXCLUDED.total_amount,
                item_count = EXCLUDED.item_count,
                status = EXCLUDED.status,
                status_name = EXCLUDED.status_name,
                order_type = EXCLUDED.order_type,
                raw_data = EXCLUDED.raw_data,
                updated_at = NOW()
        """, (company_id, company_id))
        written = cur.rowcount
        conn.commit()
        return {"staged": staged, "upserted": written}
    finally:
        cur.close()
        conn.close()


@celery_app.task(name="app.services.reports.sync_report")
def sync_report(report_type: str, company_id: int, date_from: str = None,
                date_to: str = None, branch_esb_id: str = None, static_token: str = None):
    """Pull a direct report from ESB into the structured esb_data.report_* table.

    report_type is an endpoint_registry entity (e.g. RPT_GOODS_RECEIPT_RECAPITULATION).
    Default window is the entity's configured trailing window ending today.
    """
    cfg = REPORT_SYNC_CONFIG.get(report_type)
    if not cfg:
        return f"No sync config for {report_type}"
    writer = _SYNC_MODES[cfg["mode"]]

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, esb_company_code, esb_username, esb_password, static_token FROM esb_data.company_configs WHERE id = %s",
            (company_id,))
        co = cur.fetchone()
        if not co:
            return f"Company {company_id} not found"
        code = co["esb_company_code"]
        username = co["esb_username"] or ESB_FALLBACK_USERNAME
        password = co["esb_password"] or ESB_FALLBACK_PASSWORD
        token = static_token or co["static_token"]
        if token:
            print(f"Using static token for {code}")
        else:
            if not (username and password):
                return f"{code}: no credentials"
            try:
                from app.services.trx_engine import _auth_locked_company_token
                token = _auth_locked_company_token(code, username, password)
            except Exception as e:
                return f"{code}: auth failed {str(e)[:120]}"

        from app.services.tasks import ESBClient
        client = ESBClient(token, code, username, password)

        cur.execute(
            "INSERT INTO sync_history (entity_type, status, company_id) VALUES (%s, %s, %s) RETURNING id",
            (report_type, "STARTED", company_id))
        history_id = cur.fetchone()["id"]
        conn.commit()

        end_d = date.fromisoformat(date_to) if date_to else date.today()
        start_d = date.fromisoformat(date_from) if date_from else end_d - timedelta(days=cfg["window_days"])
        pulled, written, has_error, err = 0, 0, False, ""

        if "params_for_range" in cfg:
            # Single paginated pull over the whole range (backfill-friendly),
            # written and committed incrementally per page so a dropped DB
            # connection cannot lose the whole chunk.
            page, total_pages = 1, 1
            try:
                while page <= total_pages:
                    params = {"page": page, "limit": PAGE_SIZE}
                    params.update(cfg["params_for_range"](start_d, end_d))
                    body = client.get(cfg["path"], params=params)
                    result = body.get("result")
                    if isinstance(result, dict):
                        batch = result.get("data") or []
                        count = result.get("count", 0)
                        total_pages = max(1, math.ceil((count or len(batch)) / PAGE_SIZE))
                    else:
                        batch = result or []
                        total_pages = 1
                    pulled += len(batch)
                    try:
                        written += writer(cur, conn, company_id, end_d, batch)
                    except Exception:
                        conn.rollback()
                        raise
                    page += 1
                    time.sleep(PAGE_SLEEP_SECONDS)
            except Exception as e:
                has_error, err = True, str(e)[:200]
                try:
                    conn.rollback()
                except Exception:
                    pass
        else:
            d = start_d
            while d <= end_d:
                try:
                    rows = list(_report_iter_rows(client, cfg, d))
                except Exception as e:
                    has_error, err = True, str(e)[:200]
                    break
                pulled += len(rows)
                written += writer(cur, conn, company_id, d, rows)
                d += timedelta(days=1)

        cur.execute(
            "UPDATE sync_history SET status=%s, records_processed=%s, error_message=%s, completed_at=%s WHERE id=%s",
            ("FAILED" if has_error else "SUCCESS", written, err, datetime.now(timezone.utc), history_id))
        conn.commit()
        return {code: {report_type: written if not has_error else f"ERROR {err}"}}
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# POS sales sync via ESB OMS gateway (esbcore.co.id, Basic auth)
# Source of the ERP "Sales Recapitulation Detail Report" (line-level POS)
# ─────────────────────────────────────────────────────────────────────────

OMS_BASE_URL = os.getenv("OMS_API_URL", "https://esbcore.co.id")
OMS_USERNAME = os.getenv("OMS_API_USERNAME", ESB_FALLBACK_USERNAME)
OMS_PASSWORD = os.getenv("OMS_API_PASSWORD", ESB_FALLBACK_PASSWORD)
OMS_PAGE_SIZE = 50  # server caps per-page at 50 (asking 100 silently returns 50)


class OMSClient:
    """Client for the OMS external/general endpoints (Basic auth, header pagination)."""

    def __init__(self, username: str, password: str):
        import base64
        cred = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._http = httpx.Client(
            timeout=60.0,
            headers={"Authorization": f"Basic {cred}", "Content-Type": "application/json",
                     "Accept": "application/json"},
        )

    def post(self, path: str, body: dict, page: int = 1):
        last_exc = None
        for attempt in range(7):
            try:
                r = self._http.post(f"{OMS_BASE_URL}{path}",
                                    params={"page": page, "per-page": OMS_PAGE_SIZE}, json=body)
                if r.status_code == 401:
                    # OMS throttles concurrent load from one account with 401s;
                    # back off and retry before giving up
                    time.sleep(min(120, 15 * (attempt + 1)))
                    continue
                if r.status_code >= 400:
                    raise RuntimeError(f"OMS error {r.status_code}: {r.text[:150]}")
                rows = r.json() if r.text.strip() else []
                total_pages = int(r.headers.get("x-pagination-page-count", 1) or 1)
                return rows, total_pages
            except RuntimeError:
                raise
            except Exception as e:
                last_exc = e
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"OMS unauthorized: check OMS_API_USERNAME/OMS_API_PASSWORD (needs External API access) after retries: {str(last_exc)[:120]}")

    def iter_all(self, path: str, body: dict):
        page, total_pages = 1, 1
        while page <= total_pages:
            rows, total_pages = self.post(path, body, page)
            for r in rows:
                yield r
            page += 1
            time.sleep(PAGE_SLEEP_SECONDS)


def _oms_body(date_from: str, date_to: str) -> dict:
    return {"filterSalesDateFrom": date_from, "filterSalesDateTo": date_to}


def _upsert_pos_head(cur, company_id: int, r: dict):
    cur.execute("""
        INSERT INTO esb_data.report_pos_sales_head
        (company_id, sales_num, parent_link_sales_num, bill_num, sales_date, sales_date_in,
         sales_date_out, branch_code, branch_name, member_code, member_name, table_name,
         visit_purpose_name, pax_total, subtotal, discount_total, menu_discount_total,
         promotion_discount, other_tax_total, vat_total, grand_total, voucher_total,
         rounding_total, payment_total, status_id, status_name, created_by, payments,
         raw_data, synced_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
        ON CONFLICT (company_id, sales_num) DO UPDATE SET
            grand_total = EXCLUDED.grand_total, payment_total = EXCLUDED.payment_total,
            status_id = EXCLUDED.status_id, status_name = EXCLUDED.status_name,
            payments = EXCLUDED.payments, raw_data = EXCLUDED.raw_data, updated_at = NOW()
    """, (
        company_id, r.get("salesNum"), r.get("parentLinkSalesNum"), r.get("billNum"),
        r.get("salesDate"), r.get("salesDateIn"), r.get("salesDateOut"),
        r.get("branchCode"), r.get("branchName"), r.get("memberCode"), r.get("memberName"),
        r.get("tableName"), r.get("visitPurposeName"), r.get("paxTotal"),
        r.get("subtotal") or 0, r.get("discountTotal") or 0, r.get("menuDiscountTotal") or 0,
        r.get("promotionDiscount") or 0, r.get("otherTaxTotal") or 0, r.get("vatTotal") or 0,
        r.get("grandTotal") or 0, r.get("voucherTotal") or 0, r.get("roundingTotal") or 0,
        r.get("paymentTotal") or 0, r.get("statusID"), r.get("statusName"),
        r.get("createdBy"), json.dumps(r.get("salesPayments") or [], default=str),
        json.dumps(r, default=str),
    ))


def _insert_pos_sales_line(cur, company_id: int, r: dict):
    """Upsert a single POS sales line — NO delete, safe for partial API failures."""
    cur.execute("""
        INSERT INTO esb_data.report_pos_sales
        (company_id, sales_num, bill_num, sales_date, branch_code, branch_name, batch_id,
         menu_code, menu_name, menu_category_name, menu_category_detail_name, qty, price,
         original_price, discount, discount_value, subtotal, other_tax, service_charge,
         tax, vat, total, notes, cancel_notes, status_id, status_name, created_by,
         created_date, extras, raw_data, synced_at, updated_at, id_esb)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW(),%s)
        ON CONFLICT (company_id, sales_num, menu_code, menu_category_detail_name, id_esb)
        DO UPDATE SET synced_at = NOW(), updated_at = NOW()
    """, (
        company_id, r.get("salesNum"), r.get("billNum"), r.get("salesDate"),
        r.get("branchCode"), r.get("branchName"), r.get("batchID"),
        r.get("menuCode"), r.get("menuName"), r.get("menuCategoryName"),
        r.get("menuCategoryDetailName"), r.get("qty") or 0, r.get("price") or 0,
        r.get("originalPrice") or 0, r.get("discount") or 0, r.get("discountValue") or 0,
        r.get("subTotal") or 0, r.get("otherTax") or 0, r.get("serviceCharge") or 0,
        r.get("tax") or 0, r.get("vat") or 0, r.get("total") or 0,
        r.get("notes"), r.get("cancelNotes"), r.get("statusID"), r.get("statusName"),
        r.get("createdBy"), r.get("createdDate"),
        json.dumps(r.get("extras") or [], default=str), json.dumps(r, default=str),
        r.get("ID") or r.get("id"),
    ))


def _insert_pos_package_line(cur, company_id: int, parent: dict, p: dict):
    """Explode a menu-line package/modifier into its own row, mirroring the ERP
    'Sales Recapitulation Detail Report' EXTRA lines ('<Menu> (PACKAGE)').
    Uses UPSERT — no delete, safe for partial API failures."""
    raw = {**p,
           "salesNum": parent.get("salesNum"), "billNum": parent.get("billNum"),
           "salesDate": parent.get("salesDate"), "salesType": parent.get("salesType"),
           "branchCode": parent.get("branchCode"), "branchName": parent.get("branchName"),
           "createdDate": parent.get("createdDate")}
    qty = p.get("qty") or 0
    price = p.get("price") or 0
    cur.execute("""
        INSERT INTO esb_data.report_pos_sales
        (company_id, sales_num, bill_num, sales_date, branch_code, branch_name, batch_id,
         menu_code, menu_name, menu_category_name, menu_category_detail_name, qty, price,
         original_price, discount, discount_value, subtotal, other_tax, service_charge,
         tax, vat, total, notes, cancel_notes, status_id, status_name, created_by,
         created_date, extras, raw_data, synced_at, updated_at, id_esb)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'EXTRA',NULL,%s,%s,%s,%s,0,%s,%s,0,0,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW(),NULL)
        ON CONFLICT (company_id, sales_num, menu_code, menu_category_detail_name, id_esb)
        DO UPDATE SET synced_at = NOW(), updated_at = NOW()
    """, (
        company_id, parent.get("salesNum"), parent.get("billNum"), parent.get("salesDate"),
        parent.get("branchCode"), parent.get("branchName"), parent.get("batchID"),
        p.get("menuCode") or "", f"{p.get('menuName') or ''} (PACKAGE)",
        qty, price, p.get("originalPrice") or 0, p.get("discount") or 0,
        (price * qty) if (price and qty) else 0,
        p.get("otherTax") or 0, p.get("vat") or 0, p.get("total") or 0,
        p.get("notes"), None, p.get("statusID"), p.get("statusName"),
        parent.get("createdBy"), parent.get("createdDate"),
        "[]", json.dumps(raw, default=str),
    ))


def _flush_batch(cur, sql: str, tuples: list):
    """One round-trip multi-row INSERT via execute_values (page-sized batches)."""
    if not tuples:
        return
    from psycopg2.extras import execute_values
    execute_values(cur, sql, tuples, page_size=200)


def _head_tuple(company_id: int, r: dict) -> tuple:
    return (
        company_id, r.get("salesNum"), r.get("parentLinkSalesNum"), r.get("billNum"),
        r.get("salesDate"), r.get("salesDateIn"), r.get("salesDateOut"),
        r.get("branchCode"), r.get("branchName"), r.get("memberCode"), r.get("memberName"),
        r.get("tableName"), r.get("visitPurposeName"), r.get("paxTotal"),
        r.get("subtotal") or 0, r.get("discountTotal") or 0, r.get("menuDiscountTotal") or 0,
        r.get("promotionDiscount") or 0, r.get("otherTaxTotal") or 0, r.get("vatTotal") or 0,
        r.get("grandTotal") or 0, r.get("voucherTotal") or 0, r.get("roundingTotal") or 0,
        r.get("paymentTotal") or 0, r.get("statusID"), r.get("statusName"),
        r.get("createdBy"), json.dumps(r.get("salesPayments") or [], default=str),
        json.dumps(r, default=str),
    )


def _line_tuple(company_id: int, r: dict) -> tuple:
    return (
        company_id, r.get("salesNum"), r.get("billNum"), r.get("salesDate"),
        r.get("branchCode"), r.get("branchName"), r.get("batchID"),
        r.get("menuCode"), r.get("menuName"), r.get("menuCategoryName"),
        r.get("menuCategoryDetailName"), r.get("qty") or 0, r.get("price") or 0,
        r.get("originalPrice") or 0, r.get("discount") or 0, r.get("discountValue") or 0,
        r.get("subTotal") or 0, r.get("otherTax") or 0, r.get("serviceCharge") or 0,
        r.get("tax") or 0, r.get("vat") or 0, r.get("total") or 0,
        r.get("notes"), r.get("cancelNotes"), r.get("statusID"), r.get("statusName"),
        r.get("createdBy"), r.get("createdDate"),
        json.dumps(r.get("extras") or [], default=str), json.dumps(r, default=str),
        r.get("ID") or r.get("id"),
    )


def _package_tuple(company_id: int, parent: dict, p: dict) -> tuple:
    qty = p.get("qty") or 0
    price = p.get("price") or 0
    raw = {**p,
           "salesNum": parent.get("salesNum"), "billNum": parent.get("billNum"),
           "salesDate": parent.get("salesDate"), "salesType": parent.get("salesType"),
           "branchCode": parent.get("branchCode"), "branchName": parent.get("branchName"),
           "createdDate": parent.get("createdDate")}
    return (
        company_id, parent.get("salesNum"), parent.get("billNum"), parent.get("salesDate"),
        parent.get("branchCode"), parent.get("branchName"), parent.get("batchID"),
        p.get("menuCode") or "", f"{p.get('menuName') or ''} (PACKAGE)",
        qty, price, p.get("originalPrice") or 0, p.get("discount") or 0,
        (price * qty) if (price and qty) else 0,
        p.get("otherTax") or 0, p.get("vat") or 0, p.get("total") or 0,
        p.get("notes"), None, p.get("statusID"), p.get("statusName"),
        parent.get("createdBy"), parent.get("createdDate"),
        "[]", json.dumps(raw, default=str),
    )


HEAD_BATCH_SQL = """
    INSERT INTO esb_data.report_pos_sales_head
    (company_id, sales_num, parent_link_sales_num, bill_num, sales_date, sales_date_in,
     sales_date_out, branch_code, branch_name, member_code, member_name, table_name,
     visit_purpose_name, pax_total, subtotal, discount_total, menu_discount_total,
     promotion_discount, other_tax_total, vat_total, grand_total, voucher_total,
     rounding_total, payment_total, status_id, status_name, created_by, payments,
     raw_data, synced_at, updated_at)
    VALUES %s
    ON CONFLICT (company_id, sales_num) DO UPDATE SET
     grand_total=EXCLUDED.grand_total, payment_total=EXCLUDED.payment_total,
     status_id=EXCLUDED.status_id, status_name=EXCLUDED.status_name,
     payments=EXCLUDED.payments, raw_data=EXCLUDED.raw_data, updated_at=NOW()
"""

LINE_BATCH_SQL = """
    INSERT INTO esb_data.report_pos_sales
    (company_id, sales_num, bill_num, sales_date, branch_code, branch_name, batch_id,
     menu_code, menu_name, menu_category_name, menu_category_detail_name, qty, price,
     original_price, discount, discount_value, subtotal, other_tax, service_charge,
     tax, vat, total, notes, cancel_notes, status_id, status_name, created_by,
     created_date, extras, raw_data, synced_at, updated_at, id_esb)
    VALUES %s
    ON CONFLICT (company_id, sales_num, menu_code, menu_category_detail_name, id_esb)
    DO UPDATE SET synced_at = NOW(), updated_at = NOW()
"""

PKG_BATCH_SQL = """
    INSERT INTO esb_data.report_pos_sales
    (company_id, sales_num, bill_num, sales_date, branch_code, branch_name, batch_id,
     menu_code, menu_name, menu_category_name, menu_category_detail_name, qty, price,
     original_price, discount, discount_value, subtotal, other_tax, service_charge,
     tax, vat, total, notes, cancel_notes, status_id, status_name, created_by,
     created_date, extras, raw_data, synced_at, updated_at, id_esb)
    VALUES %s
    ON CONFLICT (company_id, sales_num, menu_code, menu_category_detail_name, id_esb)
    DO UPDATE SET synced_at = NOW(), updated_at = NOW()
"""


@celery_app.task(name="app.services.reports.sync_pos_sales")
def sync_pos_sales(company_id: int, date_from: str = None, date_to: str = None):
    """Pull POS sales (head + menu lines) from the OMS gateway for a date range
    into esb_data.report_pos_sales_head / report_pos_sales (line-level, matches
    the ERP 'Sales Recapitulation Detail Report' export).

    Uses UPSERT (ON CONFLICT DO UPDATE) instead of DELETE + INSERT.
    This means:
    - Existing rows are never deleted during sync (no data loss)
    - Re-runs of the same day are safe and idempotent
    - API failures mid-day do NOT cause data loss — rows stay intact
    - Completeness audit: after each day, verify API head count matches DB count
      and trigger a retry if mismatched (up to 3 audit retries per day)

    Each package/modifier is exploded into its own 'EXTRA' row
    ('<Menu> (PACKAGE)') exactly like the ERP export."""
    lock_key = f"sync_pos_sales:{company_id}:{date_from}:{date_to}"
    lock_conn = get_db_connection()
    try:
        lock_cur = lock_conn.cursor()
        lock_cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (lock_key,))
        if not lock_cur.fetchone()["pg_try_advisory_lock"]:
            return f"skipped: another sync_pos_sales for {lock_key} is running"
    except Exception:
        lock_conn.close()
        raise

    conn = lock_conn
    cur = conn.cursor()
    history_id = None
    try:
        client = OMSClient(OMS_USERNAME, OMS_PASSWORD)

        cur.execute(
            "INSERT INTO sync_history (entity_type, status, company_id) VALUES (%s, %s, %s) RETURNING id",
            ("POS_SALES", "STARTED", company_id))
        history_id = cur.fetchone()["id"]
        conn.commit()

        end_d = date.fromisoformat(date_to) if date_to else date.today()
        start_d = date.fromisoformat(date_from) if date_from else end_d - timedelta(days=1)

        heads, lines, has_error, err = 0, 0, False, ""
        d = start_d
        while d <= end_d:
            # fresh DB connection per day: pooler drops long-lived idle conns
            try:
                conn.close()
            except Exception:
                pass
            conn = get_db_connection()
            cur = conn.cursor()
            body = _oms_body(d.isoformat(), d.isoformat())
            day_heads, day_lines = 0, 0
            day_ok, day_err = False, ""
            for attempt in range(3):
                try:
                    # fresh connection each attempt: pooler may have dropped it
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = get_db_connection()
                    cur = conn.cursor()

                    # ── UPSERT (no DELETE): safe for partial failures ─────────────
                    # Heads
                    for r in client.iter_all("/external/general/sales-head", body):
                        _upsert_pos_head(cur, company_id, r)
                        day_heads += 1
                        if day_heads % 2000 == 0:
                            conn.commit()
                    conn.commit()

                    # Lines
                    for r in client.iter_all("/external/general/sales-menu", body):
                        _insert_pos_sales_line(cur, company_id, r)
                        day_lines += 1
                        for p in r.get("packages") or []:
                            _insert_pos_package_line(cur, company_id, r, p)
                            day_lines += 1
                        if day_lines % 2000 == 0:
                            conn.commit()
                    conn.commit()

                    # ── Completeness audit ───────────────────────────────────────
                    # Check if DB row count matches what we received from API
                    cur.execute("""
                        SELECT
                            (SELECT count(*) FROM esb_data.report_pos_sales_head
                             WHERE company_id=%s AND sales_date=%s) AS db_heads,
                            (SELECT count(*) FROM esb_data.report_pos_sales
                             WHERE company_id=%s AND sales_date=%s) AS db_lines
                    """, (company_id, d.isoformat(), company_id, d.isoformat()))
                    audit_row = cur.fetchone()
                    db_heads, db_lines = audit_row[0], audit_row[1]

                    # Allow up to 1% discrepancy (handles cancelled/voided orders)
                    head_ok = db_heads >= day_heads * 0.99 if day_heads > 0 else db_heads == 0
                    line_ok = db_lines >= day_lines * 0.99 if day_lines > 0 else db_lines == 0

                    audit_note = ""
                    if not head_ok:
                        audit_note += f"AUDIT head mismatch: API={day_heads} DB={db_heads}; "
                    if not line_ok:
                        audit_note += f"AUDIT line mismatch: API={day_lines} DB={db_lines}; "
                    if audit_note:
                        print(f"POS {d.isoformat()} audit WARN: {audit_note}", flush=True)
                        # Retry from top of attempt loop (re-fetch from API)
                        day_heads, day_lines = 0, 0
                        day_ok = False
                        day_err = audit_note.strip()
                        continue

                    day_ok = True
                    print(f"POS {d.isoformat()}: {day_heads} heads, {day_lines} lines "
                          f"(DB: {db_heads} heads, {db_lines} lines) OK", flush=True)
                    break
                except Exception as e:
                    day_err = str(e)[:180]
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    time.sleep(5 * (attempt + 1))
            if day_ok:
                heads += day_heads
                lines += day_lines
            else:
                # Log error but CONTINUE to next day (don't abort entire sync)
                print(f"POS {d.isoformat()} FAILED after 3 attempts: {day_err}", flush=True)
                has_error = True
                err = f"{d.isoformat()}: {day_err}"
                # Continue to next day — don't break
            d += timedelta(days=1)

        try:
            conn.close()
        except Exception:
            pass
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE sync_history SET status=%s, records_processed=%s, error_message=%s, completed_at=%s WHERE id=%s",
            ("FAILED" if has_error else "SUCCESS", heads + lines, err,
             datetime.now(timezone.utc), history_id))
        conn.commit()
        return {"heads": heads, "lines": lines} if not has_error else f"ERROR {err}"
    finally:
        try:
            lock_cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (lock_key,))
            lock_conn.commit()
        except Exception:
            pass
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
        try:
            lock_conn.close()
        except Exception:
            pass


@celery_app.task(name="app.services.reports.sync_pos_sales_backfill")
def sync_pos_sales_backfill(company_id: int, date_from: str, date_to: str = None,
                            chunk_days: int = 7):
    """One-shot backfill for historical POS sales data (Aug 2026 onward).

    Syncs date_from → date_to in {chunk_days}-day chunks to avoid:
    - OMS API timeouts on very large date ranges
    - Celery task timeout limits
    - DB connection pool exhaustion

    Safe for re-run: uses UPSERT (no DELETE), so existing data is never lost.

    Usage:
        sync_pos_sales_backfill.delay(
            company_id=1,
            date_from="2026-08-01",
            date_to=date.today().isoformat(),
            chunk_days=7
        )
    """
    end_d = date.fromisoformat(date_to) if date_to else date.today()
    start_d = date.fromisoformat(date_from)

    total_heads, total_lines = 0, 0
    errors = []
    d = start_d

    print(f"[POS_BACKFILL] Starting backfill company={company_id} "
          f"from {start_d} to {end_d}, chunk={chunk_days}d", flush=True)

    while d <= end_d:
        chunk_end = min(d + timedelta(days=chunk_days - 1), end_d)
        result = sync_pos_sales(company_id, d.isoformat(), chunk_end.isoformat())

        if isinstance(result, dict):
            total_heads += result.get("heads", 0)
            total_lines += result.get("lines", 0)
            print(f"[POS_BACKFILL] {d}→{chunk_end}: {result}", flush=True)
        else:
            # Result is an error string
            errors.append(f"{d}→{chunk_end}: {result}")
            print(f"[POS_BACKFILL] {d}→{chunk_end} ERROR: {result}", flush=True)

        d = chunk_end + timedelta(days=1)

    summary = {"heads": total_heads, "lines": total_lines, "errors": errors}
    print(f"[POS_BACKFILL] Completed company={company_id}: {total_heads} heads, "
          f"{total_lines} lines, {len(errors)} days with errors", flush=True)
    return summary


@celery_app.task(name="app.services.reports.sync_pos_sales_recovery")
def sync_pos_sales_recovery():
    """Find and re-sync any days with low/incomplete data.

    Scans all active companies, finds days where:
    - DB row count < 10 (likely empty/missing)
    - synced_at > 24h ago AND today (stale)

    Triggers sync_pos_sales for those specific days.
    Run manually or schedule daily.
    """
    from app.core.db import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Find companies with POS sales (RealDictCursor returns dict-like rows)
        cur.execute("""
            SELECT DISTINCT company_id
            FROM esb_data.report_pos_sales
            WHERE sales_date >= CURRENT_DATE - INTERVAL '60 days'
        """)
        # RealDictCursor: fetchall() returns list; iterate before list comprehension
        rows = cur.fetchall()
        companies = [r['company_id'] for r in rows] if rows else []

        today = date.today()
        recovered_days = 0

        for cid in companies:
            # Find days with suspiciously low line counts (< 10 rows)
            cur.execute("""
                SELECT sales_date::text, count(*) as cnt
                FROM esb_data.report_pos_sales
                WHERE company_id = %s
                  AND sales_date >= CURRENT_DATE - INTERVAL '30 days'
                  AND sales_date < %s
                GROUP BY sales_date
                HAVING count(*) < 10
            """, (cid, today.isoformat()))
            low_rows = cur.fetchall()

            for row in low_rows:
                # RealDictCursor: access by column name
                day_str = str(row['sales_date'])
                cnt = row['cnt']
                print(f"[POS_RECOVERY] company={cid} day={day_str} "
                      f"has only {cnt} rows — re-syncing", flush=True)
                result = sync_pos_sales(cid, day_str, day_str)
                if isinstance(result, dict):
                    recovered_days += 1
                    print(f"[POS_RECOVERY] Re-synced {cid}/{day_str}: {result}", flush=True)
                else:
                    print(f"[POS_RECOVERY] Failed {cid}/{day_str}: {result}", flush=True)

        print(f"[POS_RECOVERY] Done: recovered {recovered_days} days", flush=True)
        return {"recovered_days": recovered_days}
    finally:
        cur.close()
        conn.close()
