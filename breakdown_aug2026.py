#!/usr/bin/env python3
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv('DB_POOLER_URL')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

print('='*80)
print('DATA BREAKDOWN - PERIODE 2026-08-01 HINGGA 2026-08-31')
print('='*80)

# 1. Overall Summary
print('\n[1] OVERALL SUMMARY')
print('-'*50)
cur.execute("""
    SELECT
        COUNT(DISTINCT h.sales_num) as total_transactions,
        COUNT(l.sales_num) as total_line_items,
        SUM(l.qty) as total_qty,
        SUM(l.total) as total_revenue
    FROM esb_data.report_pos_sales_head h
    LEFT JOIN esb_data.report_pos_sales l ON h.company_id = l.company_id AND h.sales_num = l.sales_num
    WHERE h.company_id = 1
    AND h.sales_date >= '2026-08-01' AND h.sales_date <= '2026-08-31'
""")
r = cur.fetchone()
print(f'Total Transactions (heads): {r[0]:,}')
print(f'Total Line Items: {r[1]:,}')
print(f'Total Qty Sold: {r[2]:,.0f}')
print(f'Total Revenue: Rp {r[3]:,.0f}')

# 2. Daily Breakdown
print('\n[2] DAILY BREAKDOWN')
print('-'*50)
cur.execute("""
    SELECT
        h.sales_date,
        COUNT(DISTINCT h.sales_num) as transactions,
        COUNT(l.sales_num) as items,
        SUM(l.qty) as qty,
        SUM(l.total) as revenue
    FROM esb_data.report_pos_sales_head h
    LEFT JOIN esb_data.report_pos_sales l ON h.company_id = l.company_id AND h.sales_num = l.sales_num
    WHERE h.company_id = 1
    AND h.sales_date >= '2026-08-01' AND h.sales_date <= '2026-08-31'
    GROUP BY h.sales_date
    ORDER BY h.sales_date
""")
daily = cur.fetchall()
for d in daily:
    print(f'{d[0]} | Tx: {d[1]:>4} | Items: {d[2]:>5} | Qty: {d[3]:>5,.0f} | Revenue: Rp {d[4]:>12,.0f}')

# 3. By Branch
print('\n[3] BY BRANCH')
print('-'*50)
cur.execute("""
    SELECT
        h.branch_name,
        COUNT(DISTINCT h.sales_num) as transactions,
        SUM(l.total) as revenue
    FROM esb_data.report_pos_sales_head h
    LEFT JOIN esb_data.report_pos_sales l ON h.company_id = l.company_id AND h.sales_num = l.sales_num
    WHERE h.company_id = 1
    AND h.sales_date >= '2026-08-01' AND h.sales_date <= '2026-08-31'
    GROUP BY h.branch_name
    ORDER BY revenue DESC
""")
branches = cur.fetchall()
for b in branches:
    print(f'{b[0]:<40} | Tx: {b[1]:>4} | Revenue: Rp {b[2]:>12,.0f}')

# 4. Top Selling Products
print('\n[4] TOP 15 SELLING PRODUCTS')
print('-'*50)
cur.execute("""
    SELECT
        l.menu_name,
        l.menu_category_name,
        SUM(l.qty) as total_qty,
        SUM(l.total) as revenue
    FROM esb_data.report_pos_sales l
    WHERE l.company_id = 1
    AND l.sales_date >= '2026-08-01' AND l.sales_date <= '2026-08-31'
    GROUP BY l.menu_name, l.menu_category_name
    ORDER BY total_qty DESC
    LIMIT 15
""")
products = cur.fetchall()
for i, p in enumerate(products, 1):
    print(f'{i:>2}. {p[0]:<35} [{p[1]:<15}] | Qty: {p[2]:>6,.0f} | Revenue: Rp {p[3]:>10,.0f}')

# 5. By Category
print('\n[5] BY CATEGORY')
print('-'*50)
cur.execute("""
    SELECT
        l.menu_category_name,
        COUNT(l.*) as items,
        SUM(l.qty) as qty,
        SUM(l.total) as revenue
    FROM esb_data.report_pos_sales l
    WHERE l.company_id = 1
    AND l.sales_date >= '2026-08-01' AND l.sales_date <= '2026-08-31'
    GROUP BY l.menu_category_name
    ORDER BY revenue DESC
""")
cats = cur.fetchall()
for c in cats:
    print(f'{c[0]:<25} | Items: {c[2]:>6,.0f} | Revenue: Rp {c[3]:>12,.0f}')

# 6. By Status
print('\n[6] BY TRANSACTION STATUS')
print('-'*50)
cur.execute("""
    SELECT
        h.status_name,
        COUNT(*) as count,
        SUM(h.grand_total) as revenue
    FROM esb_data.report_pos_sales_head h
    WHERE h.company_id = 1
    AND h.sales_date >= '2026-08-01' AND h.sales_date <= '2026-08-31'
    GROUP BY h.status_name
    ORDER BY count DESC
""")
statuses = cur.fetchall()
for s in statuses:
    print(f'{s[0]:<25} | Count: {s[1]:>6} | Revenue: Rp {s[2]:>12,.0f}')

# 7. Statistics
print('\n[7] STATISTICS')
print('-'*50)
cur.execute("""
    SELECT
        AVG(items_per_tx) as avg_items,
        AVG(qty_per_tx) as avg_qty,
        AVG(revenue_per_tx) as avg_revenue,
        MIN(revenue_per_tx) as min_revenue,
        MAX(revenue_per_tx) as max_revenue
    FROM (
        SELECT
            h.sales_num,
            COUNT(l.sales_num) as items_per_tx,
            COALESCE(SUM(l.qty), 0) as qty_per_tx,
            COALESCE(SUM(l.total), 0) as revenue_per_tx
        FROM esb_data.report_pos_sales_head h
        LEFT JOIN esb_data.report_pos_sales l ON h.company_id = l.company_id AND h.sales_num = l.sales_num
        WHERE h.company_id = 1
        AND h.sales_date >= '2026-08-01' AND h.sales_date <= '2026-08-31'
        GROUP BY h.sales_num
    ) tx_stats
""")
stats = cur.fetchone()
print(f'Average Items per Transaction: {stats[0]:.2f}')
print(f'Average Qty per Transaction: {stats[1]:.2f}')
print(f'Average Revenue per Transaction: Rp {stats[2]:,.0f}')
print(f'Min Transaction: Rp {stats[3]:,.0f}')
print(f'Max Transaction: Rp {stats[4]:,.0f}')

conn.close()
print('\n' + '='*80)
print('END OF BREAKDOWN')
print('='*80)
