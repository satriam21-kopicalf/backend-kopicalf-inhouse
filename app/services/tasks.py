import os
import json
import httpx
import typing
from datetime import datetime, timezone, timedelta
from psycopg2.extras import execute_values, DictCursor
from app.core.worker import celery_app
from app.core.db import get_db_connection
from app.schemas.esb import (
    ESBProductModel, ESBCategoryModel, ESBSubCategoryModel, ESBUnitModel, 
    ESBBomModel, ESBBranchProductModel, ESBPricelistModel, 
    ESBBranchModel, ESBEmployeeModel, ESBSupplierModel, ESBGenericModel
)
import pytz

ESB_API_BASE_URL = os.getenv("ESB_CORE_URL", "https://stg7.esb.co.id/core-stg")

def _refresh_esb_token() -> typing.Optional[str]:
    """Login ulang ke ESB dan kembalikan token baru. Return None jika gagal."""
    esb_user = os.getenv("ESB_CORE_USERNAME")
    esb_pass = os.getenv("ESB_CORE_PASSWORD")
    if not esb_user or not esb_pass:
        return None
    try:
        res = httpx.post(
            f"{ESB_API_BASE_URL}/auth/login",
            json={"username": esb_user, "password": esb_pass},
            timeout=15.0
        )
        if res.status_code == 200:
            return res.json().get("result", {}).get("accessToken")
    except Exception:
        pass
    return None


class CircuitBreakerOpenException(Exception):
    pass


class ESBClient:
    """HTTP client untuk ESB API dengan auto token refresh saat 401."""

    def __init__(self, token: str):
        self.token = token
        self.error_count = 0
        self.circuit_open = False
        self._http_client = httpx.Client(timeout=60.0)

    def get(self, path: str, params: typing.Optional[dict] = None):
        if self.circuit_open:
            raise CircuitBreakerOpenException("Circuit is open due to consecutive failures")

        url = f"{ESB_API_BASE_URL}{path}"

        response = self._http_client.get(
            url,
            headers=self._headers(),
            params=params
        )

        # Token expired — coba refresh sekali
        if response.status_code == 401:
            new_token = _refresh_esb_token()
            if new_token:
                self.token = new_token
                response = self._http_client.get(
                    url,
                    headers=self._headers(),
                    params=params
                )

        if response.status_code >= 400:
            # 400 pada stock-location = productDetailID tidak ditemukan, skip saja
            if response.status_code == 400 and "stock-location" in url:
                return {"result": []}
            self._record_error()
            response.raise_for_status()

        self.error_count = 0
        return response.json()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _record_error(self):
        self.error_count += 1
        if self.error_count >= 3:
            self.circuit_open = True



