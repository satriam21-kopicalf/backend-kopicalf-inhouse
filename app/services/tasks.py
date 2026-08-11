import os
import json
import httpx
import typing
from datetime import datetime, timezone
from app.core.worker import celery_app
from app.core.db import get_db_connection
from app.schemas.esb import ESBProductModel, ESBCategoryModel, ESBBranchModel, ESBEmployeeModel, ESBSupplierModel, ESBGenericModel

ESB_API_BASE_URL = os.getenv("ESB_API_BASE_URL", "https://stg7.esb.co.id/core-stg")

class CircuitBreakerOpenException(Exception):
    pass

class ESBClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None
        self.error_count = 0
        self.circuit_open = False
        self._http_client = httpx.Client(timeout=10.0)
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

    def get(self, path):
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
            response = self._http_client.get(url, headers=headers)
            if response.status_code == 401:
                # Token might have expired, try logging in again
                self._login()
                headers["Authorization"] = f"Bearer {self.token}"
                response = self._http_client.get(url, headers=headers)
            
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
        
        try:
            # Attempt to fetch data from ERP
            try:
                data = client.get(path)
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
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
                print(f"API call failed for {entity}: {api_err}. No fallback data will be used.")
                records = []
            
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
                    
                    # 1. Upsert to staging
                    cur.execute(
                        """
                        INSERT INTO esb_raw_staging (entity_type, esb_id, raw_data, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (entity_type, esb_id) DO UPDATE SET
                            raw_data = EXCLUDED.raw_data,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (entity, esb_id, json.dumps(item), datetime.now(timezone.utc))
                    )
                    
                    # 2. Transform/Classify into Canonical Tables
                    if entity == "PRODUCT":
                        cur.execute(
                            """
                            INSERT INTO md_products (esb_id, name, product_code, bom_name, category_name, sub_category_name, category_type_name, flag_active)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (esb_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                product_code = EXCLUDED.product_code,
                                bom_name = EXCLUDED.bom_name,
                                category_name = EXCLUDED.category_name,
                                sub_category_name = EXCLUDED.sub_category_name,
                                category_type_name = EXCLUDED.category_type_name,
                                flag_active = EXCLUDED.flag_active
                            """,
                            (esb_id, parsed_item.productName, parsed_item.productCode, parsed_item.bomName, parsed_item.categoryName, parsed_item.subCategoryName, parsed_item.categoryTypeName, parsed_item.flagActive)
                        )
                    elif entity == "BRANCH":
                        cur.execute(
                            """
                            INSERT INTO md_outlets (esb_id, name, branch_code, is_active)
                            VALUES (%s, %s, %s, TRUE)
                            ON CONFLICT (esb_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                branch_code = EXCLUDED.branch_code
                            """,
                            (esb_id, parsed_item.branchName, parsed_item.branchCode)
                        )
                    elif entity == "EMPLOYEE":
                        cur.execute(
                            """
                            INSERT INTO md_employees (esb_id, name, role)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (esb_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                role = EXCLUDED.role
                            """,
                            (esb_id, parsed_item.full_name, parsed_item.position)
                        )
                    elif entity == "SUPPLIER":
                        cur.execute(
                            """
                            INSERT INTO md_suppliers (esb_id, name, type)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (esb_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                type = EXCLUDED.type
                            """,
                            (esb_id, parsed_item.name, parsed_item.type)
                        )
                    total_processed += 1
                except Exception as ve:
                    # Log validation failures to DLQ logs
                    cur.execute(
                        """
                        INSERT INTO dlq_logs (entity_type, raw_payload, error_reason)
                        VALUES (%s, %s, %s)
                        """,
                        (entity, json.dumps(item), str(ve))
                    )
                    
            conn.commit()
        except CircuitBreakerOpenException:
            has_error = True
            error_msg = "Circuit breaker opened during sync."
            break
        except Exception as e:
            has_error = True
            error_msg = f"Failed fetching {entity}: {str(e)}"
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
