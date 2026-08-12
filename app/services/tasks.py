import os
import json
import httpx
import typing
from datetime import datetime, timezone
from psycopg2.extras import execute_values
from app.core.worker import celery_app
from app.core.db import get_db_connection
from app.schemas.esb import ESBProductModel, ESBCategoryModel, ESBBranchModel, ESBEmployeeModel, ESBSupplierModel, ESBGenericModel

ESB_API_BASE_URL = os.getenv("ESB_CORE_URL", "https://stg-erp.esb.co.id")

class CircuitBreakerOpenException(Exception):
    pass

class ESBClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None
        self.error_count = 0
        self.circuit_open = False
        # Increase timeout for large data loads
        self._http_client = httpx.Client(timeout=60.0)
        self._login()
        
    def _login(self):
        url = f"{ESB_API_BASE_URL}/auth/login"
        payload = {"username": self.username, "password": self.password}
        try:
            response = self._http_client.post(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            data = response.json()
            self.token = data.get("result", {}).get("accessToken")
            if not self.token:
                raise ValueError("No access token found in login response")
        except Exception as e:
            print(f"Login failed: {e}")
            raise e

    def get(self, path, params=None):
        if self.circuit_open:
            raise CircuitBreakerOpenException("Circuit is open due to consecutive failures")
            
        if not self.token:
            self._login()
            
        url = f"{ESB_API_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        try:
            response = self._http_client.get(url, headers=headers, params=params)
            if response.status_code == 401:
                # Token might have expired, try logging in again
                self._login()
                headers["Authorization"] = f"Bearer {self.token}"
                response = self._http_client.get(url, headers=headers, params=params)
            
            if response.status_code >= 500:
                self._record_error()
                response.raise_for_status()
            
            # Reset on success
            self.error_count = 0
            return response.json()
        except Exception as e:
            self._record_error()
            raise e
            
    def _record_error(self):
        self.error_count += 1
        if self.error_count >= 3:
            self.circuit_open = True



@celery_app.task
def sync_master_data():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # We use a hardcoded default credential since company_configs only had tokens
    # Ideally, company_configs should have username/password, but for this demo:
    username = os.getenv("ESB_USERNAME", "SAECLF")
    password = os.getenv("ESB_PASSWORD", "Abcd1234!")
    
    try:
        client = ESBClient(username, password)
    except Exception as e:
        print("Failed to initialize ESBClient", e)
        return
        
    # Get batch size from engine_settings
    cur.execute("SELECT sync_batch_size FROM engine_settings WHERE id = 1")
    settings = typing.cast(dict[str, typing.Any] | None, cur.fetchone())
    batch_size = settings['sync_batch_size'] if settings else 1000

    # Log start of sync
    cur.execute(
        "INSERT INTO sync_history (entity_type, status) VALUES (%s, %s) RETURNING id",
        ('MASTER_DATA_ALL', 'STARTED')
    )
    result = typing.cast(dict[str, typing.Any] | None, cur.fetchone())
    if result is None:
        raise RuntimeError("Failed to create sync history record")
    history_id = result['id']
    conn.commit()
    
    endpoints_to_sync: list[dict[str, typing.Any]] = [
        {"entity": "PRODUCT", "path": "/product/list", "schema": ESBProductModel},
        {"entity": "BRANCH", "path": "/branch", "schema": ESBBranchModel},
        {"entity": "CATEGORY", "path": "/product/category", "schema": ESBCategoryModel},
        {"entity": "EMPLOYEE", "path": "/employee", "schema": ESBEmployeeModel},
        {"entity": "SUPPLIER", "path": "/supplier", "schema": ESBSupplierModel},
        
        # Product Data extensions
        {"entity": "PRODUCT_SUB_CATEGORY", "path": "/product/subcategory", "schema": ESBGenericModel},
        {"entity": "PRODUCT_UNIT", "path": "/product/unit", "schema": ESBGenericModel},
        {"entity": "BRANCH_PRODUCT", "path": "/product/branch", "schema": ESBGenericModel},
        {"entity": "PRICELIST", "path": "/product/pricelist", "schema": ESBGenericModel},
        {"entity": "CUSTOMER_PRICELIST", "path": "/product/customer_pricelist", "schema": ESBGenericModel},
        {"entity": "BOM", "path": "/product/bom", "schema": ESBGenericModel},
        {"entity": "DOCUMENT_TEMPLATE", "path": "/product/document_template", "schema": ESBGenericModel},
        {"entity": "FOOD_COST_CALC", "path": "/product/food_cost_calc", "schema": ESBGenericModel},
        
        # POS Data
        {"entity": "POS_MENU", "path": "/pos/menu", "schema": ESBGenericModel},
        {"entity": "POS_USER", "path": "/pos/user", "schema": ESBGenericModel},
        {"entity": "POS_TABLE", "path": "/pos/table", "schema": ESBGenericModel},
        {"entity": "POS_PROMO", "path": "/pos/promotion", "schema": ESBGenericModel},
        {"entity": "POS_VOUCHER", "path": "/pos/voucher", "schema": ESBGenericModel},
        {"entity": "POS_TX", "path": "/pos/transaction", "schema": ESBGenericModel},
        {"entity": "POS_GUEST", "path": "/pos/guest", "schema": ESBGenericModel},
        {"entity": "POS_SYS", "path": "/pos/system", "schema": ESBGenericModel},
        
        # Accounting Data
        {"entity": "ACC_COA", "path": "/accounting/coa", "schema": ESBGenericModel},
        {"entity": "ACC_CASHFLOW_CAT", "path": "/accounting/cashflow_category", "schema": ESBGenericModel},
        {"entity": "ACC_CURRENCY", "path": "/accounting/currency", "schema": ESBGenericModel},
        {"entity": "ACC_TAX", "path": "/accounting/tax", "schema": ESBGenericModel},
        {"entity": "ACC_RECURRING_JRNL", "path": "/accounting/recurring_journal", "schema": ESBGenericModel},
        {"entity": "ACC_BANK", "path": "/accounting/bank", "schema": ESBGenericModel},
        {"entity": "ACC_COST_CENTER", "path": "/accounting/cost_center", "schema": ESBGenericModel},
        {"entity": "ACC_PURPOSE", "path": "/accounting/purpose", "schema": ESBGenericModel},
        
        # Company & HR Data
        {"entity": "COMP_BRAND", "path": "/company/brand", "schema": ESBGenericModel},
        {"entity": "COMP_EMP_GROUP", "path": "/employee/group", "schema": ESBGenericModel},
        {"entity": "COMP_USER_ROLE", "path": "/employee/user_role", "schema": ESBGenericModel},
        {"entity": "COMP_DELIVERY", "path": "/company/delivery", "schema": ESBGenericModel},
        {"entity": "COMP_SYS_CONFIG", "path": "/company/system_config", "schema": ESBGenericModel},
        {"entity": "COMP_MKT", "path": "/company/marketing", "schema": ESBGenericModel},
        
        # Partner & Vendor Data
        {"entity": "PARTNER_CUSTOMER", "path": "/partner/customer", "schema": ESBGenericModel},
        {"entity": "PARTNER_TENANT", "path": "/partner/tenant", "schema": ESBGenericModel},
        {"entity": "PARTNER_SALES_REP", "path": "/partner/sales_rep", "schema": ESBGenericModel},
    ]
    
    total_processed = 0
    has_error = False
    error_msg = ""
    
    for ep in endpoints_to_sync:
        entity = ep["entity"]
        path = ep["path"]
        schema_cls = ep["schema"]
        
        page = 1
        
        while True:
            try:
                # Attempt to fetch data from ERP using pagination
                try:
                    data = client.get(path, params={"page": page, "limit": batch_size})
                    records = []
                    total_pages = 1
                    
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict):
                        # Extract pagination info if exists
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
                        
                except Exception as api_err:
                    print(f"API call failed for {entity} page {page}: {api_err}.")
                    break # Break pagination loop on api error
                
                if not records:
                    break # Auto-stop if no records returned
                
                # Prepare bulk insert values
                staging_values = []
                product_values = []
                branch_values = []
                employee_values = []
                supplier_values = []
                dlq_values = []
                
                for item in records:
                    try:
                        # Validate using Pydantic
                        parsed_item = schema_cls(**item)
                        if entity == "PRODUCT":
                            esb_id = str(parsed_item.productID)
                        elif entity == "BRANCH":
                            esb_id = str(parsed_item.branchID)
                        else:
                            esb_id = getattr(parsed_item, "esb_id", "unknown")
                        
                        # 1. Upsert to staging list
                        staging_values.append((entity, esb_id, json.dumps(item), datetime.now(timezone.utc)))
                        
                        # 2. Transform/Classify into Canonical Tables lists
                        if entity == "PRODUCT":
                            product_values.append((
                                esb_id, parsed_item.productName, parsed_item.productCode, parsed_item.bomName, 
                                parsed_item.categoryName, parsed_item.subCategoryName, parsed_item.categoryTypeName, 
                                parsed_item.flagActive, parsed_item.barcode, parsed_item.uomName, 
                                parsed_item.purchasePrice, parsed_item.sellPrice, parsed_item.stock, 
                                parsed_item.hasVariant, parsed_item.isRawMaterial, parsed_item.isProduction, 
                                parsed_item.imageUrl
                            ))
                        elif entity == "BRANCH":
                            branch_values.append((
                                esb_id, parsed_item.branchName, parsed_item.branchCode, True,
                                parsed_item.locationName, parsed_item.stock, parsed_item.availableStock
                            ))
                        elif entity == "EMPLOYEE":
                            emp_group = getattr(parsed_item, 'employeeGroup', None)
                            branch_id = getattr(parsed_item, 'branch_id', 'UNKNOWN')
                            status = getattr(parsed_item, 'status', 'ACTIVE')
                            employee_values.append((
                                esb_id, parsed_item.full_name, parsed_item.position,
                                emp_group, status, branch_id
                            ))
                        elif entity == "SUPPLIER":
                            sup_category = getattr(parsed_item, 'supplierCategory', None)
                            status = getattr(parsed_item, 'status', 'ACTIVE')
                            supplier_values.append((
                                esb_id, parsed_item.name, parsed_item.type,
                                sup_category, status
                            ))
                        total_processed += 1
                    except Exception as ve:
                        dlq_values.append((entity, json.dumps(item), str(ve)))
                
                # Execute Bulk Upserts
                if staging_values:
                    execute_values(cur, """
                        INSERT INTO esb_raw_staging (entity_type, esb_id, raw_data, updated_at)
                        VALUES %s
                        ON CONFLICT (entity_type, esb_id) DO UPDATE SET
                            raw_data = EXCLUDED.raw_data,
                            updated_at = EXCLUDED.updated_at
                    """, staging_values)
                
                if product_values:
                    execute_values(cur, """
                        INSERT INTO md_products (
                            esb_id, name, product_code, bom_name, category_name, sub_category_name, category_type_name, 
                            flag_active, barcode, uom_name, purchase_price, sell_price, stock, has_variant, 
                            is_raw_material, is_production, image_url
                        )
                        VALUES %s
                        ON CONFLICT (esb_id) DO UPDATE SET
                            name = EXCLUDED.name, product_code = EXCLUDED.product_code, bom_name = EXCLUDED.bom_name,
                            category_name = EXCLUDED.category_name, sub_category_name = EXCLUDED.sub_category_name,
                            category_type_name = EXCLUDED.category_type_name, flag_active = EXCLUDED.flag_active,
                            barcode = EXCLUDED.barcode, uom_name = EXCLUDED.uom_name, purchase_price = EXCLUDED.purchase_price,
                            sell_price = EXCLUDED.sell_price, stock = EXCLUDED.stock, has_variant = EXCLUDED.has_variant,
                            is_raw_material = EXCLUDED.is_raw_material, is_production = EXCLUDED.is_production, image_url = EXCLUDED.image_url
                    """, product_values)
                
                if branch_values:
                    execute_values(cur, """
                        INSERT INTO md_outlets (esb_id, name, branch_code, is_active, location_name, stock, available_stock)
                        VALUES %s
                        ON CONFLICT (esb_id) DO UPDATE SET
                            name = EXCLUDED.name, branch_code = EXCLUDED.branch_code, is_active = EXCLUDED.is_active,
                            location_name = EXCLUDED.location_name, stock = EXCLUDED.stock, available_stock = EXCLUDED.available_stock
                    """, branch_values)
                    
                if employee_values:
                    execute_values(cur, """
                        INSERT INTO md_employees (esb_id, name, role, employee_group, status, branch_id)
                        VALUES %s
                        ON CONFLICT (esb_id) DO UPDATE SET
                            name = EXCLUDED.name, role = EXCLUDED.role, employee_group = EXCLUDED.employee_group,
                            status = EXCLUDED.status, branch_id = EXCLUDED.branch_id
                    """, employee_values)
                    
                if supplier_values:
                    execute_values(cur, """
                        INSERT INTO md_suppliers (esb_id, name, type, supplier_category, status)
                        VALUES %s
                        ON CONFLICT (esb_id) DO UPDATE SET
                            name = EXCLUDED.name, type = EXCLUDED.type, supplier_category = EXCLUDED.supplier_category,
                            status = EXCLUDED.status
                    """, supplier_values)
                    
                if dlq_values:
                    execute_values(cur, """
                        INSERT INTO dlq_logs (entity_type, raw_payload, error_reason)
                        VALUES %s
                    """, dlq_values)

                conn.commit()
                
                # Check pagination bounds
                if page >= total_pages:
                    break
                
                page += 1

            except CircuitBreakerOpenException:
                has_error = True
                error_msg = "Circuit breaker opened during sync."
                break
            except Exception as e:
                has_error = True
                error_msg = f"Failed fetching {entity} page {page}: {str(e)}"
                break
            
    # Update sync history
    status = "FAILED" if has_error else "SUCCESS"
    cur.execute(
        """
        UPDATE sync_history SET status = %s, records_processed = %s, error_message = %s, completed_at = %s
        WHERE id = %s
        """,
        (status, total_processed, error_msg, datetime.now(timezone.utc), history_id)
    )
    conn.commit()

    cur.close()
    conn.close()