def get_all_endpoints():
    return [
        {"entity": "PRODUCT", "path": "/product/list", "schema": ESBProductModel},
        {"entity": "BRANCH", "path": "/branch", "schema": ESBBranchModel},
        {"entity": "CATEGORY", "path": "/product/category", "schema": ESBCategoryModel},
        {"entity": "EMPLOYEE", "path": "/employee", "schema": ESBEmployeeModel},
        {"entity": "SUPPLIER", "path": "/supplier", "schema": ESBSupplierModel},
        
        {"entity": "PRODUCT_SUB_CATEGORY", "path": "/product/sub-category", "schema": ESBSubCategoryModel},
        {"entity": "PRODUCT_UNIT", "path": "/units", "schema": ESBUnitModel},
        {"entity": "PRICELIST", "path": "/pricelist", "schema": ESBPricelistModel},
        {"entity": "BRANCH_PRODUCT", "path": "/product/stock-location", "schema": ESBBranchProductModel},
        {"entity": "CUSTOMER_PRICELIST", "path": "/customer-pricelist", "schema": ESBGenericModel},
        {"entity": "BOM", "path": "/product/bom", "schema": ESBBomModel},
        {"entity": "DOCUMENT_TEMPLATE", "path": "/document-template", "schema": ESBGenericModel},
        {"entity": "FOOD_COST_CALC", "path": "/food-cost-calc", "schema": ESBGenericModel},
        
        {"entity": "POS_MENU", "path": "/pos/menu", "schema": ESBGenericModel},
        {"entity": "POS_USER", "path": "/pos/user", "schema": ESBGenericModel},
        {"entity": "POS_TABLE", "path": "/pos/table", "schema": ESBGenericModel},
        {"entity": "POS_PROMO", "path": "/pos/promotion", "schema": ESBGenericModel},
        {"entity": "POS_VOUCHER", "path": "/pos/voucher", "schema": ESBGenericModel},
        {"entity": "POS_TX", "path": "/pos/transaction", "schema": ESBGenericModel, "is_report": True},
        {"entity": "POS_GUEST", "path": "/pos/guest", "schema": ESBGenericModel},
        {"entity": "POS_SYS", "path": "/pos/system", "schema": ESBGenericModel},
        
        {"entity": "ACC_COA", "path": "/accounting/coa", "schema": ESBGenericModel},
        {"entity": "ACC_CASHFLOW_CAT", "path": "/accounting/cashflow_category", "schema": ESBGenericModel},
        {"entity": "ACC_CURRENCY", "path": "/accounting/currency", "schema": ESBGenericModel},
        {"entity": "ACC_TAX", "path": "/accounting/tax", "schema": ESBGenericModel},
        {"entity": "ACC_RECURRING_JRNL", "path": "/accounting/recurring_journal", "schema": ESBGenericModel},
        {"entity": "ACC_BANK", "path": "/accounting/bank", "schema": ESBGenericModel},
        {"entity": "ACC_COST_CENTER", "path": "/accounting/cost_center", "schema": ESBGenericModel},
        {"entity": "ACC_PURPOSE", "path": "/accounting/purpose", "schema": ESBGenericModel},
        
        {"entity": "COMP_BRAND", "path": "/company/brand", "schema": ESBGenericModel},
        {"entity": "COMP_EMP_GROUP", "path": "/employee/group", "schema": ESBGenericModel},
        {"entity": "COMP_USER_ROLE", "path": "/employee/user_role", "schema": ESBGenericModel},
        {"entity": "COMP_DELIVERY", "path": "/company/delivery", "schema": ESBGenericModel},
        {"entity": "COMP_SYS_CONFIG", "path": "/company/system_config", "schema": ESBGenericModel},
        {"entity": "COMP_MKT", "path": "/company/marketing", "schema": ESBGenericModel},
        
        {"entity": "PARTNER_CUSTOMER", "path": "/partner/customer", "schema": ESBGenericModel},
        {"entity": "PARTNER_TENANT", "path": "/partner/tenant", "schema": ESBGenericModel},
        {"entity": "PARTNER_SALES_REP", "path": "/partner/sales_rep", "schema": ESBGenericModel},
    ]


