import sys
import json
sys.path.append('.')
from app.services.trx_engine import TRX_INDEX_VIEW
from cross_check_endpoints import get_esb_endpoints

with open('api_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find fields for each endpoint
docs = {}
for item in data:
    if item.get('type') == 'get':
        url = item.get('url', '').replace('{{base_url}}', '').rstrip('/')
        fields = []
        if 'success' in item and 'fields' in item['success']:
            for group in item['success']['fields']:
                for field in item['success']['fields'][group]:
                    fields.append(field.get('field', ''))
        
        docs[url] = fields

print("--- FIELD CHECK ---")
for entity, cfg in TRX_INDEX_VIEW.items():
    path = cfg['index_path']
    doc_num = cfg.get('doc_num_field')
    doc_date = cfg.get('doc_date_field')
    status = cfg.get('status_field')
    
    # Try to find matching url in docs
    matched_url = None
    for u in docs:
        if u == path or u == f"/{path.lstrip('/')}":
            matched_url = u
            break
            
    if not matched_url:
        print(f"[{entity}] '{path}' - SKIPPED (endpoint not in docs)")
        continue
        
    esb_fields = docs[matched_url]
    print(f"[{entity}] '{path}'")
    for f_name, f_val in [('doc_num_field', doc_num), ('doc_date_field', doc_date), ('status_field', status)]:
        if f_val and f_val not in esb_fields:
            # Maybe it's nested e.g. result.docNum
            found = any(f_val in ef or ef in f_val for ef in esb_fields)
            if not found:
                print(f"  WARNING: {f_name} '{f_val}' not found in ESB docs fields for this endpoint!")
            else:
                print(f"  OK (nested): {f_name} '{f_val}'")
        elif f_val:
            print(f"  OK: {f_name} '{f_val}'")
