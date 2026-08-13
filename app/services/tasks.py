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

class CircuitBreakerOpenException(Exception):
    pass

class ESBClient:
    def __init__(self, token):
        self.token = token
        self.error_count = 0
        self.circuit_open = False
        self._http_client = httpx.Client(timeout=60.0)
        
    def get(self, path, params=None):
        if self.circuit_open:
            raise CircuitBreakerOpenException("Circuit is open due to consecutive failures")
            
        url = f"{ESB_API_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        try:
            response = self._http_client.get(url, headers=headers, params=params)
            
            if response.status_code >= 400:
                self._record_error()
                response.raise_for_status()
            
            self.error_count = 0
            return response.json()
        except Exception as e:
            self._record_error()
            raise e
            
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
        {"entity": "BRANCH_PRODUCT", "path": "/product/stock-location", "schema": ESBBranchProductModel},
        {"entity": "PRICELIST", "path": "/pricelist", "schema": ESBPricelistModel},
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


@celery_app.task
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
        
        page = 1
        
        while True:
            try:
                params = {"page": page, "limit": batch_size}
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
                    if pagination:
                        total_pages = pagination.get('totalPages', 1)
                        
                    result_obj = data.get('result', [])
                    if isinstance(result_obj, list):
                        records = result_obj
                    elif isinstance(result_obj, dict):
                        records = result_obj.get('data', [])
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
                error_msg = f"API call failed for {entity} page {page}: {api_err}"
                break 
            
            if not records:
                break 
            
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
                    if entity == "PRODUCT":
                        esb_id = str(parsed_item.productID)
                    elif entity == "BRANCH":
                        esb_id = str(parsed_item.branchID)
                    elif entity == "CATEGORY":
                        esb_id = str(parsed_item.categoryID)
                    elif entity == "PRODUCT_SUB_CATEGORY":
                        esb_id = str(parsed_item.subCategoryID)
                    elif entity == "PRODUCT_UNIT":
                        esb_id = str(parsed_item.unitID)
                    elif entity == "BOM":
                        esb_id = str(parsed_item.bomID)
                    elif entity == "BRANCH_PRODUCT":
                        esb_id = str(parsed_item.branchProductID)
                    elif entity == "PRICELIST":
                        esb_id = str(parsed_item.pricelistID)
                    elif entity == "EMPLOYEE":
                        esb_id = str(parsed_item.employeeID)
                    elif entity == "SUPPLIER":
                        esb_id = str(parsed_item.supplierID)
                    else:
                        esb_id_val = item.get('id') or item.get(f"{entity.lower().split('_')[-1]}ID") or item.get('coaNo') or item.get('code') or item.get('name')
                        esb_id = str(esb_id_val) if esb_id_val else "unknown"
                    
                    # Use (company_id, entity, esb_id) uniquely
                    staging_values.append((entity, esb_id, company_id, json.dumps(item), datetime.now(timezone.utc)))
                    
                    if entity == "PRODUCT":
                        product_values.append((
                            esb_id, company_id, parsed_item.productName, parsed_item.productCode, parsed_item.bomName, 
                            parsed_item.categoryName, parsed_item.subCategoryName, parsed_item.categoryTypeName, 
                            bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True, parsed_item.barcode, parsed_item.uomName, 
                            parsed_item.purchasePrice, parsed_item.sellPrice, parsed_item.stock, 
                            bool(parsed_item.hasVariant) if parsed_item.hasVariant is not None else False, 
                            bool(parsed_item.isRawMaterial) if parsed_item.isRawMaterial is not None else False, 
                            bool(parsed_item.isProduction) if parsed_item.isProduction is not None else False, 
                            parsed_item.imageUrl
                        ))
                    elif entity == "CATEGORY":
                        category_values.append((
                            esb_id, company_id, parsed_item.categoryCode, parsed_item.categoryName,
                            parsed_item.categoryTypeName, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))
                    elif entity == "PRODUCT_SUB_CATEGORY":
                        sub_category_values.append((
                            esb_id, company_id, parsed_item.categoryID, parsed_item.subCategoryCode,
                            parsed_item.subCategoryName, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))
                    elif entity == "PRODUCT_UNIT":
                        unit_values.append((
                            esb_id, company_id, parsed_item.unitCode, parsed_item.unitName, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))
                    elif entity == "BOM":
                        bom_values.append((
                            esb_id, company_id, parsed_item.productID, parsed_item.bomCode,
                            parsed_item.bomName, parsed_item.outputQty, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))
                    elif entity == "BRANCH_PRODUCT":
                        branch_product_values.append((
                            esb_id, company_id, parsed_item.branchID, parsed_item.productID,
                            parsed_item.stock, parsed_item.availableStock, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))
                    elif entity == "PRICELIST":
                        pricelist_values.append((
                            esb_id, company_id, parsed_item.productID, parsed_item.branchID,
                            parsed_item.price, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))
                    elif entity == "BRANCH":
                        branch_values.append((
                            esb_id, company_id, parsed_item.branchName, parsed_item.branchCode, True,
                            parsed_item.locationName, parsed_item.stock, parsed_item.availableStock
                        ))
                    elif entity == "EMPLOYEE":
                        emp_group = getattr(parsed_item, 'employeeGroup', None)
                        branch_id = getattr(parsed_item, 'branch_id', 'UNKNOWN')
                        status = getattr(parsed_item, 'status', 'ACTIVE')
                        employee_values.append((
                            esb_id, company_id, parsed_item.full_name, parsed_item.position,
                            emp_group, status, branch_id
                        ))
                    elif entity == "SUPPLIER":
                        sup_category = getattr(parsed_item, 'supplierCategory', None)
                        status = getattr(parsed_item, 'status', 'ACTIVE')
                        supplier_values.append((
                            esb_id, company_id, parsed_item.name, parsed_item.type,
                            sup_category, status
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
                        is_raw_material, is_production, image_url
                    )
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, product_code = EXCLUDED.product_code, bom_name = EXCLUDED.bom_name,
                        category_name = EXCLUDED.category_name, sub_category_name = EXCLUDED.sub_category_name,
                        category_type_name = EXCLUDED.category_type_name, flag_active = EXCLUDED.flag_active,
                        barcode = EXCLUDED.barcode, uom_name = EXCLUDED.uom_name, purchase_price = EXCLUDED.purchase_price,
                        sell_price = EXCLUDED.sell_price, stock = EXCLUDED.stock, has_variant = EXCLUDED.has_variant,
                        is_raw_material = EXCLUDED.is_raw_material, is_production = EXCLUDED.is_production, image_url = EXCLUDED.image_url
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
                    INSERT INTO md_sub_categories (esb_id, company_id, category_esb_id, code, name, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        category_esb_id = EXCLUDED.category_esb_id, code = EXCLUDED.code, name = EXCLUDED.name, flag_active = EXCLUDED.flag_active
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
                    INSERT INTO md_branch_products (esb_id, company_id, branch_esb_id, product_esb_id, stock, available_stock, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        branch_esb_id = EXCLUDED.branch_esb_id, product_esb_id = EXCLUDED.product_esb_id,
                        stock = EXCLUDED.stock, available_stock = EXCLUDED.available_stock, flag_active = EXCLUDED.flag_active
                """, branch_product_values)

            if pricelist_values:
                pricelist_values = list({v[0]: v for v in pricelist_values}.values())
                execute_values(cur, """
                    INSERT INTO md_pricelists (esb_id, company_id, product_esb_id, branch_esb_id, price, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        product_esb_id = EXCLUDED.product_esb_id, branch_esb_id = EXCLUDED.branch_esb_id,
                        price = EXCLUDED.price, flag_active = EXCLUDED.flag_active
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
            
            if page >= total_pages:
                break
            
            page += 1

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
                
            endpoints = get_all_endpoints()
            for ep in endpoints:
                entity = ep["entity"]
                path = ep["path"]
                is_report = ep.get("is_report", False)
                
                # For reports, pass date ranges
                d_from = historical_start if is_report else None
                d_to = today_str if is_report else None
                
                sync_endpoint_data.delay(
                    company_id=company_id,
                    esb_token=esb_token,
                    entity=entity,
                    path=path,
                    date_from=d_from,
                    date_to=d_to
                )
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
