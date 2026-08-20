import sys
sys.path.append('.')
from app.services.trx_engine import TRX_INDEX_VIEW
from cross_check_endpoints import get_esb_endpoints

esb_eps = get_esb_endpoints()
backend_eps = {k: v['index_path'] for k, v in TRX_INDEX_VIEW.items()}

print(f'Backend endpoints found: {len(backend_eps)}')

print("--- ENDPOINT MISMATCH REPORT ---")
esb_urls = [e['url'] for e in esb_eps]
mismatches = 0
for entity, path in backend_eps.items():
    exact = False
    for esb in esb_eps:
        # Some esb urls have trailing slashes or parameters, but for index they usually match
        # Let's normalize
        e_url = esb['url'].rstrip('/')
        if e_url == path or e_url == f"/{path.lstrip('/')}" or e_url.startswith(path + "/") or e_url.startswith(path + ":"):
            exact = True
            break
    
    if not exact:
        mismatches += 1
        print(f"[{entity}] '{path}' NOT FOUND exactly in ESB GET endpoints.")
        parts = path.split('/')[-1].replace('-', ' ')
        print(f"   Suggestions from ESB docs:")
        for esb in esb_eps:
            if parts.lower() in esb['url'].replace('-', ' ').lower() or parts.lower() in esb['title'].lower():
                print(f"      - {esb['url']} ({esb['title']})")
        print()

if mismatches == 0:
    print("All backend endpoints match ESB GET endpoints perfectly!")
