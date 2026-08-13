-- Phase 3: Product Master Data Integration (Group A)

-- 1. Create md_categories
CREATE TABLE IF NOT EXISTS public.md_categories (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    code VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    type_name VARCHAR(100),
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- 2. Create md_sub_categories
CREATE TABLE IF NOT EXISTS public.md_sub_categories (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    category_esb_id VARCHAR(100), -- We use ESB ID for easy reference during import
    esb_id VARCHAR(100) NOT NULL,
    code VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- 3. Create md_units (Satuan)
CREATE TABLE IF NOT EXISTS public.md_units (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    code VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- 4. Create md_boms (Bill of Material Header)
CREATE TABLE IF NOT EXISTS public.md_boms (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    product_esb_id VARCHAR(100), -- References product's ESB ID
    code VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    output_qty DECIMAL(15,2) DEFAULT 1,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- 5. Create md_bom_items (Bill of Material Details)
CREATE TABLE IF NOT EXISTS public.md_bom_items (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    bom_esb_id VARCHAR(100) NOT NULL,
    item_esb_id VARCHAR(100) NOT NULL,
    quantity DECIMAL(15,2) NOT NULL,
    uom_name VARCHAR(100),
    is_scrap BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, bom_esb_id, item_esb_id)
);

-- 6. Create md_branch_products (Mapping Branch to Product Stock)
CREATE TABLE IF NOT EXISTS public.md_branch_products (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    branch_esb_id VARCHAR(100) NOT NULL,
    product_esb_id VARCHAR(100) NOT NULL,
    stock DECIMAL(15,2) DEFAULT 0,
    available_stock DECIMAL(15,2) DEFAULT 0,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- 7. Create md_pricelists
CREATE TABLE IF NOT EXISTS public.md_pricelists (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    product_esb_id VARCHAR(100) NOT NULL,
    branch_esb_id VARCHAR(100), -- Optional: if specific to branch
    price DECIMAL(15,2) DEFAULT 0,
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- Add RLS (Row Level Security)
ALTER TABLE public.md_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_sub_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_boms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_bom_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_branch_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_pricelists ENABLE ROW LEVEL SECURITY;

-- Create Policies (Read Access for Authenticated Users)
CREATE POLICY "Allow read access for authenticated users" ON public.md_categories FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.md_sub_categories FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.md_units FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.md_boms FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.md_bom_items FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.md_branch_products FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.md_pricelists FOR SELECT TO authenticated USING (true);
