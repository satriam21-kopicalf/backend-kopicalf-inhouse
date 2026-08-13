import psycopg2

DB_URI = 'postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019%23@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'

companies = [
    {"code": "CALF", "name": "PT Yuda Prawira Group", "token": "5KVmOvhHSGhHhZi7JZTzFKUwr5nw80Ay5hyG5or1tT94ZXfKlUDjUl25cHrY", "active": True},
    {"code": "CALF1", "name": "Calf Roastery", "token": "SOCsqZ6qW0F7YfuMpnASQpAAQJ3fzHWkL7CRywrjZueB3q3SfDXcIoicyDWz", "active": False},
    {"code": "CALF2", "name": "Calf Central Kitchen", "token": "1ysCkQhwrAjwqa6VKGzpOZbp7xY3uSnGraR4lqEOL22ChKys0mTxCYW5WbTN", "active": False},
    {"code": "CALF3", "name": "PT DAYUPRA SOLUSI PARTNER", "token": "W9M6pUjaxltPZvHhYfMg8NrkGv1ufoNvT1oFeTHtCE9G3LuRMRdE3zYv53lr", "active": False},
    {"code": "CALF4", "name": "Coffee Solution Indo", "token": "pTjRz80Y68eIZ4n89iEcREISdXsv7Z2aWkyzD0cCkZrXWFJdYHaIR38hfHzk", "active": False},
    {"code": "CALF5", "name": "Calf COTR", "token": "UMfwdaTQrprC0K0VPNNgDPqReASoXM7NCo7NydUp81M5RY87CgfUU703SJpX", "active": False},
    {"code": "CALF6", "name": "Calf Central Kitchen Food", "token": "8YAAMD0fzQYSsyVzNTOOK0rqRkFcD4p87RNhrWfole1mu9rkc4Pw38wiS13s", "active": False},
    {"code": "CALF7", "name": "Wasgee Tea", "token": "BZ9AEbOj7J69FrqilGrSWxsWnSkyBGeeoJzh1ITVGyCqlGjMSurBLfUwtmkU", "active": False}
]

def update_db():
    conn = psycopg2.connect(DB_URI)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Disable all existing
    cur.execute("UPDATE company_configs SET is_active = FALSE")
    
    for c in companies:
        # Upsert based on company_name or code. Wait, company_configs schema: 
        # id, company_name, esb_token, is_active, created_at, updated_at
        cur.execute("SELECT id FROM company_configs WHERE company_name = %s", (c['name'],))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE company_configs SET esb_token = %s, is_active = %s WHERE id = %s", (c['token'], c['active'], row[0]))
        else:
            cur.execute("INSERT INTO company_configs (company_name, esb_token, is_active) VALUES (%s, %s, %s)", (c['name'], c['token'], c['active']))
            
    print("Database updated successfully.")
    cur.execute("SELECT id, company_name, is_active FROM company_configs ORDER BY is_active DESC, id ASC")
    for r in cur.fetchall():
        print(r)

if __name__ == '__main__':
    update_db()