@celery_app.task
def sync_master_data_router():
    from datetime import datetime, timezone
    import pytz
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get settings
        cur.execute("SELECT work_hours_interval_minutes, morning_window_interval_minutes FROM engine_settings WHERE id = 1")
        settings = typing.cast(typing.Any, cur.fetchone())
        if not settings:
            return "No engine settings found"
            
        work_interval = settings['work_hours_interval_minutes']
        morning_interval = settings['morning_window_interval_minutes']
        
        # Determine current window (Asia/Jakarta)
        jkt_tz = pytz.timezone('Asia/Jakarta')
        now_jkt = datetime.now(jkt_tz)
        current_hour = now_jkt.hour
        current_minute = now_jkt.minute
        current_time_float = current_hour + (current_minute / 60.0)
        
        is_morning_window = 2.5 <= current_time_float <= 8.0  # 02:30 to 08:00
        is_work_hours = not is_morning_window
        
        target_interval = morning_interval if is_morning_window else work_interval
        
        # Check last successful sync
        cur.execute("SELECT completed_at FROM sync_history WHERE entity_type = 'MASTER_DATA_ALL' AND status = 'SUCCESS' ORDER BY id DESC LIMIT 1")
        last_sync = typing.cast(typing.Any, cur.fetchone())
        
        should_run = False
        if last_sync and last_sync.get('completed_at'):
            last_sync_time = last_sync['completed_at']
            # Postgres timestamp with time zone is returned as UTC-aware datetime
            delta_minutes = (datetime.now(timezone.utc) - last_sync_time).total_seconds() / 60.0
            if delta_minutes >= target_interval:
                should_run = True
        else:
            should_run = True # Never run before
            
        if should_run:
            print(f"Triggering sync_master_data. Interval matched: {target_interval} minutes.")
            sync_master_data.delay()
            return f"Triggered sync (interval {target_interval})"
        else:
            print(f"Skipping sync. Target interval {target_interval} mins not yet reached.")
            return "Skipped sync"
            
    finally:
        cur.close()
        conn.close()
