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
    # PRODUCT SALES REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "product-sales-recapitulation-report": {
        "title": "Product Sales Recapitulation Report",
        "title_id": "Laporan Rekapitulasi Penjualan Produk",
        "category": "product-sales",
        "tier": "T1",
        "source": "trx",
        "entity": "PRODUCT_SALES",
        "description": "Product sales summary",
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
    # ADDITIONAL INVENTORY REPORTS (T1)
    # ─────────────────────────────────────────────────────────────────────────────
    "goods-receipt-recapitulation-report": {
        "title": "Goods Receipt Recapitulation Report",
        "title_id": "Laporan Rekapitulasi Penerimaan Barang",
        "category": "inventory",
        "tier": "T1",
        "source": "trx",
        "entity": "GOODS_RECEIPT",
        "description": "Goods receipt summary",
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
}


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
    params = [company_id, date_from, date_to]
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
            rows.append({
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
            })
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
    params = [company_id, entity_type, date_from, date_to]
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("purchaseOrderDetails") or []:
            rows.append({
                "purchaseOrderNum": payload.get("purchaseOrderNum"),
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("goodsReceiptDetails") or []:
            rows.append({
                "goodsReceiptNum": payload.get("goodsReceiptNum"),
                "goodsReceiptDate": str(payload.get("goodsReceiptDate") or "")[:10],
                "purchaseOrderNum": payload.get("purchaseOrderNum"),
                "supplierName": payload.get("supplierName"),
                "branchName": payload.get("branchName"),
                "warehouseName": payload.get("warehouseName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qtyOrder": _num(d.get("qtyOrder")),
                "qtyReceive": _num(d.get("qtyReceive")),
                "qtyReject": _num(d.get("qtyReject")),
                "hpp": _num(d.get("hpp")),
                "totalReceive": _num(d.get("totalReceive")),
                "statusName": payload.get("statusName"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("purchaseRequestDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("goodsDeliveryDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("manufacturingDetails") or []:
            rows.append({
                "manufacturingNum": payload.get("manufacturingNum"),
                "manufacturingDate": str(payload.get("manufacturingDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "bomName": payload.get("bomName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "outputQty": _num(d.get("outputQty")),
                "hpp": _num(d.get("hpp")),
                "totalOutput": _num(d.get("totalOutput")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("disbursementDetails") or []:
            rows.append({
                "disbursementNum": payload.get("disbursementNum"),
                "disbursementDate": str(payload.get("disbursementDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "accountName": payload.get("accountName"),
                "paymentMethodName": payload.get("paymentMethodName"),
                "partnerName": payload.get("partnerName"),
                "purposeName": d.get("purposeName"),
                "description": d.get("description"),
                "amount": _num(d.get("amount")),
                "coaNo": d.get("coaNo"),
                "statusName": payload.get("statusName"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("receiptDetails") or []:
            rows.append({
                "receiptNum": payload.get("receiptNum"),
                "receiptDate": str(payload.get("receiptDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "accountName": payload.get("accountName"),
                "paymentMethodName": payload.get("paymentMethodName"),
                "partnerName": payload.get("partnerName"),
                "purposeName": d.get("purposeName"),
                "description": d.get("description"),
                "amount": _num(d.get("amount")),
                "coaNo": d.get("coaNo"),
                "statusName": payload.get("statusName"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("advanceSalesDetails") or []:
            rows.append({
                "advanceSalesNum": payload.get("advanceSalesNum"),
                "advanceSalesDate": str(payload.get("advanceSalesDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "customerName": payload.get("customerName"),
                "productName": d.get("productName"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "price": _num(d.get("price")),
                "total": _num(d.get("total")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("journalDetails") or []:
            rows.append({
                "journalNum": payload.get("journalNum"),
                "journalDate": str(payload.get("journalDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "accountName": d.get("accountName"),
                "accountNo": d.get("accountNo"),
                "description": d.get("description"),
                "debit": _num(d.get("debit")),
                "credit": _num(d.get("credit")),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes"),
            })
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
    params = [company_id, entity_type, date_from, date_to]
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("transferDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("productionOrderDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("materialDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("paymentDetails") or []:
            rows.append({
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
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("salesDetails") or []:
            rows.append({
                "salesNum": payload.get("salesNum"),
                "salesDate": str(payload.get("salesDate") or "")[:10],
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
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("suspenseDetails") or []:
            rows.append({
                "suspenseNum": payload.get("suspenseNum"),
                "suspenseDate": str(payload.get("suspenseDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "customerName": payload.get("customerName"),
                "accountName": d.get("accountName"),
                "accountNo": d.get("accountNo"),
                "description": d.get("description"),
                "debit": _num(d.get("debit")),
                "credit": _num(d.get("credit")),
                "balance": _num(d.get("balance")),
                "dueDate": str(d.get("dueDate") or "")[:10],
                "statusName": payload.get("statusName"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("suspenseDetails") or []:
            rows.append({
                "suspenseNum": payload.get("suspenseNum"),
                "suspenseDate": str(payload.get("suspenseDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "supplierName": payload.get("supplierName"),
                "accountName": d.get("accountName"),
                "accountNo": d.get("accountNo"),
                "description": d.get("description"),
                "debit": _num(d.get("debit")),
                "credit": _num(d.get("credit")),
                "balance": _num(d.get("balance")),
                "dueDate": str(d.get("dueDate") or "")[:10],
                "statusName": payload.get("statusName"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("advanceDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
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
            rows.append({
                "budgetNum": payload.get("budgetNum"),
                "budgetDate": str(payload.get("budgetDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "departmentName": payload.get("departmentName"),
                "accountName": d.get("accountName"),
                "accountNo": d.get("accountNo"),
                "periodName": d.get("periodName"),
                "budgetAmount": budget_amount,
                "realizedAmount": realized_amount,
                "remainingAmount": remaining,
                "percentageUsed": pct_used,
                "statusName": payload.get("statusName"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("revisionDetails") or []:
            rows.append({
                "revisionNum": payload.get("revisionNum"),
                "revisionDate": str(payload.get("revisionDate") or "")[:10],
                "branchName": payload.get("branchName"),
                "departmentName": payload.get("departmentName"),
                "accountName": d.get("accountName"),
                "periodName": d.get("periodName"),
                "previousAmount": _num(d.get("previousAmount")),
                "changeAmount": _num(d.get("changeAmount")),
                "newAmount": _num(d.get("newAmount")),
                "changeType": d.get("changeType"),
                "reason": d.get("reason"),
                "statusName": payload.get("statusName"),
            })
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


def _purchase_invoice_rows(cur, company_id: int, branch_esb_id: typing.Optional[str],
                           date_from: date, date_to: date):
    """Fetch purchase invoice rows."""
    sql = """
        SELECT t.payload
        FROM trx_raw_staging t
        WHERE t.company_id = %s AND t.entity_type = 'PURCHASE_INVOICE'
          AND t.doc_date BETWEEN %s AND %s
    """
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("invoiceDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("returnDetails") or []:
            rows.append({
                "returnNum": payload.get("returnNum"),
                "returnDate": str(payload.get("returnDate") or "")[:10],
                "invoiceNum": payload.get("invoiceNum"),
                "supplierName": payload.get("supplierName"),
                "branchName": payload.get("branchName"),
                "warehouseName": payload.get("warehouseName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "price": _num(d.get("price")),
                "total": _num(d.get("total")),
                "reason": d.get("reason"),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("returnDetails") or []:
            rows.append({
                "returnNum": payload.get("returnNum"),
                "returnDate": str(payload.get("returnDate") or "")[:10],
                "goodsReceiptNum": payload.get("goodsReceiptNum"),
                "supplierName": payload.get("supplierName"),
                "branchName": payload.get("branchName"),
                "warehouseName": payload.get("warehouseName"),
                "productName": d.get("productName"),
                "productCode": d.get("productCode"),
                "uomName": d.get("uomName"),
                "qty": _num(d.get("qty")),
                "hpp": _num(d.get("hpp")),
                "total": _num(d.get("total")),
                "reason": d.get("reason"),
                "statusName": payload.get("statusName"),
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("returnDetails") or []:
            rows.append({
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
                "notes": payload.get("notes"),
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        for d in payload.get("bomDetails") or []:
            rows.append({
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
            })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append({
            "advanceNum": payload.get("advanceNum"),
            "advanceDate": str(payload.get("advanceDate") or "")[:10],
            "branchName": payload.get("branchName"),
            "employeeName": payload.get("employeeName"),
            "departmentName": payload.get("departmentName"),
            "purposeName": payload.get("purposeName"),
            "amount": _num(payload.get("amount")),
            "realizedAmount": _num(payload.get("realizedAmount")),
            "remainingAmount": _num(payload.get("remainingAmount")),
            "statusName": payload.get("statusName"),
            "notes": payload.get("notes"),
        })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append({
            "journalNum": payload.get("journalNum"),
            "journalDate": str(payload.get("journalDate") or "")[:10],
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
            "notes": payload.get("notes"),
        })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append({
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
            "notes": payload.get("notes"),
        })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append({
            "paymentNum": payload.get("paymentNum"),
            "paymentDate": str(payload.get("paymentDate") or "")[:10],
            "invoiceNum": payload.get("invoiceNum"),
            "supplierName": payload.get("supplierName"),
            "branchName": payload.get("branchName"),
            "accountName": payload.get("accountName"),
            "paymentMethodName": payload.get("paymentMethodName"),
            "amount": _num(payload.get("amount")),
            "reference": payload.get("reference"),
            "statusName": payload.get("statusName"),
            "notes": payload.get("notes"),
        })
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
    params = [company_id, date_from, date_to]
    if branch_esb_id:
        sql += " AND t.payload->>'branchID' = %s"
        params.append(str(branch_esb_id))
    sql += " ORDER BY t.doc_date DESC"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        rows.append({
            "actuationNum": payload.get("actuationNum"),
            "actuationDate": str(payload.get("actuationDate") or "")[:10],
            "purchaseOrderNum": payload.get("purchaseOrderNum"),
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
        })
    return rows


def _rpt_rows(cur, company_id: int, report_key: str, entity: str,
              branch_esb_id: typing.Optional[str], date_from: date, date_to: date):
    """Rows from report_raw_staging: one stored row per branch/day with lines[]."""
    sql = """
        SELECT raw_data FROM report_raw_staging
        WHERE company_id = %s AND report_type = %s AND period_start BETWEEN %s AND %s
    """
    params = [company_id, entity, date_from, date_to]
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
                    rows.append(flat)
                continue
            for k, v in list(line.items()):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    line[k] = _num(v)
            rows.append(line)
    return rows


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
    """Unpaginated row iterator for exports."""
    spec = REPORTS.get(slug)
    if not spec:
        raise ValueError(f"Unknown report: {slug}")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if spec["source"] == "trx":
            entity = spec["entity"]
            fetcher = TRX_ROW_FETCHERS.get(entity)
            if fetcher:
                rows = fetcher(cur, company_id, branch_esb_id, date_from, date_to)
            else:
                rows = []
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
