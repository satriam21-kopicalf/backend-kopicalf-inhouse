-- =====================================================================
-- ENGINE V2: Multi-company auth (login/company switch) + schema alignment
-- Based on verified ESB API documentation (probed 2026-08-15)
--
-- Key facts:
--  * POST /auth/login                     -> base JWT (group scope)
--  * POST /auth/login/company {code}      -> per-company JWT (single-use base JWT)
--  * companyCode mapping: CALF..CALF7 (8 companies)
--  * Response shapes: array (branch, cost-center) vs envelope {page,limit,count,data}
-- =====================================================================

-- ============ 1. company_configs: company code + credentials ============
ALTER TABLE public.company_configs
    ADD COLUMN IF NOT EXISTS esb_company_code VARCHAR(20),
    ADD COLUMN IF NOT EXISTS esb_username    VARCHAR(100),
    ADD COLUMN IF NOT EXISTS esb_password    VARCHAR(200);

-- Map codes per verified ESB data
UPDATE public.company_configs SET esb_company_code = 'CALF'  WHERE id = 1;
UPDATE public.company_configs SET esb_company_code = 'CALF1' WHERE id = 2;  -- Calf Roastery (CK account only)
UPDATE public.company_configs SET esb_company_code = 'CALF2' WHERE id = 3;  -- Calf Central Kitchen
UPDATE public.company_configs SET esb_company_code = 'CALF3' WHERE id = 4;  -- PT DAYUPRA SOLUSI PARTNER
UPDATE public.company_configs SET esb_company_code = 'CALF4' WHERE id = 5;  -- Coffee Solution Indo
UPDATE public.company_configs SET esb_company_code = 'CALF5' WHERE id = 6;  -- Calf COTR
UPDATE public.company_configs SET esb_company_code = 'CALF6' WHERE id = 7;  -- Calf Central Kitchen Food
UPDATE public.company_configs SET esb_company_code = 'CALF7' WHERE id = 8;  -- Wasgee Tea

-- ============ 2. NEW md_customers (/customer, 1203 rows in CALF) ============
CREATE TABLE IF NOT EXISTS public.md_customers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    code VARCHAR(100),
    category_esb_id VARCHAR(50),
    category_name VARCHAR(150),
    payment_due_days INTEGER DEFAULT 0,
    address TEXT,
    pic_name VARCHAR(255),
    pic_phone VARCHAR(100),
    flag_active BOOLEAN DEFAULT TRUE,
    lock_vat BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);
CREATE INDEX IF NOT EXISTS idx_md_customers_company_esb ON public.md_customers(company_id, esb_id);

-- ============ 3. NEW md_purposes (/purpose, 11 rows) ============
CREATE TABLE IF NOT EXISTS public.md_purposes (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    account VARCHAR(255),
    coa_no VARCHAR(100),
    applied_to JSONB,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);
CREATE INDEX IF NOT EXISTS idx_md_purposes_company_esb ON public.md_purposes(company_id, esb_id);

-- ============ 4. NEW md_cost_centers (/cost-center, array response) ============
CREATE TABLE IF NOT EXISTS public.md_cost_centers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    code VARCHAR(100),
    name VARCHAR(255),
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);
CREATE INDEX IF NOT EXISTS idx_md_cost_centers_company_esb ON public.md_cost_centers(company_id, esb_id);

-- ============ 5. NEW md_product_details (from /product/{id}.productDetails) ============
CREATE TABLE IF NOT EXISTS public.md_product_details (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,              -- productDetailID
    product_esb_id VARCHAR(100),
    uom_id INTEGER,
    metric_id INTEGER,
    uom_name VARCHAR(100),
    qty NUMERIC(15,4),
    base_price NUMERIC(15,2),
    sku VARCHAR(255),
    is_base BOOLEAN DEFAULT FALSE,
    is_stock BOOLEAN DEFAULT FALSE,
    is_purchase BOOLEAN DEFAULT FALSE,
    is_transfer BOOLEAN DEFAULT FALSE,
    is_sales BOOLEAN DEFAULT FALSE,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);
CREATE INDEX IF NOT EXISTS idx_md_product_details_company_esb ON public.md_product_details(company_id, esb_id);
CREATE INDEX IF NOT EXISTS idx_md_product_details_product ON public.md_product_details(company_id, product_esb_id);

