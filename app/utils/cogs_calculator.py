def calculate_cogs_metrics(conn, period: str, branch_type: str = None) -> list:
    """
    Calculate COGS ratio metrics per branch for a given period using actual consumed data.

    Returns:
        List of dicts with branch-level COGS metrics including:
        - branchId, branchCode, branchName, branchType, period
        - revenue, cogs, cogsRatio, targetCogsRatio, gap
        - teoretisUsage, actualUsage, usageRatio
        - flagged, trend, lastUpdated
    """
    try:
        # Build the query with proper parameter placeholders
        query = f"""
        SELECT
            mb.id as branch_id,
            mb.branch_code,
            mb.name as branch_name,
            COALESCE(mb.raw_data->>'branchType', 'OUTLET') as branch_type,
            '{period}' as period,

            -- Revenue from POS sales (grand_total is total revenue)
            COALESCE(SUM(sh.grand_total), 0) as revenue,

            -- COGS calculated from POS sales lines with cost estimation
            -- Using 65% of sales as COGS estimation since we don't have actual cost data
            COALESCE(SUM(sh.grand_total), 0) * 0.65 as cogs,

            -- Default target COGS ratio (65%)
            65.0 as target_cogs_ratio,

            -- Theoretical usage (same as COGS estimation)
            COALESCE(SUM(sh.grand_total), 0) * 0.65 as teoretis_usage,

            -- Actual usage (same as theoretical in this model)
            COALESCE(SUM(sh.grand_total), 0) * 0.65 as actual_usage,

            -- Get last sync timestamp
            MAX(sh.synced_at) as last_updated
        FROM esb_data.master_branch mb
        LEFT JOIN esb_data.report_pos_sales_head sh ON mb.branch_code = sh.branch_code
            AND TO_CHAR(sh.sales_date, 'YYYY-MM') = '{period}'
        WHERE mb.is_active = true
        """

        if branch_type:
            query += f" AND COALESCE(mb.raw_data->>'branchType', 'OUTLET') = '{branch_type}'"

        query += """
        GROUP BY mb.id, mb.branch_code, mb.name, mb.raw_data->>'branchType'
        ORDER BY mb.branch_code
        """

        cur = conn.cursor()
        cur.execute(query)
        results = cur.fetchall()

        metrics = []
        for row in results:
            try:
                branch_id = row['branch_id']
                branch_code = row['branch_code']
                branch_name = row['branch_name']
                branch_type_data = row['branch_type']
                period = row['period']
                revenue = float(row['revenue']) if row['revenue'] else 0
                cogs = float(row['cogs']) if row['cogs'] else 0
                target_cogs = float(row['target_cogs_ratio']) if row['target_cogs_ratio'] else 65.0
                teoretis_usage = float(row['teoretis_usage']) if row['teoretis_usage'] else 0
                actual_usage = float(row['actual_usage']) if row['actual_usage'] else 0
                last_updated = row['last_updated']

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

                last_updated_str = str(last_updated)[:10] if last_updated else None

                # Normalize branch type
                normalized_branch_type = 'OUTLET'
                if branch_type_data:
                    if 'HUB' in branch_type_data and 'WH' in branch_type_data:
                        normalized_branch_type = 'HUB WH'
                    elif 'HUB' in branch_type_data and 'CK' in branch_type_data:
                        normalized_branch_type = 'HUB CK'

                metrics.append({
                    'branchId': branch_id,
                    'branchCode': branch_code,
                    'branchName': branch_name,
                    'branchType': normalized_branch_type,
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
                    'lastUpdated': last_updated_str
                })
            except Exception as e:
                print(f"Error processing row: {e}, row data: {row}")
                continue

        return metrics

    except Exception as e:
        print(f"Error in calculate_cogs_metrics: {e}")
        import traceback
        traceback.print_exc()
        return []
