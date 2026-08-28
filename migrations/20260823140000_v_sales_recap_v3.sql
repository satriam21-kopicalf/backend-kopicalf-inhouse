-- v3: field alignment with ERP sample —
--  * Sales Type = 'Void' for cancelled lines, 'Sales' otherwise (ERP semantic);
--    the OMS raw 'salesType' (POS Lite / SHOPEEFOOD / ...) is actually the
--    ERP "Order Mode" column.
--  * Order Mode from raw salesType.
--  * Timestamps trimmed to 'YYYY-MM-DD HH24:MI:SS' (no TZ suffix).
DROP VIEW IF EXISTS esb_data.v_sales_recap_detail;
CREATE VIEW esb_data.v_sales_recap_detail AS
SELECT
    l.company_id,
    l.sales_num,
    l.bill_num,
    CASE WHEN l.status_name ILIKE '%void%' OR l.status_name ILIKE '%cancel%'
         THEN 'Void' ELSE 'Sales' END                     AS sales_type,
    l.batch_id                                            AS batch_order,
    h.table_name,
    to_char(l.sales_date::date, 'YYYY-MM-DD')             AS sales_date,
    to_char(h.sales_date_in,  'YYYY-MM-DD HH24:MI:SS')    AS sales_date_in,
    to_char(h.sales_date_out, 'YYYY-MM-DD HH24:MI:SS')    AS sales_date_out,
    l.branch_code,
    l.branch_name,
    h.visit_purpose_name,
    h.member_code                                         AS regular_member_code,
    h.member_name                                         AS regular_member_name,
    (h.payments::jsonb -> 0 ->> 'paymentMethodName')      AS payment_method,
    l.menu_category_name,
    l.menu_category_detail_name,
    l.menu_name,
    l.menu_code,
    l.notes                                               AS menu_notes,
    l.raw_data::jsonb ->> 'salesType'                     AS order_mode,
    l.qty,
    l.price,
    l.subtotal,
    l.discount_value,
    l.service_charge,
    l.tax,
    l.vat                                                 AS vat,
    COALESCE((l.raw_data::jsonb ->> 'vatValue')::numeric, 0)       AS vat_amount,
    COALESCE((l.raw_data::jsonb ->> 'otherTaxValue')::numeric, 0)  AS other_tax_amount,
    l.total,
    ROUND(
        l.total
        - l.tax
        - COALESCE((l.raw_data::jsonb ->> 'vatValue')::numeric, 0)
        - COALESCE((l.raw_data::jsonb ->> 'otherTaxValue')::numeric, 0), 2) AS nett_sales,
    ROUND(
        CASE
            WHEN COALESCE((l.raw_data::jsonb ->> 'inclusivePrice')::numeric, 0) > 0
            THEN (l.raw_data::jsonb ->> 'inclusivePrice')::numeric * l.qty
                 / (1 + COALESCE(l.vat, 0) / 100.0)
            ELSE 0
        END, 2)                                           AS dpp,
    h.discount_total                                      AS bill_discount,
    h.grand_total                                         AS total_after_bill_discount,
    l.created_by                                          AS waiter,
    to_char(l.created_date, 'YYYY-MM-DD HH24:MI:SS')      AS order_time,
    l.status_name
FROM esb_data.report_pos_sales l
LEFT JOIN esb_data.report_pos_sales_head h
    ON h.company_id = l.company_id AND h.sales_num = l.sales_num;
