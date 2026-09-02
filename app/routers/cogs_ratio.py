from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
import pytz

from app.database import get_db_connection
from app.utils.response import success_response, error_response

router = APIRouter()

JAKARTA = pytz.timezone('Asia/Jakarta')

def calculate_cogs_metrics(conn, period: str, branch_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Calculate COGS ratio metrics per branch for a given period.

    Returns:
        List of dicts with branch-level COGS metrics including:
        - branchId, branchCode, branchName, branchType, period
        - revenue, cogs, cogsRatio, targetCogsRatio, gap
        - teoretisUsage, actualUsage, usageRatio
        - flagged, trend, lastUpdated
    """
    query = """
    SELECT 
        m.branch_id,
        m.branch_code,
        m.branch_name,
        m.branch_type,
        %s as period,
        
        -- Revenue from POS sales
        COALESCE(SUM(sh.net_total), 0) as revenue,
        
        -- COGS calculated from stock movements
        COALESCE(
            (
                SELECT COALESCE(SUM(sm.qty * p.cost_price), 0)
                FROM esb_data.stock_movements sm
                JOIN esb_data.products p ON sm.product_id = p.product_id
                WHERE sm.branch_id = m.branch_id
                AND DATE_TRUNC('month', sm.created_at) = %s
                AND sm.movement_type IN ('USAGE', 'WASTE', 'TRANSFER_OUT')
            ), 
            0
        ) as cogs,
        
        -- Default target COGS ratio (65%)
        65.0 as target_cogs_ratio,
        
        -- Theoretical usage based on BOM and sales
        COALESCE(
            (
                SELECT COALESCE(SUM(shl.qty * (
                    SELECT COALESCE(SUM(bi.qty_per_unit), 0)
                    FROM esb_data.bom_items bi
                    WHERE bi.product_id = shl.product_id
                )), 0)
                FROM esb_data.report_pos_sales_head sh
                JOIN esb_data.report_pos_sales shl ON sh.sales_num = shl.sales_num
                WHERE sh.branch_id = m.branch_id
                AND DATE_TRUNC('month', sh.sales_date) = %s
            ),
            0
        ) as teoretis_usage,
        
        -- Actual usage from stock movements
        COALESCE(
            (
                SELECT COALESCE(SUM(sm.qty * p.cost_price), 0)
                FROM esb_data.stock_movements sm
                JOIN esb_data.products p ON sm.product_id = p.product_id
                WHERE sm.branch_id = m.branch_id
                AND DATE_TRUNC('month', sm.created_at) = %s
                AND sm.movement_type IN ('USAGE', 'WASTE', 'TRANSFER_OUT')
            ),
            0
        ) as actual_usage,
        
        -- Get last sync timestamp
        MAX(sh.synced_at) as last_updated
    FROM esb_data.master_branches m
    LEFT JOIN esb_data.report_pos_sales_head sh ON m.branch_id = sh.branch_id
        AND DATE_TRUNC('month', sh.sales_date) = %s
    WHERE m.is_active = true
    """

    params = [period, period, period, period, period]

    if branch_type:
        query += " AND m.branch_type = %s"
        params.append(branch_type)

    query += """
    GROUP BY m.branch_id, m.branch_code, m.branch_name, m.branch_type
    ORDER BY m.branch_type, m.branch_name
    """

    with conn.cursor() as cursor:
        cursor.execute(query, params)
        results = cursor.fetchall()

        metrics = []
        for row in results:
            revenue = float(row[4]) if row[4] else 0
            cogs = float(row[5]) if row[5] else 0
            target_cogs = float(row[6]) if row[6] else 65.0
            teoretis_usage = float(row[7]) if row[7] else 0
            actual_usage = float(row[8]) if row[8] else 0
            last_updated = row[9] if row[9] else datetime.now(JAKARTA).strftime('%Y-%m-%d')

            # Calculate derived metrics
            cogs_ratio = (cogs / revenue * 100) if revenue > 0 else 0
            gap = cogs_ratio - target_cogs
            usage_ratio = (actual_usage / teoretis_usage * 100) if teoretis_usage > 0 else 0

            # Flag branches that need investigation (usage > 105% or COGS > target + 10%)
            flagged = usage_ratio > 105 or cogs_ratio > target_cogs + 10

            # Determine trend (simplified - would need historical data for real trend)
            trend = 'flat'
            if cogs_ratio > target_cogs + 5:
                trend = 'up'
            elif cogs_ratio < target_cogs - 5:
                trend = 'down'

            metrics.append({
                'branchId': row[0],
                'branchCode': row[1],
                'branchName': row[2],
                'branchType': row[3],
                'period': period,
                'revenue': revenue,
                'cogs': cogs,
                'cogsRatio': round(cogs_ratio, 1),
                'targetCogsRatio': target_cogs,
                'gap': round(gap, 1),
                'teoretisUsage': teoretis_usage,
                'actualUsage': actual_usage,
                'usageRatio': round(usage_ratio, 1),
                'flagged': flagged,
                'trend': trend,
                'lastUpdated': str(last_updated)[:10] if isinstance(last_updated, datetime) else last_updated
            })

        return metrics

@router.get("/cogs-ratio")
async def get_cogs_ratio(
    period: str = Query(..., description="Period in YYYY-MM format"),
    branch_type: Optional[str] = Query(None, description="Filter by branch type: OUTLET, HUB WH, HUB CK")
):
    """
    Get COGS ratio analysis for all branches for a given period.
    
    Returns branch-level metrics including:
    - Revenue and COGS per branch
    - COGS ratio vs target (default 65%)
    - Usage ratio (actual vs theoretical)
    - Flagging for branches needing investigation
    """
    try:
        conn = get_db_connection()
        metrics = calculate_cogs_metrics(conn, period, branch_type)
        conn.close()

        # Calculate summary KPIs
        if metrics:
            total_branches = len(metrics)
            flagged_branches = sum(1 for m in metrics if m['flagged'])
            avg_cogs = sum(m['cogsRatio'] for m in metrics) / total_branches
            avg_usage = sum(m['usageRatio'] for m in metrics) / total_branches
            total_revenue = sum(m['revenue'] for m in metrics)
            total_cogs = sum(m['cogs'] for m in metrics)

            summary = {
                'totalBranches': total_branches,
                'flaggedBranches': flagged_branches,
                'avgCogsRatio': round(avg_cogs, 1),
                'avgUsageRatio': round(avg_usage, 1),
                'totalRevenue': total_revenue,
                'totalCogs': total_cogs
            }
        else:
            summary = {
                'totalBranches': 0,
                'flaggedBranches': 0,
                'avgCogsRatio': 0,
                'avgUsageRatio': 0,
                'totalRevenue': 0,
                'totalCogs': 0
            }

        return success_response({
            'summary': summary,
            'data': metrics
        })

    except Exception as e:
        return error_response(f"Failed to calculate COGS ratio: {str(e)}", 500)

@router.get("/cogs-ratio/{branch_id}")
async def get_cogs_ratio_by_branch(
    branch_id: int,
    period: str = Query(..., description="Period in YYYY-MM format")
):
    """
    Get detailed COGS ratio analysis for a specific branch.
    """
    try:
        conn = get_db_connection()
        query = """
        SELECT 
            m.branch_id,
            m.branch_code,
            m.branch_name,
            m.branch_type,
            %s as period,
            
            COALESCE(SUM(sh.net_total), 0) as revenue,
            COALESCE(
                (SELECT COALESCE(SUM(sm.qty * p.cost_price), 0)
                 FROM esb_data.stock_movements sm
                 JOIN esb_data.products p ON sm.product_id = p.product_id
                 WHERE sm.branch_id = %s
                 AND DATE_TRUNC('month', sm.created_at) = %s
                 AND sm.movement_type IN ('USAGE', 'WASTE', 'TRANSFER_OUT')), 0
            ) as cogs,
            65.0 as target_cogs_ratio,
            MAX(sh.synced_at) as last_updated
        FROM esb_data.master_branches m
        LEFT JOIN esb_data.report_pos_sales_head sh ON m.branch_id = sh.branch_id
            AND DATE_TRUNC('month', sh.sales_date) = %s
        WHERE m.branch_id = %s
        GROUP BY m.branch_id, m.branch_code, m.branch_name, m.branch_type
        """

        with conn.cursor() as cursor:
            cursor.execute(query, (period, branch_id, period, period, branch_id))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return error_response("Branch not found", 404)

            revenue = float(result[4]) if result[4] else 0
            cogs = float(result[5]) if result[5] else 0
            target_cogs = float(result[6]) if result[6] else 65.0
            last_updated = result[7] if result[7] else datetime.now(JAKARTA).strftime('%Y-%m-%d')

            cogs_ratio = (cogs / revenue * 100) if revenue > 0 else 0
            gap = cogs_ratio - target_cogs

        conn.close()

        return success_response({
            'branchId': result[0],
            'branchCode': result[1],
            'branchName': result[2],
            'branchType': result[3],
            'period': period,
            'revenue': revenue,
            'cogs': cogs,
            'cogsRatio': round(cogs_ratio, 1),
            'targetCogsRatio': target_cogs,
            'gap': round(gap, 1),
            'lastUpdated': str(last_updated)[:10] if isinstance(last_updated, datetime) else last_updated
        })

    except Exception as e:
        return error_response(f"Failed to get COGS ratio for branch: {str(e)}", 500)
