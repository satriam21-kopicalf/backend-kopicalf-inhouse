import re

with open("app/services/aggregation.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace in _fetch_company_master_data
content = content.replace('result["entities"][entity] = row[0] if row else 0', 'result["entities"][entity] = row["cnt"] if row else 0')

# Replace in _fetch_company_trx_counts
content = content.replace('row[0] if row else 0', 'row["cnt"] if row else 0')
content = content.replace('str(row[1]) if row and row[1] else None', 'str(row["earliest"]) if row and row.get("earliest") else None')
content = content.replace('str(row[2]) if row and row[2] else None', 'str(row["latest"]) if row and row.get("latest") else None')
content = content.replace('row[3].isoformat() if row and row[3] else None', 'row["last_sync"].isoformat() if row and row.get("last_sync") else None')

# Replace in _fetch_company_report_data
old_trx_sql = """            WHERE company_id = %s AND entity_type = %s
              AND doc_date BETWEEN %s AND %s
            ORDER BY doc_date DESC
            LIMIT %s
        """, (company_id, entity_type, date_from, date_to, limit))"""
new_trx_sql = """            WHERE company_id = %s AND entity_type = %s
              AND doc_date >= %s AND doc_date < %s
            ORDER BY doc_date DESC
            LIMIT %s
        """, (company_id, entity_type, date_from, date_to + timedelta(days=1), limit))"""
content = content.replace(old_trx_sql, new_trx_sql)

content = content.replace('payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])', 'payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])')
content = content.replace('str(row[1]) if row[1] else None', 'str(row["doc_date"]) if row.get("doc_date") else None')
content = content.replace('row[2]', 'row["status"]')
content = content.replace('row[3].isoformat() if row[3] else None', 'row["synced_at"].isoformat() if row.get("synced_at") else None')

old_trx_count = """        # Get total count
        cur.execute(\"\"\"
            SELECT count(*)
            FROM trx_raw_staging
            WHERE company_id = %s AND entity_type = %s
              AND doc_date BETWEEN %s AND %s
        \"\"\", (company_id, entity_type, date_from, date_to))
        result["count"] = cur.fetchone()[0]"""
new_trx_count = """        # Get total count
        cur.execute(\"\"\"
            SELECT count(*) as cnt
            FROM trx_raw_staging
            WHERE company_id = %s AND entity_type = %s
              AND doc_date >= %s AND doc_date < %s
        \"\"\", (company_id, entity_type, date_from, date_to + timedelta(days=1)))
        row = cur.fetchone()
        result["count"] = row["cnt"] if row else 0"""
content = content.replace(old_trx_count, new_trx_count)

# Wait, let's just do regex or manual targeted for direct reports
content = re.sub(
    r"AND period_start >= %s AND period_end <= %s\s+ORDER BY period_start DESC\s+\"\"\", \(company_id, report_type, date_from, date_to\)",
    r"AND period_start >= %s AND period_end < %s\n            ORDER BY period_start DESC\n        \"\"\", (company_id, report_type, date_from, date_to + timedelta(days=1))",
    content
)
content = content.replace('raw_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])', 'raw_data = row["raw_data"] if isinstance(row["raw_data"], dict) else json.loads(row["raw_data"])')

# get_integration_hub_summary
content = content.replace('trx_totals[row[0]] = {', 'trx_totals[row["entity_type"]] = {')
content = content.replace('"count": row[1],', '"count": row["count"],')
content = content.replace('str(row[2]) if row[2] else None,', 'str(row["earliest"]) if row.get("earliest") else None,')
content = content.replace('str(row[3]) if row[3] else None,', 'str(row["latest"]) if row.get("latest") else None,')
content = content.replace('"companies": row[4],', '"companies": row["companies"],')

content = content.replace('report_totals[row[0]] = {', 'report_totals[row["report_type"]] = {')
content = content.replace('"lines": row[1],', '"lines": row["lines"],')
content = content.replace('"companies": row[2],', '"companies": row["companies"],')

content = content.replace('sync_status.setdefault(row[0], {})[row[1]] = {', 'sync_status.setdefault(row["entity_type"], {})[row["status"]] = {')
content = content.replace('"count": row[2],', '"count": row["n"],')
content = content.replace('row[3].isoformat() if row[3] else None,', 'row["last_run"].isoformat() if row.get("last_run") else None,')

content = content.replace('"id": row[0],', '"id": row["id"],')
content = content.replace('"code": row[1],', '"code": row["esb_company_code"],')
content = content.replace('"name": row[2],', '"name": row["company_name"],')
content = content.replace('"branches": row[3],', '"branches": row["branches"],')
content = content.replace('"products": row[4],', '"products": row["products"],')
content = content.replace('"trx_records": row[5],', '"trx_records": row["trx_records"],')
content = content.replace('"report_lines": row[6],', '"report_lines": row["report_lines"],')

with open("app/services/aggregation.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done replacing.")