def sync_endpoint_data(company_id: int, esb_token: str, entity: str, path: str, date_from: typing.Optional[str] = None, date_to: typing.Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    try:
        # Resolve schema_cls
        schema_cls: typing.Type[typing.Any] = ESBGenericModel
        for ep in get_all_endpoints():
            if ep["entity"] == entity:
                schema_cls = ep["schema"]
                break

        try:
            client = ESBClient(esb_token)
        except Exception as e:
            print("Failed to initialize ESBClient", e)
            return
        
        cur.execute("SELECT sync_batch_size FROM engine_settings WHERE id = 1")
        settings = typing.cast(dict[str, typing.Any] | None, cur.fetchone())
        batch_size = settings['sync_batch_size'] if settings else 1000

        cur.execute(
            "INSERT INTO sync_history (entity_type, status, company_id) VALUES (%s, %s, %s) RETURNING id",
            (entity, 'STARTED', company_id)
        )
        result = typing.cast(dict[str, typing.Any] | None, cur.fetchone())
        if result is None:
            raise RuntimeError("Failed to create sync history record")
        history_id = result['id']
        conn.commit()
        
        total_processed = 0
        has_error = False
        error_msg = ""
        
        fetch_queue = []
        if entity == "BRANCH_PRODUCT":
            # ESB API requires productDetailID for stock-location
            # We extract unique productDetailIDs from the PRICELIST raw data
            cur.execute("""
                SELECT DISTINCT CAST(raw_data->>'productDetailID' AS TEXT) AS pd_id 
                FROM esb_raw_staging 
                WHERE entity_type = 'PRICELIST' AND company_id = %s 
                  AND raw_data->>'productDetailID' IS NOT NULL
            """, (company_id,))
            product_detail_ids = [row['pd_id'] for row in cur.fetchall() if row['pd_id']]
            for pd_id in product_detail_ids:
                fetch_queue.append({"productDetailID": pd_id, "page": 1, "limit": batch_size})
            if not product_detail_ids:
                error_msg = "No product details found. Please ensure PRICELIST is synced first."
                has_error = True
        else:
            fetch_queue.append({"page": 1, "limit": batch_size})
            
        while fetch_queue:
            params = fetch_queue.pop(0)
            
            try:
                if date_from and date_to:
                    params["start_date"] = date_from
                    params["end_date"] = date_to
                    
                data = client.get(path, params=params)
                records = []
                total_pages = 1
                
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    pagination = data.get('pagination', {})
                    if pagination and isinstance(pagination, dict):
                        total_pages = pagination.get('totalPages', 1)
                        
                    result_obj = data.get('result', [])
                    if isinstance(result_obj, list):
                        records = result_obj
                    elif isinstance(result_obj, dict):
                        records = result_obj.get('data', [])
                        if not pagination and 'count' in result_obj:
                            import math
                            total_pages = math.ceil(result_obj['count'] / batch_size)
                    else:
                        records = []
                else:
                    records = []
                    
            except CircuitBreakerOpenException:
                has_error = True
                error_msg = "Circuit breaker opened during sync."
                break
            except Exception as api_err:
                has_error = True
                error_msg = f"API call failed for {entity} page {params.get('page', 1)}: {api_err}"
                break 
            
            if not records:
                # Instead of break, continue because there might be other product IDs in queue
                continue 

            
            staging_values = []
            product_values = []
            category_values = []
            sub_category_values = []
            unit_values = []
            bom_values = []
            branch_product_values = []
            pricelist_values = []
            branch_values = []
            employee_values = []
            supplier_values = []
            dlq_values = []
            
            for item in records:
                try:
                    parsed_item = schema_cls(**item)

                    # ─── Derive esb_id per entity ─────────────────────────────
                    if entity == "PRODUCT":
                        esb_id = str(parsed_item.productID)
                    elif entity == "BRANCH":
                        esb_id = str(parsed_item.branchID)
                    elif entity == "CATEGORY":
                        esb_id = str(parsed_item.categoryID)
                    elif entity == "PRODUCT_SUB_CATEGORY":
                        esb_id = str(parsed_item.subCategoryID)
                    elif entity == "PRODUCT_UNIT":
                        # uomID adalah ID utama unit (bukan metricID grup)
                        esb_id = str(parsed_item.uomID)
                    elif entity == "BOM":
                        esb_id = str(parsed_item.bomID)
                    elif entity == "BRANCH_PRODUCT":
                        # productDetailID adalah identifier utama dari stock-location
                        esb_id = str(parsed_item.productDetailID)
                        if esb_id == "0":
                            import hashlib
                            esb_id = hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()
                    elif entity == "PRICELIST":
                        # ID field di response adalah 'ID' (kapital)
                        esb_id = str(parsed_item.pricelistID)
                        if esb_id == "0":
                            import hashlib
                            esb_id = hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()
                    elif entity == "EMPLOYEE":
                        esb_id = str(parsed_item.employeeID)
                    elif entity == "SUPPLIER":
                        esb_id = str(parsed_item.supplierID)
                    else:
                        esb_id_val = (
                            item.get('id') or item.get('ID') or
                            item.get(f"{entity.lower().split('_')[-1]}ID") or
                            item.get('coaNo') or item.get('code') or item.get('name')
                        )
                        esb_id = str(esb_id_val) if esb_id_val else "unknown"
                        if esb_id == "unknown":
                            import hashlib
                            esb_id = hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()

                    # Staging row
                    staging_values.append((entity, esb_id, company_id, json.dumps(item), datetime.now(timezone.utc)))

                    # ─── Extract ke tabel spesifik ────────────────────────────
                    if entity == "PRODUCT":
                        product_values.append((
                            esb_id, company_id,
                            parsed_item.productName,
                            parsed_item.productCode or "",
                            parsed_item.bomName,
                            parsed_item.categoryName,
                            parsed_item.subCategoryName,
                            parsed_item.categoryTypeName,
                            parsed_item.flagActive if parsed_item.flagActive is not None else 1,
                            parsed_item.barcode,
                            parsed_item.uomName,
                            parsed_item.purchasePrice,
                            parsed_item.sellPrice,
                            parsed_item.stock,
                            bool(parsed_item.hasVariant) if parsed_item.hasVariant is not None else False,
                            bool(parsed_item.isRawMaterial) if parsed_item.isRawMaterial is not None else False,
                            bool(parsed_item.isProduction) if parsed_item.isProduction is not None else False,
                            parsed_item.imageUrl,
                            parsed_item.productAlias,
                            parsed_item.categoryID,
                            parsed_item.subCategoryID,
                            parsed_item.uomID,
                            parsed_item.bomID,
                            parsed_item.pricelistID,
                            parsed_item.minStock,
                            parsed_item.maxStock,
                            parsed_item.isTrackInventory,
                            parsed_item.description
                        ))

                    elif entity == "CATEGORY":
                        # categoryCode tidak ada di response, simpan None
                        category_values.append((
                            esb_id, company_id,
                            getattr(parsed_item, 'categoryCode', None),  # None
                            parsed_item.categoryName,
                            parsed_item.categoryTypeName,
                            bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))

                    elif entity == "PRODUCT_SUB_CATEGORY":
                        # categoryID & subCategoryCode tidak ada di response list
                        sub_category_values.append((
                            esb_id, company_id,
                            None,                    # category_esb_id — tidak ada di response
                            None,                    # code — tidak ada di response
                            parsed_item.subCategoryName,
                            bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True,
                            parsed_item.displayOrder  # None
                        ))

                    elif entity == "PRODUCT_UNIT":
                        # metricName sebagai code, uomName sebagai name
                        unit_values.append((
                            esb_id, company_id,
                            parsed_item.metricName,  # code = nama metrik
                            parsed_item.uomName,     # name = nama satuan
                            bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))

                    elif entity == "BOM":
                        # productID tidak ada di list endpoint, simpan None
                        bom_values.append((
                            esb_id, company_id,
                            parsed_item.productID,   # None dari list response
                            parsed_item.bomCode,
                            parsed_item.bomName,
                            parsed_item.outputQty or 1.0,
                            bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))

                    elif entity == "BRANCH_PRODUCT":
                        # Response: productDetailID, productName, uomName, qty, stockQty
                        # branchID/branchName tidak ada di response ini
                        branch_product_values.append((
                            esb_id, company_id,
                            None,                          # branch_esb_id — tidak ada
                            parsed_item.productID,         # None
                            parsed_item.stockQty or 0,     # stock = stockQty
                            parsed_item.stockQty or 0,     # available_stock = stockQty
                            bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True,
                            parsed_item.productCode,       # None
                            parsed_item.productName,
                            parsed_item.branchName,        # None
                            parsed_item.locationID,        # None
                            parsed_item.locationName,      # None
                            parsed_item.minStock or 0,
                            parsed_item.maxStock or 0,
                            parsed_item.reservedStock or 0
                        ))

                    elif entity == "PRICELIST":
                        # expiredDate dipetakan dari 'expireDate' via AliasChoices
                        _price_date = parsed_item.priceDate or None
                        _expired_date = parsed_item.expiredDate or None
                        # branchID dari applicableBranch jika ada
                        _branch_id = parsed_item.branchID  # property dari applicableBranch
                        pricelist_values.append((
                            esb_id, company_id,
                            parsed_item.productID,
                            _branch_id,
                            parsed_item.price or 0,
                            bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True,
                            _price_date,
                            parsed_item.supplierName,
                            parsed_item.productName,
                            parsed_item.productCode,
                            parsed_item.unitName,
                            parsed_item.currency,
                            _expired_date
                        ))

                    elif entity == "BRANCH":
                        branch_values.append((
                            esb_id, company_id,
                            parsed_item.branchName,
                            parsed_item.branchCode,
                            parsed_item.isActive if parsed_item.isActive is not None else True,
                            parsed_item.locationName,
                            parsed_item.stock,
                            parsed_item.availableStock
                        ))

                    elif entity == "EMPLOYEE":
                        employee_values.append((
                            esb_id, company_id,
                            parsed_item.full_name,
                            parsed_item.position,
                            getattr(parsed_item, 'employeeGroup', None),
                            getattr(parsed_item, 'status', 'ACTIVE'),
                            str(parsed_item.branch_id) if parsed_item.branch_id else 'UNKNOWN'
                        ))

                    elif entity == "SUPPLIER":
                        supplier_values.append((
                            esb_id, company_id,
                            parsed_item.name,
                            parsed_item.type,
                            parsed_item.supplierCategory,
                            getattr(parsed_item, 'status', 'ACTIVE')
                        ))

                    total_processed += 1
                except Exception as ve:
                    dlq_values.append((entity, json.dumps(item), str(ve)))
            
            if staging_values:
                staging_values = list({(v[0], v[1], v[2]): v for v in staging_values}.values())
                execute_values(cur, """
                    INSERT INTO esb_raw_staging (entity_type, esb_id, company_id, raw_data, updated_at)
                    VALUES %s
                    ON CONFLICT (company_id, entity_type, esb_id) DO UPDATE SET
                        raw_data = EXCLUDED.raw_data,
                        updated_at = EXCLUDED.updated_at
                """, staging_values)
            
            if product_values:
                product_values = list({v[0]: v for v in product_values}.values())
                execute_values(cur, """
                    INSERT INTO md_products (
                        esb_id, company_id, name, product_code, bom_name, category_name, sub_category_name, category_type_name, 
                        flag_active, barcode, uom_name, purchase_price, sell_price, stock, has_variant, 
                        is_raw_material, is_production, image_url, product_alias, category_id, sub_category_id,
                        uom_id, bom_id, pricelist_id, min_stock, max_stock, is_track_inventory, description
                    )
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, product_code = EXCLUDED.product_code, bom_name = EXCLUDED.bom_name,
                        category_name = EXCLUDED.category_name, sub_category_name = EXCLUDED.sub_category_name,
                        category_type_name = EXCLUDED.category_type_name, flag_active = EXCLUDED.flag_active,
                        barcode = EXCLUDED.barcode, uom_name = EXCLUDED.uom_name, purchase_price = EXCLUDED.purchase_price,
                        sell_price = EXCLUDED.sell_price, stock = EXCLUDED.stock, has_variant = EXCLUDED.has_variant,
                        is_raw_material = EXCLUDED.is_raw_material, is_production = EXCLUDED.is_production, image_url = EXCLUDED.image_url,
                        product_alias = EXCLUDED.product_alias, category_id = EXCLUDED.category_id, sub_category_id = EXCLUDED.sub_category_id,
                        uom_id = EXCLUDED.uom_id, bom_id = EXCLUDED.bom_id, pricelist_id = EXCLUDED.pricelist_id, min_stock = EXCLUDED.min_stock,
                        max_stock = EXCLUDED.max_stock, is_track_inventory = EXCLUDED.is_track_inventory, description = EXCLUDED.description
                """, product_values)
            
            if category_values:
                category_values = list({v[0]: v for v in category_values}.values())
                execute_values(cur, """
                    INSERT INTO md_categories (esb_id, company_id, code, name, type_name, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        code = EXCLUDED.code, name = EXCLUDED.name, type_name = EXCLUDED.type_name, flag_active = EXCLUDED.flag_active
                """, category_values)

            if sub_category_values:
                sub_category_values = list({v[0]: v for v in sub_category_values}.values())
                execute_values(cur, """
                    INSERT INTO md_sub_categories (esb_id, company_id, category_esb_id, code, name, flag_active, display_order)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        category_esb_id = EXCLUDED.category_esb_id, code = EXCLUDED.code, name = EXCLUDED.name, flag_active = EXCLUDED.flag_active,
                        display_order = EXCLUDED.display_order
                """, sub_category_values)

            if unit_values:
                unit_values = list({v[0]: v for v in unit_values}.values())
                execute_values(cur, """
                    INSERT INTO md_units (esb_id, company_id, code, name, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        code = EXCLUDED.code, name = EXCLUDED.name, flag_active = EXCLUDED.flag_active
                """, unit_values)

            if bom_values:
                bom_values = list({v[0]: v for v in bom_values}.values())
                execute_values(cur, """
                    INSERT INTO md_boms (esb_id, company_id, product_esb_id, code, name, output_qty, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        product_esb_id = EXCLUDED.product_esb_id, code = EXCLUDED.code, name = EXCLUDED.name, output_qty = EXCLUDED.output_qty, flag_active = EXCLUDED.flag_active
                """, bom_values)

            if branch_product_values:
                branch_product_values = list({v[0]: v for v in branch_product_values}.values())
                execute_values(cur, """
                    INSERT INTO md_branch_products (esb_id, company_id, branch_esb_id, product_esb_id, stock, available_stock, flag_active,
                        product_code, product_name, branch_name, location_id, location_name, min_stock, max_stock, reserved_stock)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        branch_esb_id = EXCLUDED.branch_esb_id, product_esb_id = EXCLUDED.product_esb_id,
                        stock = EXCLUDED.stock, available_stock = EXCLUDED.available_stock, flag_active = EXCLUDED.flag_active,
                        product_code = EXCLUDED.product_code, product_name = EXCLUDED.product_name, branch_name = EXCLUDED.branch_name,
                        location_id = EXCLUDED.location_id, location_name = EXCLUDED.location_name, min_stock = EXCLUDED.min_stock,
                        max_stock = EXCLUDED.max_stock, reserved_stock = EXCLUDED.reserved_stock
                """, branch_product_values)

            if pricelist_values:
                pricelist_values = list({v[0]: v for v in pricelist_values}.values())
                execute_values(cur, """
                    INSERT INTO md_pricelists (esb_id, company_id, product_esb_id, branch_esb_id, price, flag_active,
                        price_date, supplier_name, product_name, product_code, unit_name, currency, expired_date)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        product_esb_id = EXCLUDED.product_esb_id, branch_esb_id = EXCLUDED.branch_esb_id,
                        price = EXCLUDED.price, flag_active = EXCLUDED.flag_active,
                        price_date = EXCLUDED.price_date, supplier_name = EXCLUDED.supplier_name, product_name = EXCLUDED.product_name,
                        product_code = EXCLUDED.product_code, unit_name = EXCLUDED.unit_name, currency = EXCLUDED.currency, expired_date = EXCLUDED.expired_date
                """, pricelist_values)

            if branch_values:
                branch_values = list({v[0]: v for v in branch_values}.values())
                execute_values(cur, """
                    INSERT INTO md_outlets (esb_id, company_id, name, branch_code, is_active, location_name, stock, available_stock)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, branch_code = EXCLUDED.branch_code, is_active = EXCLUDED.is_active,
                        location_name = EXCLUDED.location_name, stock = EXCLUDED.stock, available_stock = EXCLUDED.available_stock
                """, branch_values)
                
            if employee_values:
                employee_values = list({v[0]: v for v in employee_values}.values())
                execute_values(cur, """
                    INSERT INTO md_employees (esb_id, company_id, name, role, employee_group, status, branch_id)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, role = EXCLUDED.role, employee_group = EXCLUDED.employee_group,
                        status = EXCLUDED.status, branch_id = EXCLUDED.branch_id
                """, employee_values)
                
            if supplier_values:
                supplier_values = list({v[0]: v for v in supplier_values}.values())
                execute_values(cur, """
                    INSERT INTO md_suppliers (esb_id, company_id, name, type, supplier_category, status)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, type = EXCLUDED.type, supplier_category = EXCLUDED.supplier_category,
                        status = EXCLUDED.status
                """, supplier_values)
                
            if dlq_values:
                execute_values(cur, """
                    INSERT INTO dlq_logs (entity_type, raw_payload, error_reason)
                    VALUES %s
                """, dlq_values)

            conn.commit()
            
            if params["page"] < total_pages:
                next_params = params.copy()
                next_params["page"] += 1
                fetch_queue.append(next_params)

        status = "FAILED" if has_error else "SUCCESS"
        cur.execute(
            """
            UPDATE sync_history SET status = %s, records_processed = %s, error_message = %s, completed_at = %s
            WHERE id = %s
            """,
            (status, total_processed, error_msg, datetime.now(timezone.utc), history_id)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


@celery_app.task
def sync_company_data(company_id: int, esb_token: str, historical_start: str, today_str: str):
    endpoints = get_all_endpoints()
    for ep in endpoints:
        entity = ep["entity"]
        path = ep["path"]
        is_report = ep.get("is_report", False)
        
        # For reports, pass date ranges
        d_from = historical_start if is_report else None
        d_to = today_str if is_report else None
        
        try:
            sync_endpoint_data(
                company_id=company_id,
                esb_token=esb_token,
                entity=entity,
                path=path,
                date_from=d_from,
                date_to=d_to
            )
        except Exception as e:
            print(f"Error syncing {entity} sequentially: {e}")

@celery_app.task
def sync_master_data():
    """
    Backwards compatible trigger that acts as the router to spawn subtasks for ALL companies.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    try:
        cur.execute("SELECT id, esb_token FROM company_configs WHERE is_active = true")
        companies = cur.fetchall()
        
        if not companies:
            print("No active companies found.")
            return
        
        # Calculate date_from and date_to for report endpoints
        # Initial historical pull: 2026-07-01 to today
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        historical_start = "2026-07-01"
            
        # Try to get dynamic token
        dynamic_token = None
        esb_user = os.getenv("ESB_CORE_USERNAME")
        esb_pass = os.getenv("ESB_CORE_PASSWORD")
        if esb_user and esb_pass:
            try:
                login_url = f"{ESB_API_BASE_URL}/auth/login"
                res = httpx.post(login_url, json={"username": esb_user, "password": esb_pass}, timeout=15.0)
                if res.status_code == 200:
                    data = res.json()
                    dynamic_token = data.get("result", {}).get("accessToken")
            except Exception as e:
                print(f"Failed to fetch dynamic token: {e}")

        for company in companies:
            company_id = company['id']
            esb_token = dynamic_token if dynamic_token else company['esb_token']
            
            if not esb_token:
                continue
                
            sync_company_data.delay(company_id, esb_token, historical_start, today_str)
    finally:
        cur.close()
        conn.close()

@celery_app.task
def sync_master_data_router():
    from datetime import datetime, timezone
    import pytz
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    try:
        cur.execute("SELECT work_hours_interval_minutes, morning_window_interval_minutes FROM engine_settings WHERE id = 1")
        settings = typing.cast(typing.Any, cur.fetchone())
        if not settings:
            return "No engine settings found"
            
        work_interval = settings['work_hours_interval_minutes']
        morning_interval = settings['morning_window_interval_minutes']
        
        jkt_tz = pytz.timezone('Asia/Jakarta')
        now_jkt = datetime.now(jkt_tz)
        current_hour = now_jkt.hour
        current_minute = now_jkt.minute
        current_time_float = current_hour + (current_minute / 60.0)
        
        is_morning_window = 2.5 <= current_time_float <= 8.0 
        is_work_hours = not is_morning_window
        
        target_interval = morning_interval if is_morning_window else work_interval
        
        cur.execute("SELECT completed_at FROM sync_history WHERE entity_type = 'SYSTEM_SYNC_TRACKER' AND status = 'SUCCESS' ORDER BY id DESC LIMIT 1")
        last_sync = typing.cast(typing.Any, cur.fetchone())
        
        should_run = False
        if last_sync and last_sync.get('completed_at'):
            last_sync_time = last_sync['completed_at']
            delta_minutes = (datetime.now(timezone.utc) - last_sync_time).total_seconds() / 60.0
            if delta_minutes >= (target_interval - 0.5):
                should_run = True
        else:
            should_run = True
            
        if should_run:
            print(f"Triggering sync_master_data. Interval matched: {target_interval} minutes.")
            
            # Create a master record to record the fact we triggered it (so the interval works)
            cur.execute("INSERT INTO sync_history (entity_type, status, completed_at) VALUES ('SYSTEM_SYNC_TRACKER', 'SUCCESS', %s)", (datetime.now(timezone.utc),))
            conn.commit()
            
            sync_master_data.delay()
            return f"Triggered sync (interval {target_interval})"
        else:
            print(f"Skipping sync. Target interval {target_interval} mins not yet reached.")
            return "Skipped sync"
            
    finally:
        cur.close()
        conn.close()
