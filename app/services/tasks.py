import os
import json
import hashlib
import math
import httpx
import typing
from datetime import datetime, timezone, date, timedelta
from psycopg2.extras import execute_values, DictCursor
from app.core.worker import celery_app
from app.core.db import get_db_connection
import pytz
from croniter import croniter

JAKARTA = pytz.timezone("Asia/Jakarta")


def _cron_next(cron_expr: str, base=None):
    """Next run time for a cron expression, in Asia/Jakarta local time."""
    try:
        base = base or datetime.now(JAKARTA)
        return croniter(cron_expr, base).get_next(datetime)
    except Exception:
        return None

ESB_API_BASE_URL = os.getenv("ESB_CORE_URL", "https://services.esb.co.id/core")

# Fallback credentials from env (used when company_configs rows have no per-company creds)
ESB_FALLBACK_USERNAME = os.getenv("ESB_CORE_USERNAME", "CALFSUPERADMINOPS")
ESB_FALLBACK_PASSWORD = os.getenv("ESB_CORE_PASSWORD", "")

# Dynamic endpoint loading functions
def _get_endpoints_from_db(company_id: int = None, only_documented: bool = False, 
                          category: str = None, module: str = None) -> list:
    """Load endpoints dynamically from esb_data.endpoint_registry.
    
    Args:
        company_id: Filter by company_id (for per-company endpoints)
        only_documented: Only return endpoints documented in ESB API
        category: Filter by category ('master' or 'report')
        module: Filter by module (Product, POS, Accounting, etc.)
    
    Returns:
        List of endpoint dicts: {entity, path, id_field, response_shape, is_active, is_documented, category, module}
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        base = "SELECT * FROM esb_data.endpoint_registry WHERE is_active = true"
        params = []
        
        if company_id:
            base += " AND id IN (SELECT endpoint_id FROM esb_data.sync_schedules WHERE company_id = %s AND enabled = true)"
            params.append(company_id)
        if only_documented:
            base += " AND is_documented = true"
        if category:
            base += " AND category = %s"
            params.append(category)
        if module:
            base += " AND module = %s"
            params.append(module)
            
        cur.execute(base, params)
        endpoints = []
        for row in cur.fetchall():
            endpoints.append({
                "entity": row["entity"],
                "path": row["path"],
                "id_field": row["id_field"],
                "response_shape": row["response_shape"],
                "is_active": row["is_active"],
                "is_documented": row["is_documented"],
                "category": row["category"],
                "module": row["module"],
                "description": row.get("description", "")
            })
        return endpoints
    finally:
        cur.close()
        conn.close()

def _get_sync_schedules(company_id: int = None, module: str = None, 
                       enabled_only: bool = True) -> list:
    """Load sync schedules dynamically from esb_data.sync_schedules.
    
    Args:
        company_id: Filter by company_id
        module: Filter by module ('master' or 'report')
        enabled_only: Only return enabled schedules
    
    Returns:
        List of schedule dicts with joined endpoint and company info
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        base = """
            SELECT ss.*, er.entity, er.path, er.id_field, er.response_shape, er.category,
                   cc.esb_company_code, cc.company_name, cc.esb_username, cc.esb_password,
                   cc.static_token
            FROM esb_data.sync_schedules ss
            JOIN esb_data.endpoint_registry er ON ss.endpoint_id = er.id
            JOIN esb_data.company_configs cc ON ss.company_id = cc.id
            WHERE 1=1
        """
        params = []
        
        if company_id:
            base += " AND ss.company_id = %s"
            params.append(company_id)
        if module:
            base += " AND ss.module = %s"
            params.append(module)
        if enabled_only:
            base += " AND ss.enabled = true"
            
        cur.execute(base, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

def _get_due_schedules() -> list:
    """Get schedules that are due to run based on next_run timestamp."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute("""
            SELECT ss.*, er.entity, er.path, er.id_field, er.response_shape, er.category,
                   cc.esb_company_code, cc.company_name, cc.esb_username, cc.esb_password,
                   cc.static_token
            FROM esb_data.sync_schedules ss
            JOIN esb_data.endpoint_registry er ON ss.endpoint_id = er.id
            JOIN esb_data.company_configs cc ON ss.company_id = cc.id
            WHERE ss.enabled = true 
              AND ss.next_run <= NOW()
            ORDER BY ss.next_run ASC
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

PAGE_SIZE = 100  # verified safe; limit=10000 triggers Validation Error on several endpoints


class CircuitBreakerOpenException(Exception):
    pass


class ESBAuthError(Exception):
    pass


def _esb_login(username: str, password: str) -> str:
    """POST /auth/login -> base JWT."""
    res = httpx.post(
        f"{ESB_API_BASE_URL}/auth/login",
        json={"username": username, "password": password},
        timeout=20.0,
    )
    data = res.json()
    if res.status_code != 200 or data.get("status") != "ok":
        raise ESBAuthError(f"ESB login failed: {data.get('message') or res.status_code}")
    return data["result"]["accessToken"]


def _esb_switch_company(base_token: str, company_code: str, username: str, password: str) -> str:
    """POST /auth/login/company with base JWT -> company-scoped JWT.

    The base JWT is single-use for this call: on failure caused by an
    already-consumed/expired token we re-login once and retry.
    """
    res = httpx.post(
        f"{ESB_API_BASE_URL}/auth/login/company",
        headers={"Authorization": f"Bearer {base_token}"},
        json={"companyCode": company_code},
        timeout=20.0,
    )
    data = res.json()
    if res.status_code != 200 or data.get("status") != "ok":
        # retry once with a fresh base token (base JWT may have been consumed)
        fresh = _esb_login(username, password)
        res = httpx.post(
            f"{ESB_API_BASE_URL}/auth/login/company",
            headers={"Authorization": f"Bearer {fresh}"},
            json={"companyCode": company_code},
            timeout=20.0,
        )
        data = res.json()
        if res.status_code != 200 or data.get("status") != "ok":
            raise ESBAuthError(f"Company switch failed for {company_code}: {data.get('message')}")
    return data["result"]["accessToken"]


def _esb_company_token(company_code: str, username: str, password: str,
                       max_attempts: int = 4) -> str:
    """Full auth flow: login -> switch to company -> scoped JWT.

    Concurrent logins on the ESB can invalidate each other's base JWT,
    so we retry with backoff.
    """
    import time
    last_err = None
    for attempt in range(max_attempts):
        try:
            base = _esb_login(username, password)
            return _esb_switch_company(base, company_code, username, password)
        except ESBAuthError as e:
            last_err = e
            # "not linked" errors are transient session-release issues on ESB;
            # they need a longer wait before retrying
            wait = 20 if "not linked" in str(e).lower() else 2 * (attempt + 1)
            time.sleep(wait)
    raise last_err


class ESBClient:
    """HTTP client for ESB API with company-scoped token and single re-auth on 401."""

    def __init__(self, token: str, company_code: str = "", username: str = "", password: str = ""):
        self.token = token
        self.company_code = company_code
        self.username = username
        self.password = password
        self.error_count = 0
        self.circuit_open = False
        self._http = httpx.Client(timeout=60.0)

    def _reauth(self) -> bool:
        # Static tokens are long-lived; a 401 means the token was rotated on
        # the ESB side and we cannot refresh it locally -> only username/password
        # flow can re-auth.
        if not (self.company_code and self.username and self.password):
            return False
        try:
            self.token = _esb_company_token(self.company_code, self.username, self.password)
            return True
        except Exception:
            return False

    def get(self, path: str, params: typing.Optional[dict] = None):
        if self.circuit_open:
            raise CircuitBreakerOpenException("Circuit is open due to consecutive failures")

        response = self._http.get(
            f"{ESB_API_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
            params=params,
        )

        # ESB returns 200 with status=fail JSON on auth errors too; handle both
        if response.status_code == 401:
            if self._reauth():
                response = self._http.get(
                    f"{ESB_API_BASE_URL}{path}",
                    headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                    params=params,
                )

        if response.status_code >= 400:
            self._record_error()
            response.raise_for_status()

        body = response.json()
        if body.get("status") not in (None, "ok"):
            msg = body.get("message", "")
            code = body.get("code", "")
            if code == "EC03100001":  # invalid/expired token -> re-auth once
                if self._reauth():
                    response = self._http.get(
                        f"{ESB_API_BASE_URL}{path}",
                        headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                        params=params,
                    )
                    body = response.json()
                    if body.get("status") == "ok":
                        self.error_count = 0
                        return body
            raise RuntimeError(f"ESB error {code}: {msg} ({path})")

        self.error_count = 0
        return body

    def _record_error(self):
        self.error_count += 1
        if self.error_count >= 3:
            self.circuit_open = True


def _extract_page(body: dict, shape: str) -> typing.Tuple[list, int]:
    """Normalize response -> (records, total_pages). Handles array vs envelope."""
    result = body.get("result")
    if shape == "array":
        records = result if isinstance(result, list) else []
        return records, 1
    if isinstance(result, dict):
        records = result.get("data") or []
        count = result.get("count", 0)
        total_pages = max(1, math.ceil((count or len(records)) / PAGE_SIZE))
        return records, total_pages
    return [], 1


def _derive_esb_id(item: dict, id_field: str) -> str:
    val = item.get(id_field) or item.get("id") or item.get("ID")
    if val is None:
        return hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()
    return str(val)


# ─────────────────────────────────────────────────────────────────────────
# Per-endpoint normalizers -> (table, tuple) rows
# ─────────────────────────────────────────────────────────────────────────

def _normalize(entity: str, item: dict, esb_id: str, company_id: int):
    """Normalize ESB API response to database table format.
    Now targets esb_data.master_* tables instead of public.md_* tables.
    """
    if entity == "BRANCH":
        return ("esb_data.master_branch", (esb_id, company_id, item.get("branchName"), item.get("branchCode"),
                               True, None, None, None, json.dumps(item)))
    if entity == "PRODUCT":
        return ("esb_data.master_product", (esb_id, company_id, item.get("productName"), item.get("productCode") or "",
                                item.get("bomName"), item.get("categoryName"), item.get("subCategoryName"),
                                item.get("categoryTypeName"), bool(item.get("flagActive", 1)), json.dumps(item)))
    if entity == "CATEGORY":
        return ("esb_data.master_category", (esb_id, company_id, item.get("categoryCode"), item.get("categoryName"),
                                  item.get("categoryTypeName"), bool(item.get("flagActive", 1)),
                                  item.get("categoryTypeID"), item.get("notes"), json.dumps(item)))
    if entity == "PRODUCT_SUB_CATEGORY":
        return ("esb_data.master_sub_category", (esb_id, company_id, None, None, item.get("subCategoryName"),
                                      bool(item.get("flagActive", 1)), item.get("deadStockThreshold"), item.get("notes"), json.dumps(item)))
    if entity == "PRODUCT_UNIT":
        return ("esb_data.master_unit", (esb_id, company_id, item.get("metricName"), item.get("uomName"),
                             bool(item.get("flagActive", 1)), json.dumps(item)))
    if entity == "PRICELIST":
        ab = item.get("applicableBranch") or {}
        branch = None
        if ab.get("type") == "ALL":
            branch = "ALL"
        elif isinstance(ab.get("branches"), list) and ab["branches"]:
            branch = ",".join(str(b.get("branchID")) for b in ab["branches"] if b.get("branchID"))
        return ("esb_data.master_pricelist", (
            esb_id, company_id, item.get("productID"), branch, item.get("price") or 0,
            bool(item.get("flagActive", 1)), item.get("priceDate"), item.get("supplierName"),
            item.get("productName"), item.get("productCode"), item.get("unit"), item.get("currencyName"),
            item.get("expireDate"), item.get("pricelistNum"), item.get("productDetailID"),
            item.get("uomID"), item.get("currencyID"),
            json.dumps(ab, default=str), json.dumps(item)))
    if entity == "SUPPLIER":
        return ("esb_data.master_supplier", (esb_id, company_id, item.get("supplierName"), None, item.get("category"),
                                 "ACTIVE" if item.get("flagActive") else "INACTIVE",
                                 item.get("address"), item.get("contactPerson"), item.get("cellPhone"),
                                 item.get("dueDate"), item.get("supplierCategoryID"),
                                 bool(item.get("lockVAT", False)), bool(item.get("vatSubject", False)), json.dumps(item)))
    if entity == "CUSTOMER":
        return ("esb_data.master_customer", (esb_id, company_id, item.get("customerName"), item.get("customerCode") or "",
                                 str(item.get("customerCategoryID") or ""), item.get("customerCategoryName"),
                                 item.get("paymentDueDays") or 0, item.get("address"), item.get("picName"),
                                 item.get("picPhone"), bool(item.get("flagActive", 1)),
                                 bool(item.get("lockVat", 0)), json.dumps(item)))
    if entity == "BOM":
        return ("esb_data.master_bill_of_material", (esb_id, company_id, item.get("productID"), item.get("bomCode"), item.get("bomName"),
                            1.0, bool(item.get("flagActive", 1)), item.get("bomTypeID"),
                            item.get("bomTypeName"), item.get("productName"), item.get("uomName"), json.dumps(item)))
    if entity == "DOCUMENT_TEMPLATE":
        return ("esb_data.master_document_template", (esb_id, company_id, item.get("requestTemplateName"),
                                          item.get("requestTemplateTypeNames"), str(item.get("requestTemplateID")),
                                          bool(item.get("flagActive", 1)), json.dumps(item)))
    if entity == "ACC_PURPOSE":
        return ("esb_data.master_purpose", (esb_id, company_id, item.get("purposeName"), item.get("purposeAccount"),
                                item.get("purposeCoaNo"), json.dumps(item.get("purposeAppliedTo") or []),
                                bool(item.get("flagActive", True)), json.dumps(item)))
    if entity == "ACC_COST_CENTER":
        return ("esb_data.master_cost_center", (esb_id, company_id, item.get("costCenter"), item.get("costCenterName"),
                                    bool(item.get("flagActive", True)), json.dumps(item)))
    if entity == "ACC_COA":
        return ("esb_data.master_charts_of_account", (esb_id, company_id, item.get("coaNo"), item.get("coaLevel"),
                            item.get("description"), item.get("currency"),
                            str(item.get("branchID") or ""), bool(item.get("flagActive", 0)), json.dumps(item)))
    if entity == "COMP_PROJECT":
        return ("esb_data.master_project", (esb_id, company_id, item.get("projectName"), item.get("projectCode"),
                                bool(item.get("flagActive", True)), json.dumps(item)))
    if entity == "COMP_USER":
        return ("esb_data.master_user", (esb_id, company_id, item.get("username"), item.get("fullName"),
                             item.get("userRoleID"), item.get("userRoleDesc"),
                             bool(item.get("flagActive", 1)), json.dumps(item)))
    if entity == "PARTNER_CUST_CAT":
        return ("esb_data.master_customer_category", (esb_id, company_id, item.get("customerCategoryName"),
                                           bool(item.get("flagActive", 1)), json.dumps(item)))
    if entity == "PARTNER_SUPP_CAT":
        return ("esb_data.master_supplier_category", (esb_id, company_id, item.get("supplierCategoryName"), True, json.dumps(item)))
    if entity == "CUSTOMER_PRICELIST":
        return ("esb_data.master_customer_pricelist", (esb_id, company_id, item.get("customerName"),
                                           item.get("productName"), item.get("productCode"),
                                           item.get("uomName"), item.get("currencyName"),
                                           item.get("price") or 0, item.get("priceDate"),
                                           item.get("expireDate"), True, json.dumps(item)))
    if entity == "ACC_TAX":
        return ("esb_data.master_tax", (esb_id, company_id, item.get("taxName"), item.get("rate"),
                                      item.get("taxCode"), bool(item.get("flagActive", 1)), json.dumps(item)))
    if entity == "ACC_CASHFLOW_CAT":
        return ("esb_data.master_cashflow_category", (esb_id, company_id, item.get("name"),
                                               item.get("code"), bool(item.get("flagActive", 1)), json.dumps(item)))
    if entity == "ACC_APPROVAL_FLOW":
        return ("esb_data.master_approval_flow", (esb_id, company_id, item.get("name"),
                                          item.get("description"), bool(item.get("flagActive", 1)), json.dumps(item)))
    return ("esb_raw_staging", None)


UPSERTS = {
    "esb_data.master_branch": """
        INSERT INTO esb_data.master_branch (esb_id, company_id, name, branch_code, is_active, location_name, stock, available_stock, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, branch_code=EXCLUDED.branch_code, is_active=EXCLUDED.is_active,
            location_name=EXCLUDED.location_name, stock=EXCLUDED.stock, available_stock=EXCLUDED.available_stock,
            raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_product": """
        INSERT INTO esb_data.master_product (esb_id, company_id, name, product_code, bom_name, category_name,
            sub_category_name, category_type_name, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, product_code=EXCLUDED.product_code, bom_name=EXCLUDED.bom_name,
            category_name=EXCLUDED.category_name, sub_category_name=EXCLUDED.sub_category_name,
            category_type_name=EXCLUDED.category_type_name, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_category": """
        INSERT INTO esb_data.master_category (esb_id, company_id, code, name, type_name, flag_active, category_type_id, notes, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            code=EXCLUDED.code, name=EXCLUDED.name, type_name=EXCLUDED.type_name,
            flag_active=EXCLUDED.flag_active, category_type_id=EXCLUDED.category_type_id,
            notes=EXCLUDED.notes, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_sub_category": """
        INSERT INTO esb_data.master_sub_category (esb_id, company_id, category_esb_id, code, name, flag_active, dead_stock_threshold, notes, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            category_esb_id=EXCLUDED.category_esb_id, code=EXCLUDED.code, name=EXCLUDED.name,
            flag_active=EXCLUDED.flag_active, dead_stock_threshold=EXCLUDED.dead_stock_threshold,
            notes=EXCLUDED.notes, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_unit": """
        INSERT INTO esb_data.master_unit (esb_id, company_id, code, name, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            code=EXCLUDED.code, name=EXCLUDED.name, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_pricelist": """
        INSERT INTO esb_data.master_pricelist (esb_id, company_id, product_esb_id, branch_esb_id, price, flag_active,
            price_date, supplier_name, product_name, product_code, unit_name, currency, expired_date,
            pricelist_num, product_detail_esb_id, uom_id, currency_id, applicable_branch, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            product_esb_id=EXCLUDED.product_esb_id, branch_esb_id=EXCLUDED.branch_esb_id,
            price=EXCLUDED.price, flag_active=EXCLUDED.flag_active, price_date=EXCLUDED.price_date,
            supplier_name=EXCLUDED.supplier_name, product_name=EXCLUDED.product_name,
            product_code=EXCLUDED.product_code, unit_name=EXCLUDED.unit_name, currency=EXCLUDED.currency,
            expired_date=EXCLUDED.expired_date, pricelist_num=EXCLUDED.pricelist_num,
            product_detail_esb_id=EXCLUDED.product_detail_esb_id, uom_id=EXCLUDED.uom_id,
            currency_id=EXCLUDED.currency_id, applicable_branch=EXCLUDED.applicable_branch, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_supplier": """
        INSERT INTO esb_data.master_supplier (esb_id, company_id, name, type, supplier_category, status, address,
            contact_person, cell_phone, due_date, category_esb_id, lock_vat, vat_subject, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, supplier_category=EXCLUDED.supplier_category, status=EXCLUDED.status,
            address=EXCLUDED.address, contact_person=EXCLUDED.contact_person, cell_phone=EXCLUDED.cell_phone,
            due_date=EXCLUDED.due_date, category_esb_id=EXCLUDED.category_esb_id,
            lock_vat=EXCLUDED.lock_vat, vat_subject=EXCLUDED.vat_subject, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_customer": """
        INSERT INTO esb_data.master_customer (esb_id, company_id, name, code, category_esb_id, category_name,
            payment_due_days, address, pic_name, pic_phone, flag_active, lock_vat, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, code=EXCLUDED.code, category_esb_id=EXCLUDED.category_esb_id,
            category_name=EXCLUDED.category_name, payment_due_days=EXCLUDED.payment_due_days,
            address=EXCLUDED.address, pic_name=EXCLUDED.pic_name, pic_phone=EXCLUDED.pic_phone,
            flag_active=EXCLUDED.flag_active, lock_vat=EXCLUDED.lock_vat, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_bill_of_material": """
        INSERT INTO esb_data.master_bill_of_material (esb_id, company_id, product_esb_id, code, name, output_qty, flag_active,
            bom_type_id, bom_type_name, product_name, uom_name, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            product_esb_id=EXCLUDED.product_esb_id, code=EXCLUDED.code, name=EXCLUDED.name,
            output_qty=EXCLUDED.output_qty, flag_active=EXCLUDED.flag_active,
            bom_type_id=EXCLUDED.bom_type_id, bom_type_name=EXCLUDED.bom_type_name,
            product_name=EXCLUDED.product_name, uom_name=EXCLUDED.uom_name, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_document_template": """
        INSERT INTO esb_data.master_document_template (esb_id, company_id, name, document_type, template_code, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, document_type=EXCLUDED.document_type, template_code=EXCLUDED.template_code,
            flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_purpose": """
        INSERT INTO esb_data.master_purpose (esb_id, company_id, name, account, coa_no, applied_to, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, account=EXCLUDED.account, coa_no=EXCLUDED.coa_no,
            applied_to=EXCLUDED.applied_to, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_charts_of_account": """
        INSERT INTO esb_data.master_charts_of_account (esb_id, company_id, coa_no, coa_level, description, currency, branch_esb_id, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            coa_no=EXCLUDED.coa_no, coa_level=EXCLUDED.coa_level, description=EXCLUDED.description,
            currency=EXCLUDED.currency, branch_esb_id=EXCLUDED.branch_esb_id,
            flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_project": """
        INSERT INTO esb_data.master_project (esb_id, company_id, name, code, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, code=EXCLUDED.code, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_user": """
        INSERT INTO esb_data.master_user (esb_id, company_id, username, full_name, role_id, role_desc, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            username=EXCLUDED.username, full_name=EXCLUDED.full_name, role_id=EXCLUDED.role_id,
            role_desc=EXCLUDED.role_desc, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_customer_category": """
        INSERT INTO esb_data.master_customer_category (esb_id, company_id, name, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_supplier_category": """
        INSERT INTO esb_data.master_supplier_category (esb_id, company_id, name, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_customer_pricelist": """
        INSERT INTO esb_data.master_customer_pricelist (esb_id, company_id, customer_name, product_name, product_code,
            uom_name, currency_name, price, price_date, expire_date, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            customer_name=EXCLUDED.customer_name, product_name=EXCLUDED.product_name,
            product_code=EXCLUDED.product_code, uom_name=EXCLUDED.uom_name,
            currency_name=EXCLUDED.currency_name, price=EXCLUDED.price,
            price_date=EXCLUDED.price_date, expire_date=EXCLUDED.expire_date,
            flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_cost_center": """
        INSERT INTO esb_data.master_cost_center (esb_id, company_id, code, name, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            code=EXCLUDED.code, name=EXCLUDED.name, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    # Additional master tables for undocumented entities
    "esb_data.master_tax": """
        INSERT INTO esb_data.master_tax (esb_id, company_id, name, rate, code, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, rate=EXCLUDED.rate, code=EXCLUDED.code, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_cashflow_category": """
        INSERT INTO esb_data.master_cashflow_category (esb_id, company_id, name, code, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, code=EXCLUDED.code, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
    "esb_data.master_approval_flow": """
        INSERT INTO esb_data.master_approval_flow (esb_id, company_id, name, description, flag_active, raw_data)
        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
            name=EXCLUDED.name, description=EXCLUDED.description, flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()""",
}


def _is_engine_enabled(cur) -> bool:
    cur.execute("SELECT sync_enabled FROM engine_settings WHERE id = 1")
    row = cur.fetchone()
    return bool(row and row["sync_enabled"])


def sync_endpoint_data(company_id: int, client: ESBClient, entity: str, path: str,
                       id_field: str, shape: str):
    """Pull all pages of one endpoint for one company into staging + normalized tables."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute(
            "INSERT INTO sync_history (entity_type, status, company_id) VALUES (%s, %s, %s) RETURNING id",
            (entity, 'STARTED', company_id))
        history_id = cur.fetchone()['id']
        conn.commit()

        total_processed = 0
        has_error = False
        error_msg = ""
        page = 1
        total_pages = 1
        table_rows: typing.Dict[str, list] = {}

        while page <= total_pages:
            try:
                body = client.get(path, params={"page": page, "limit": PAGE_SIZE})
                records, total_pages = _extract_page(body, shape)
            except CircuitBreakerOpenException:
                has_error, error_msg = True, "Circuit breaker opened during sync."
                break
            except Exception as api_err:
                has_error = True
                error_msg = f"API call failed for {entity} page {page}: {api_err}"
                break

            staging_values = []
            for item in records:
                try:
                    esb_id = _derive_esb_id(item, id_field)
                    staging_values.append((entity, esb_id, company_id, json.dumps(item, default=str),
                                           datetime.now(timezone.utc)))
                    table, row = _normalize(entity, item, esb_id, company_id)
                    if row:
                        table_rows.setdefault(table, []).append(row)
                    total_processed += 1
                except Exception as ve:
                    cur.execute(
                        "INSERT INTO dlq_logs (entity_type, raw_payload, error_reason) VALUES (%s, %s, %s)",
                        (entity, json.dumps(item, default=str), str(ve)))

            if staging_values:
                staging_values = list({(v[0], v[1], v[2]): v for v in staging_values}.values())
                execute_values(cur, """
                    INSERT INTO esb_raw_staging (entity_type, esb_id, company_id, raw_data, updated_at)
                    VALUES %s ON CONFLICT (company_id, entity_type, esb_id) DO UPDATE SET
                        raw_data = EXCLUDED.raw_data, updated_at = EXCLUDED.updated_at
                """, staging_values, page_size=500)
            conn.commit()
            page += 1

        for table, rows in table_rows.items():
            if table in UPSERTS and rows:
                # Dedupe by natural key (first tuple element = esb_id) to avoid
                # "ON CONFLICT cannot affect row a second time" on batch upserts
                rows = list({r[0]: r for r in rows}.values())
                try:
                    execute_values(cur, UPSERTS[table], rows, page_size=500)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    has_error = True
                    error_msg = f"{table} upsert failed: {e}"

        status = "FAILED" if has_error else "SUCCESS"
        cur.execute(
            "UPDATE sync_history SET status=%s, records_processed=%s, error_message=%s, completed_at=%s WHERE id=%s",
            (status, total_processed, error_msg, datetime.now(timezone.utc), history_id))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _sync_product_details(company_id: int, client: ESBClient):
    """Pull /product/{id} details (productDetails array) into md_product_details."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute("""
            SELECT esb_id FROM md_products WHERE company_id = %s
              AND NOT EXISTS (
                SELECT 1 FROM md_product_details d WHERE d.company_id = %s AND d.product_esb_id = md_products.esb_id
              )
        """, (company_id, company_id))
        ids = [r['esb_id'] for r in cur.fetchall()]
        for esb_id in ids:
            try:
                body = client.get(f"/product/{esb_id}")
                result = body.get("result") or {}
                rows = []
                for pd in result.get("productDetails") or []:
                    rows.append((
                        str(pd.get("productDetailID")), company_id, esb_id,
                        pd.get("uomID"), pd.get("metricID"), pd.get("uomName"),
                        pd.get("qty"), pd.get("basePrice"), pd.get("SKU"),
                        bool(pd.get("isBase")), bool(pd.get("isStock")), bool(pd.get("isPurchase")),
                        bool(pd.get("isTransfer")), bool(pd.get("isSales")), bool(pd.get("flagActive", True))))
                if rows:
                    execute_values(cur, """
                        INSERT INTO md_product_details (esb_id, company_id, product_esb_id, uom_id, metric_id,
                            uom_name, qty, base_price, sku, is_base, is_stock, is_purchase, is_transfer, is_sales, flag_active, raw_data)
                        VALUES %s ON CONFLICT (company_id, esb_id) DO UPDATE SET
                            qty=EXCLUDED.qty, base_price=EXCLUDED.base_price, sku=EXCLUDED.sku,
                            is_base=EXCLUDED.is_base, is_stock=EXCLUDED.is_stock, is_purchase=EXCLUDED.is_purchase,
                            is_transfer=EXCLUDED.is_transfer, is_sales=EXCLUDED.is_sales,
                            flag_active=EXCLUDED.flag_active, raw_data=EXCLUDED.raw_data, updated_at=NOW()
                    """, rows)
                    conn.commit()
            except Exception:
                conn.rollback()
                continue
    finally:
        cur.close()
        conn.close()


def _get_due_entities(cur) -> list:
    """Return entities whose sync interval has elapsed (or never synced) using dynamic scheduling."""
    # First get schedules that are due based on next_run timestamp
    cur.execute("""
        SELECT DISTINCT er.entity 
        FROM esb_data.sync_schedules ss
        JOIN esb_data.endpoint_registry er ON ss.endpoint_id = er.id
        WHERE ss.enabled = true 
          AND ss.module = 'master'
          AND ss.next_run <= NOW()
    """)
    return [r["entity"] for r in cur.fetchall()]


def _mark_entity_synced(cur, entity: str):
    """Mark entity as synced by updating the corresponding schedules."""
    cur.execute("""
        SELECT id, cron_expr FROM esb_data.sync_schedules
        WHERE endpoint_id IN (
            SELECT id FROM esb_data.endpoint_registry WHERE entity = %s
        )
    """, (entity,))
    for row in cur.fetchall():
        cur.execute("""
            UPDATE esb_data.sync_schedules
            SET last_run = NOW(),
                next_run = COALESCE(%s, NOW() + INTERVAL '1 hour'),
                updated_at = NOW()
            WHERE id = %s
        """, (_cron_next(row["cron_expr"]), row["id"]))


@celery_app.task
def sync_company_data(company_id: int, company_code: str, username: str, password: str,
                      entities: list, static_token: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        if not _is_engine_enabled(cur):
            print("Engine disabled (engine_settings.sync_enabled=false). Skipping sync.")
            return
        if not entities:
            print("No due entities for this run.")
            return

        token = static_token
        if not token:
            try:
                # Serialize the login flow across parallel company tasks (lazy import:
                # trx_engine imports this module at load time)
                from app.services.trx_engine import _auth_locked_company_token
                token = _auth_locked_company_token(company_code, username, password)
            except ESBAuthError as e:
                cur.execute(
                    "INSERT INTO sync_history (entity_type, status, company_id, error_message, completed_at) VALUES (%s,%s,%s,%s,%s)",
                    ("AUTH", "FAILED", company_id, str(e), datetime.now(timezone.utc)))
                conn.commit()
                print(f"Auth failed for {company_code}: {e}")
                return
        else:
            print(f"Using static token for {company_code}")

        client = ESBClient(token, company_code, username, password)
        # Use dynamic endpoint registry instead of hardcoded arrays
        endpoints = _get_endpoints_from_db(company_id=company_id, category='master')
        for ep in endpoints:
            if ep["entity"] not in entities:
                continue
            if not _is_engine_enabled(cur):
                print("Engine disabled mid-sync. Aborting.")
                return
            try:
                sync_endpoint_data(company_id, client, ep["entity"], ep["path"], ep["id_field"], ep["response_shape"])
            except Exception as e:
                print(f"Error syncing {ep['entity']} for {company_code}: {e}")

        if "PRODUCT_DETAIL" in entities:
            try:
                _sync_product_details(company_id, client)
            except Exception as e:
                print(f"Product detail sync failed for {company_code}: {e}")
    finally:
        cur.close()
        conn.close()


@celery_app.task
def sync_all_companies(companies: list, entities: list):
    """Run sync_company_data sequentially for each company (avoids ESB auth races)."""
    for co in companies:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        enabled = _is_engine_enabled(cur)
        cur.close(); conn.close()
        if not enabled:
            print("Engine disabled mid-run. Aborting remaining companies.")
            return
        try:
            sync_company_data(
                company_id=co["company_id"],
                company_code=co["company_code"],
                username=co["username"],
                password=co["password"],
                entities=entities,
            )
        except Exception as e:
            print(f"Company {co['company_code']} sync failed: {e}")


@celery_app.task
def sync_master_data():


    """Spawn per-company sync tasks for all ACTIVE companies using per-company credentials."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute("SELECT sync_enabled FROM engine_settings WHERE id = 1")
        row = cur.fetchone()
        if not row or not row["sync_enabled"]:
            print("Engine disabled. No sync spawned.")
            return

        cur.execute("""
            SELECT id, esb_company_code, esb_username, esb_password, static_token
            FROM esb_data.company_configs WHERE is_active = true AND esb_company_code IS NOT NULL
        """)
        companies = cur.fetchall()
        if not companies:
            print("No active companies with esb_company_code found.")
            return

        # Per-entity scheduling: only pull entities whose interval has elapsed
        due_entities = _get_due_entities(cur)
        if not due_entities:
            print("No entities are due for sync.")
            return

        # Parallel per-company dispatch (Sprint 3): each company becomes its own
        # queue_master task. Concurrent ESB logins are serialized by the shared
        # esb_auth_lock inside sync_company_data, so parallelism is safe.
        for co in companies:
            username = co["esb_username"] or ESB_FALLBACK_USERNAME
            password = co["esb_password"] or ESB_FALLBACK_PASSWORD
            if not (co["static_token"] or (username and password)):
                continue
            sync_company_data.delay(
                company_id=co["id"],
                company_code=co["esb_company_code"],
                username=username,
                password=password,
                entities=due_entities,
                static_token=co["static_token"],
            )

        # Mark entities as synced (per-run granularity; company-level done inside task)
        for entity in due_entities:
            _mark_entity_synced(cur, entity)
        conn.commit()
    finally:
        cur.close()
        conn.close()


@celery_app.task
def dynamic_schedule_router():
    """Dynamic scheduling router that checks esb_data.sync_schedules and dispatches tasks.
    
    This replaces the old fixed-interval scheduling with cron-based dynamic scheduling.
    Runs every minute to check for due schedules and dispatches appropriate tasks.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled"
        
        # Get all due schedules
        due_schedules = _get_due_schedules()
        if not due_schedules:
            return "No due schedules"
        
        dispatched_count = 0
        for schedule in due_schedules:
            try:
                # Dispatch based on module type
                if schedule['module'] == 'master':
                    sync_company_data.delay(
                        company_id=schedule['company_id'],
                        company_code=schedule['esb_company_code'],
                        username=schedule['esb_username'],
                        password=schedule['esb_password'],
                        entities=[schedule['entity']],
                        static_token=schedule.get('static_token'),
                    )
                elif schedule['module'] == 'report':
                    celery_app.send_task("app.services.reports.sync_report", kwargs={
                        "report_type": schedule['entity'],
                        "company_id": schedule['company_id'],
                        "static_token": schedule.get('static_token'),
                    })
                elif schedule['module'] == 'pos':
                    # Daily sync: last 30 days to catch any missing historical data
                    # + today for real-time. UPSERT ensures no data loss on re-runs.
                    today_str = date.today().isoformat()
                    from_str = (date.today() - timedelta(days=30)).isoformat()
                    celery_app.send_task("app.services.reports.sync_pos_sales", kwargs={
                        "company_id": schedule['company_id'],
                        "date_from": from_str,
                        "date_to": today_str,
                    })

                # Update the schedule's next_run time using cron expression
                cur.execute("""
                    UPDATE esb_data.sync_schedules
                    SET last_run = NOW(),
                        next_run = COALESCE(%s, NOW() + INTERVAL '1 hour'),
                        updated_at = NOW()
                    WHERE id = %s
                """, (_cron_next(schedule['cron_expr']), schedule['id']))
                
                dispatched_count += 1
            except Exception as e:
                print(f"Error dispatching schedule {schedule['id']}: {e}")
                # Mark as failed but don't stop other schedules
                cur.execute("""
                    UPDATE esb_data.sync_schedules 
                    SET next_run = NOW() + INTERVAL '5 minutes',  -- Retry in 5 minutes
                        updated_at = NOW()
                    WHERE id = %s
                """, (schedule['id'],))
        
        conn.commit()
        return f"Dispatched {dispatched_count} schedules"
    finally:
        cur.close()
        conn.close()


@celery_app.task
def sync_master_data_router():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute("SELECT sync_enabled, work_hours_interval_minutes, morning_window_interval_minutes FROM engine_settings WHERE id = 1")
        settings = cur.fetchone()
        if not settings or not settings["sync_enabled"]:
            return "Engine disabled"

        work_interval = settings["work_hours_interval_minutes"]
        morning_interval = settings["morning_window_interval_minutes"]

        jkt_tz = pytz.timezone('Asia/Jakarta')
        now_jkt = datetime.now(jkt_tz)
        current_time_float = now_jkt.hour + (now_jkt.minute / 60.0)

        is_morning_window = 2.5 <= current_time_float <= 8.0
        target_interval = morning_interval if is_morning_window else work_interval

        cur.execute(
            "SELECT completed_at FROM sync_history WHERE entity_type = 'SYSTEM_SYNC_TRACKER' AND status = 'SUCCESS' ORDER BY id DESC LIMIT 1")
        last_sync = cur.fetchone()

        should_run = True
        if last_sync and last_sync["completed_at"]:
            delta_minutes = (datetime.now(timezone.utc) - last_sync["completed_at"]).total_seconds() / 60.0
            should_run = delta_minutes >= (target_interval - 0.5)

        if should_run:
            cur.execute(
                "INSERT INTO sync_history (entity_type, status, completed_at) VALUES ('SYSTEM_SYNC_TRACKER', 'SUCCESS', %s)",
                (datetime.now(timezone.utc),))
            conn.commit()
            sync_master_data.delay()

            # Dual-lane: dispatch TRX delta lane when any TRX_* entity is due.
            # send_task (by name) avoids a circular import with trx_engine.
            try:
                cur.execute("""
                    SELECT 1 FROM md_sync_schedules
                    WHERE enabled = true AND entity_type LIKE 'TRX\\_%%'
                      AND (last_synced_at IS NULL OR last_synced_at + (interval_minutes || ' minutes')::interval <= NOW())
                    LIMIT 1
                """)
                if cur.fetchone():
                    celery_app.send_task("app.services.trx_engine.delta_sync_trx")
            except Exception as e:
                print(f"TRX delta dispatch check failed: {e}")

            return f"Triggered sync (interval {target_interval} minutes)"
        return "Skipped sync"
    finally:
        cur.close()
        conn.close()
