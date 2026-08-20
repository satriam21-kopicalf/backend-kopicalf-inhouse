import json
import ast

def get_backend_endpoints():
    with open('app/services/trx_engine.py', 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read(), filename='app/services/trx_engine.py')
    
    endpoints = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'TRX_INDEX_VIEW':
                if isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant):
                            entity = k.value
                            if isinstance(v, ast.Dict):
                                for vk, vv in zip(v.keys, v.values):
                                    if isinstance(vk, ast.Constant) and vk.value == 'index_path':
                                        if isinstance(vv, ast.Constant):
                                            endpoints[entity] = vv.value
    return endpoints

def get_esb_endpoints():
    with open('api_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    endpoints = []
    for item in data:
        if item.get('type') == 'get':
            url = item.get('url', '')
            endpoints.append({
                'url': url.replace('{{base_url}}', ''),
                'title': item.get('title', '')
            })
    return endpoints

backend_eps = get_backend_endpoints()
esb_eps = get_esb_endpoints()

print("--- ENDPOINT MISMATCH REPORT ---")
esb_urls = [e['url'] for e in esb_eps]
for entity, path in backend_eps.items():
    # Attempt to find exact or partial match
    exact = False
    for esb in esb_eps:
        # ESB urls might have things like /product/bom, while backend has /production/bill-of-material
        # Let's just check exact match first
        if esb['url'] == path or esb['url'] == f"/{path.lstrip('/')}":
            exact = True
            break
    
    if not exact:
        print(f"Backend Entity '{entity}' uses path '{path}' which is NOT FOUND exactly in ESB GET endpoints.")
        # Try to suggest
        parts = path.split('/')[-1].replace('-', ' ')
        print(f"   Suggestions from ESB docs:")
        for esb in esb_eps:
            if parts.lower() in esb['url'].replace('-', ' ').lower() or parts.lower() in esb['title'].lower():
                print(f"      - {esb['url']} ({esb['title']})")
        print()

print("Done.")
