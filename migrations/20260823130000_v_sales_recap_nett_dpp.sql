-- Add Nett Sales & DPP to the ERP-identical Sales Recapitulation Detail view.
-- Nett Sales = total - tax - vat amount (vatValue in raw) - other tax value.
-- DPP (dasar pengenaan pajak) applies to inclusive-price lines:
--   inclusive_price * qty / (1 + vat_rate/100); 0 for regular lines.
CREATE OR REPLACE VIEW esb_data.v_sales_recap_detail AS
SELECT
    l.company_id,
    l.sales_num,
    l.bill_num,
    l.raw_data::jsonb ->> 'salesType'                      AS sales_type,
    l.batch_id                                            AS batch_order,
    h.table_name,
    l.sales_date,
    h.sales_date_in,
    h.sales_date_out,
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
    -- Nett Sales: gross total minus all pass-through taxes
    ROUND(
        l.total
        - l.tax
        - COALESCE((l.raw_data::jsonb ->> 'vatValue')::numeric, 0)
        - COALESCE((l.raw_data::jsonb ->> 'otherTaxValue')::numeric, 0), 2) AS nett_sales,
    -- DPP: taxable base for inclusive-price lines (inclusivePrice stored per unit)
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
    l.created_date                                        AS order_time,
    l.status_name
FROM esb_data.report_pos_sales l
LEFT JOIN esb_data.report_pos_sales_head h
    ON h.company_id = l.company_id AND h.sales_num = l.sales_num;
