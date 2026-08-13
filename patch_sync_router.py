import os

file_path = "d:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove @celery_app.task
old1 = """@celery_app.task
def sync_endpoint_data(company_id: int, esb_token: str, entity: str, path: str, date_from: typing.Optional[str] = None, date_to: typing.Optional[str] = None):"""
new1 = """def sync_endpoint_data(company_id: int, esb_token: str, entity: str, path: str, date_from: typing.Optional[str] = None, date_to: typing.Optional[str] = None):"""
content = content.replace(old1, new1)

# 2. Insert sync_company_data
old2 = """@celery_app.task
def sync_master_data():"""
new2 = """@celery_app.task
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
def sync_master_data():"""
content = content.replace(old2, new2)

# 3. Replace inner loop
old3 = """            endpoints = get_all_endpoints()
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
                )"""
new3 = """            sync_company_data.delay(company_id, esb_token, historical_start, today_str)"""
content = content.replace(old3, new3)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("tasks.py patched successfully for sequential sync orchestration.")
