-- ERP-identical Sales Recapitulation Detail: line items joined with bill head
-- to expose the same field set as the ERP sample export (46 columns where data
-- exists in the OMS source; brand/city/area/DPP etc. are ERP-side joins and
-- are not exposed by the OMS API).
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
    l.vat,
    l.total,
    l.original_price,
    h.discount_total                                      AS bill_discount,
    h.grand_total                                         AS total_after_bill_discount,
    l.created_by                                          AS waiter,
    l.created_date                                        AS order_time,
    l.status_name
FROM esb_data.report_pos_sales l
LEFT JOIN esb_data.report_pos_sales_head h
    ON h.company_id = l.company_id AND h.sales_num = l.sales_num;