-- ============ 6. NEW report_raw staging (for /report & /pos/transaction later) ============
CREATE TABLE IF NOT EXISTS public.report_raw_staging (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    report_type VARCHAR(100) NOT NULL,
    period_start DATE,
    period_end DATE,
    branch_esb_id VARCHAR(100),
    raw_data JSONB NOT NULL,
    source_params JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, report_type, period_start, period_end, branch_esb_id)
);
CREATE INDEX IF NOT EXISTS idx_report_raw_staging_lookup ON public.report_raw_staging(company_id, report_type, period_start);

-- ============ 7. Align existing tables with verified payloads ============
-- md_pricelists: verified fields (ID, pricelistNum, productDetailID, uomID, unit, currencyID, currencyName, expireDate, applicableBranch)
ALTER TABLE public.md_pricelists
    ADD COLUMN IF NOT EXISTS pricelist_num VARCHAR(100),
    ADD COLUMN IF NOT EXISTS product_detail_esb_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS uom_id INTEGER,
    ADD COLUMN IF NOT EXISTS unit_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS currency_id INTEGER,
    ADD COLUMN IF NOT EXISTS applicable_branch JSONB;

-- md_categories: verified (categoryID, categoryName, categoryTypeID, categoryTypeName, notes, flagActive)
ALTER TABLE public.md_categories
    ADD COLUMN IF NOT EXISTS category_type_id INTEGER,
    ADD COLUMN IF NOT EXISTS notes TEXT;

-- md_sub_categories: verified (subCategoryID, subCategoryName, notes, deadStockThreshold, flagActive)
ALTER TABLE public.md_sub_categories
    ADD COLUMN IF NOT EXISTS dead_stock_threshold INTEGER,
    ADD COLUMN IF NOT EXISTS notes TEXT;

-- md_boms: verified (bomID, bomName, bomCode, bomTypeID, bomTypeName, productName, uomName, notes)
ALTER TABLE public.md_boms
    ADD COLUMN IF NOT EXISTS bom_type_id INTEGER,
    ADD COLUMN IF NOT EXISTS bom_type_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS product_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS uom_name VARCHAR(100);

-- md_suppliers: verified (supplierID, supplierName, address, supplierCode, dueDate, contactPerson, cellPhone, category, supplierCategoryID, linkSupplierCodeEsbGoods, lockVAT, vatSubject)
ALTER TABLE public.md_suppliers
    ADD COLUMN IF NOT EXISTS address TEXT,
    ADD COLUMN IF NOT EXISTS contact_person VARCHAR(255),
    ADD COLUMN IF NOT EXISTS cell_phone VARCHAR(100),
    ADD COLUMN IF NOT EXISTS due_date INTEGER,
    ADD COLUMN IF NOT EXISTS category_esb_id INTEGER,
    ADD COLUMN IF NOT EXISTS lock_vat BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS vat_subject BOOLEAN DEFAULT FALSE;

-- ============ 8. RLS for new tables ============
ALTER TABLE public.md_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_purposes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_cost_centers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_product_details ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.report_raw_staging ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'md_customers' AND policyname = 'md_customers_read') THEN
        CREATE POLICY md_customers_read ON public.md_customers FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'md_purposes' AND policyname = 'md_purposes_read') THEN
        CREATE POLICY md_purposes_read ON public.md_purposes FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'md_cost_centers' AND policyname = 'md_cost_centers_read') THEN
        CREATE POLICY md_cost_centers_read ON public.md_cost_centers FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'md_product_details' AND policyname = 'md_product_details_read') THEN
        CREATE POLICY md_product_details_read ON public.md_product_details FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'report_raw_staging' AND policyname = 'report_raw_staging_read') THEN
        CREATE POLICY report_raw_staging_read ON public.report_raw_staging FOR SELECT TO authenticated USING (true);
    END IF;
END
$$;

-- ============ 9. Engine kill-switch column ============
ALTER TABLE public.engine_settings
    ADD COLUMN IF NOT EXISTS sync_enabled BOOLEAN DEFAULT TRUE;
UPDATE public.engine_settings SET sync_enabled = FALSE WHERE id = 1;
