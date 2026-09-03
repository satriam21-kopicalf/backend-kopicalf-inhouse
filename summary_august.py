#!/usr/bin/env python3
import psycopg2
import os

db_url = os.getenv("DB_POOLER_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

print("="*80)
print("POS DATA SUMMARY - AUGUST 2026")
print("="*80)

# Total counts
print("\n1. TOTAL COUNTS:")
cur.execute("SELECT COUNT(*) FROM esb_data.report_pos_sales_head")
heads = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM esb_data.report_pos_sales")
lines = cur.fetchone()[0]
print("   report_pos_sales_head: " + str(heads))
print("   report_pos_sales: " + str(lines))

# Check August 2026 data
print("\n2. AUGUST 2026 DATA:")
cur.execute("""
    SELECT COUNT(DISTINCT sales_num), COUNT(*)
    FROM esb_data.report_pos_sales_head
    WHERE sales_date >= '2026-08-01' AND sales_date <= '2026-08-31'
""")
aug_heads = cur.fetchone()
print("   August 2026 Heads: " + str(aug_heads[0]) + " unique sales")
print("   August 2026 Lines: checking...")

cur.execute("""
    SELECT COUNT(*)
    FROM esb_data.report_pos_sales
    WHERE sales_date >= '2026-08-01' AND sales_date <= '2026-08-31'
""")
aug_lines = cur.fetchone()[0]
print("   August 2026 Lines: " + str(aug_lines))

# Daily breakdown
print("\n3. DAILY BREAKDOWN (August 2026):")
cur.execute("""
    SELECT sales_date, COUNT(DISTINCT sales_num) as heads, COUNT(*) as lines
    FROM esb_data.report_pos_sales_head
    WHERE sales_date >= '2026-08-01' AND sales_date <= '2026-08-31'
    GROUP BY sales_date
    ORDER BY sales_date
""")
print("   Date        | Heads | Lines")
print("   " + "-"*35)
for r in cur.fetchall():
    print("   " + str(r[0]) + " | " + str(r[1]) + " | " + str(r[2]))

# Date range check
print("\n4. DATE RANGE:")
cur.execute("SELECT MIN(sales_date), MAX(sales_date) FROM esb_data.report_pos_sales_head")
range = cur.fetchone()
print("   From: " + str(range[0]))
print("   To: " + str(range[1]))

conn.close()
print("\n" + "="*80)
