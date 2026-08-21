-- Migration: Add raw_data to all master tables
-- This ensures no detailed fields from the ESB API are lost during normalization.

DO $$ 
DECLARE
    t_name text;
    tables_list text[] := ARRAY[
        'md_outlets',
        'md_products',
        'md_product_details',
        'md_categories',
        'md_sub_categories',
        'md_units',
        'md_pricelists',
        'md_suppliers',
        'md_customers',
        'md_boms',
        'md_bom_items',
        'md_branch_products',
        'md_document_templates',
        'md_purposes',
        'md_coas',
        'md_projects',
        'md_users',
        'md_customer_categories',
        'md_supplier_categories',
        'md_customer_pricelists',
        'md_cost_centers'
    ];
BEGIN
    FOREACH t_name IN ARRAY tables_list
    LOOP
        -- Check if table exists
        IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = t_name) THEN
            -- Check if column raw_data already exists
            IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_schema = 'public' AND table_name = t_name AND column_name = 'raw_data') THEN
                EXECUTE format('ALTER TABLE public.%I ADD COLUMN raw_data JSONB DEFAULT ''{}''::jsonb', t_name);
            END IF;
        END IF;
    END LOOP;
END $$;
