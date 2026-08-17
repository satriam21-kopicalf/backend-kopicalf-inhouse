-- Extra master tables from MASTER.md requirements (verified endpoints 2026-08-15)

-- /project (array, 38 rows)
CREATE TABLE IF NOT EXISTS public.md_projects (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    code VARCHAR(100),
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- /customer/category (array, 1 row)
CREATE TABLE IF NOT EXISTS public.md_customer_categories (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- /supplier/category (array, 1 row)
CREATE TABLE IF NOT EXISTS public.md_supplier_categories (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- /user (envelope, 364 rows)
CREATE TABLE IF NOT EXISTS public.md_users (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    username VARCHAR(100),
    full_name VARCHAR(255),
    role_id INTEGER,
    role_desc VARCHAR(100),
    flag_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

-- /accounting/coa (array, 356 rows)
CREATE TABLE IF NOT EXISTS public.md_coas (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    esb_id VARCHAR(100) NOT NULL,
    coa_no VARCHAR(100),
    coa_level INTEGER,
    description VARCHAR(255),
    currency VARCHAR(50),
    branch_esb_id VARCHAR(50),
    flag_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_md_projects_company_esb ON public.md_projects(company_id, esb_id);
CREATE INDEX IF NOT EXISTS idx_md_customer_categories_company_esb ON public.md_customer_categories(company_id, esb_id);
CREATE INDEX IF NOT EXISTS idx_md_supplier_categories_company_esb ON public.md_supplier_categories(company_id, esb_id);
CREATE INDEX IF NOT EXISTS idx_md_users_company_esb ON public.md_users(company_id, esb_id);
CREATE INDEX IF NOT EXISTS idx_md_coas_company_esb ON public.md_coas(company_id, esb_id);

ALTER TABLE public.md_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_customer_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_supplier_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.md_coas ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='md_projects' AND policyname='md_projects_read') THEN
        CREATE POLICY md_projects_read ON public.md_projects FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='md_customer_categories' AND policyname='md_customer_categories_read') THEN
        CREATE POLICY md_customer_categories_read ON public.md_customer_categories FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='md_supplier_categories' AND policyname='md_supplier_categories_read') THEN
        CREATE POLICY md_supplier_categories_read ON public.md_supplier_categories FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='md_users' AND policyname='md_users_read') THEN
        CREATE POLICY md_users_read ON public.md_users FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='md_coas' AND policyname='md_coas_read') THEN
        CREATE POLICY md_coas_read ON public.md_coas FOR SELECT TO authenticated USING (true);
    END IF;
END
$$;
