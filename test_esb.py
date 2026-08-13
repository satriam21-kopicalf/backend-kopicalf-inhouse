import sys
import os
import json
import urllib.request
from urllib.error import HTTPError
sys.path.append('.')

import psycopg2
from psycopg2.extras import RealDictCursor

def fetch(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode('utf-8')
    except HTTPError as e:
        return e.code, e.read().decode('utf-8')

def test():
    conn = psycopg2.connect('postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019#@aws-0-ap-south-1.pooler.supabase.com:5432/postgres')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT esb_token FROM company_configs WHERE is_active = true LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("No active company_configs")
        return
        
    token = row['esb_token']
    base_url = "https://services.esb.co.id/core"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Testing with URL: {base_url}/product/stock-location")
    
    # 1. No param
    status1, text1 = fetch(f"{base_url}/product/stock-location?page=1&limit=10", headers)
    print("No param Status:", status1)
    print("No param snippet:", text1[:300])
        
    # 2. productDetailID
    cur.execute("SELECT esb_id FROM md_products LIMIT 1")
    prow = cur.fetchone()
    if prow:
        pid = prow['esb_id']
        status2, text2 = fetch(f"{base_url}/product/stock-location?productDetailID={pid}&page=1&limit=10", headers)
        print(f"With productDetailID={pid} Status:", status2)
        print(f"productDetailID={pid} snippet:", text2[:300])

    # 3. productID
    if prow:
        pid = prow['esb_id']
        status3, text3 = fetch(f"{base_url}/product/stock-location?productID={pid}&page=1&limit=10", headers)
        print(f"With productID={pid} Status:", status3)
        print(f"productID={pid} snippet:", text3[:300])

if __name__ == '__main__':
    test()
