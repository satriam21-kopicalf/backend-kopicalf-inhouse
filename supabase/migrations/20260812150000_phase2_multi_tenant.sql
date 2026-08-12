-- Phase 2 Multi-Tenant Database Schema Updates

-- 1. Create name_normalizations table
CREATE TABLE IF NOT EXISTS public.name_normalizations (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL, -- 'COMPANY' or 'BRANCH'
    reference_id INTEGER NOT NULL, -- ID of the company_configs or md_outlets
    original_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Add company_id to Master Data Tables and Staging
-- Drop existing unique constraints that only rely on esb_id
ALTER TABLE public.md_products DROP CONSTRAINT IF EXISTS md_products_esb_id_key;
ALTER TABLE public.md_employees DROP CONSTRAINT IF EXISTS md_employees_esb_id_key;
ALTER TABLE public.md_suppliers DROP CONSTRAINT IF EXISTS md_suppliers_esb_id_key;
ALTER TABLE public.esb_raw_staging DROP CONSTRAINT IF EXISTS esb_raw_staging_entity_type_esb_id_key;

-- Add company_id columns (allow null initially if data exists, but since we truncated it's fine. We make it nullable just in case, but ideally NOT NULL)
ALTER TABLE public.md_products ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE;
ALTER TABLE public.md_employees ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE;
ALTER TABLE public.md_suppliers ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE;
ALTER TABLE public.esb_raw_staging ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE;

-- Recreate unique constraints incorporating company_id
ALTER TABLE public.md_products ADD CONSTRAINT md_products_company_id_esb_id_key UNIQUE (company_id, esb_id);
ALTER TABLE public.md_employees ADD CONSTRAINT md_employees_company_id_esb_id_key UNIQUE (company_id, esb_id);
ALTER TABLE public.md_suppliers ADD CONSTRAINT md_suppliers_company_id_esb_id_key UNIQUE (company_id, esb_id);
ALTER TABLE public.esb_raw_staging ADD CONSTRAINT esb_raw_staging_company_id_entity_type_esb_id_key UNIQUE (company_id, entity_type, esb_id);
