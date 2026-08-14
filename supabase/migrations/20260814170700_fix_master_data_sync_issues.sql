-- Fix P0 issues: Missing tables and product data sync issues

-- 1. Create md_document_templates table (currently missing)
CREATE TABLE IF NOT EXISTS public.md_document_templates (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    document_type VARCHAR(100),
    template_code VARCHAR(100),
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- 2. Create md_customer_pricelists table (currently missing)
CREATE TABLE IF NOT EXISTS public.md_customer_pricelists (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    customer_name VARCHAR(255),
    product_name VARCHAR(255),
    product_code VARCHAR(100),
    uom_name VARCHAR(100),
    currency_name VARCHAR(100),
    price DECIMAL(15,2) DEFAULT 0,
    price_date TIMESTAMP WITH TIME ZONE,
    expire_date TIMESTAMP WITH TIME ZONE,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- 3. Add RLS (Row Level Security) for new tables
ALTER TABLE public.md_document_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_customer_pricelists ENABLE ROW LEVEL SECURITY;

-- 4. Create Policies for new tables
CREATE POLICY "Allow read access for authenticated users" ON public.md_document_templates FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.md_customer_pricelists FOR SELECT TO authenticated USING (true);

-- 5. Update md_pricelists table to include missing fields for EXPORT format
ALTER TABLE public.md_pricelists 
ADD COLUMN IF NOT EXISTS price_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS product_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS product_code VARCHAR(100),
ADD COLUMN IF NOT EXISTS unit_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS currency VARCHAR(100),
ADD COLUMN IF NOT EXISTS expired_date TIMESTAMP WITH TIME ZONE;

-- 6. Update md_branch_products table to include missing fields for EXPORT format
ALTER TABLE public.md_branch_products 
ADD COLUMN IF NOT EXISTS product_code VARCHAR(100),
ADD COLUMN IF NOT EXISTS product_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS branch_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS location_id INTEGER,
ADD COLUMN IF NOT EXISTS location_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS min_stock DECIMAL(15,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS max_stock DECIMAL(15,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS reserved_stock DECIMAL(15,2) DEFAULT 0;

-- 7. Update md_pricelists table to fix any existing NULL values
UPDATE public.md_pricelists 
SET price_date = NOW() WHERE price_date IS NULL;

-- 8. Update md_branch_products table to fix any existing NULL values
UPDATE public.md_branch_products 
SET product_code = '', product_name = '', branch_name = '', location_name = '' 
WHERE product_code IS NULL;

-- 9. Update md_pricelists table to fix any existing NULL values
UPDATE public.md_pricelists 
SET supplier_name = '', product_name = '', product_code = '', unit_name = '', currency = 'IDR' 
WHERE supplier_name IS NULL;

-- 10. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_md_document_templates_company_esb ON public.md_document_templates(company_id, esb_id);
CREATE INDEX IF NOT EXISTS idx_md_customer_pricelists_company_esb ON public.md_customer_pricelists(company_id, esb_id);
CREATE INDEX IF NOT EXISTS idx_md_pricelists_product_esb_id ON public.md_pricelists(company_id, product_esb_id);
CREATE INDEX IF NOT EXISTS idx_md_branch_products_product_esb_id ON public.md_branch_products(company_id, product_esb_id);

-- 11. Add comments to new tables
COMMENT ON TABLE public.md_document_templates IS 'Document templates from ESB API';
COMMENT ON TABLE public.md_customer_pricelists IS 'Customer-specific pricelists from ESB API';
COMMENT ON COLUMN public.md_document_templates.document_type IS 'Type of document (INVOICE, RECEIPT, etc.)';
COMMENT ON COLUMN public.md_document_templates.template_code IS 'Template identifier code';
COMMENT ON COLUMN public.md_customer_pricelists.price_date IS 'Effective date for customer pricelist price';
COMMENT ON COLUMN public.md_customer_pricelists.expire_date IS 'Expiration date for customer pricelist price';
