import psycopg2, os
from dotenv import load_dotenv
load_dotenv('D:/kopicalf-projection/backend-kopicalf-inhouse/.env')

TOKENS = {
    'CALF':   '5KVmOvhHSGhHhZi7JZTzFKUwr5nw80Ay5hyG5or1tT94ZXfKlUDjUl25cHrY',
    'CALF1': 'SOCsqZ6qW0F7YfuMpnASQpAAQJ3fzHWkL7CRywrjZueB3q3SfDXcIoicyDWz',
    'CALF2': '1ysCkQhwrAjwqa6VKGzpOZbp7xY3uSnGraR4lqEOL22ChKys0mTxCYW5WbTN',
    'CALF3': 'W9M6pUjaxltPZvHhYfMg8NrkGv1ufoNvT1oFeTHtCE9G3LuRMRdE3zYv53lr',
    'CALF4': 'pTjRz80Y68eIZ4n89iEcREISdXsv7Z2aWkyzD0cCkZrXWFJdYHaIR38hfHzk',
    'CALF5': 'UMfwdaTQrprC0K0VPNNgDPqReASoXM7NCo7NydUp81M5RY87CgfUU703SJpX',
    'CALF6': '8YAAMD0fzQYSsyVzNTOOK0rqRkFcD4p87RNhrWfole1mu9rkc4Pw38wiS13s',
    'CALF7': 'BZ9AEbOj7J69FrqilGrSWxsWnSkyBGeeoJzh1ITVGyCqlGjMSurBLfUwtmkU',
}

conn = psycopg2.connect(os.environ['DB_POOLER_URL'])
cur = conn.cursor()
for code, token in TOKENS.items():
    cur.execute(
        "UPDATE esb_data.company_configs SET static_token = %s, updated_at = NOW() WHERE esb_company_code = %s",
        (token, code),
    )
    print(f"{code}: updated {cur.rowcount} row(s)")
conn.commit()
cur.execute("SELECT esb_company_code, company_name, static_token IS NOT NULL AS has_token FROM esb_data.company_configs ORDER BY id")
for row in cur.fetchall():
    print(row)
conn.close()
