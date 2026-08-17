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
}


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
