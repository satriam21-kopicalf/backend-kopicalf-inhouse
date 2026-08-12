-- Phase 1: Engine Settings and Core Master Data Expansion

-- 1. Create engine_settings table
CREATE TABLE IF NOT EXISTS public.engine_settings (
    id SERIAL PRIMARY KEY,
    sync_batch_size INTEGER DEFAULT 1000,
    work_hours_interval_minutes INTEGER DEFAULT 30,
    morning_window_interval_minutes INTEGER DEFAULT 30,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default row if not exists
INSERT INTO public.engine_settings (id, sync_batch_size, work_hours_interval_minutes, morning_window_interval_minutes)
SELECT 1, 1000, 30, 30
WHERE NOT EXISTS (SELECT 1 FROM public.engine_settings WHERE id = 1);

-- 2. Expand md_products
ALTER TABLE public.md_products 
    ADD COLUMN IF NOT EXISTS barcode TEXT,
    ADD COLUMN IF NOT EXISTS uom_name TEXT,
    ADD COLUMN IF NOT EXISTS purchase_price DECIMAL(15,2),
    ADD COLUMN IF NOT EXISTS sell_price DECIMAL(15,2),
    ADD COLUMN IF NOT EXISTS stock DECIMAL(15,2),
    ADD COLUMN IF NOT EXISTS has_variant BOOLEAN,
    ADD COLUMN IF NOT EXISTS is_raw_material BOOLEAN,
    ADD COLUMN IF NOT EXISTS is_production BOOLEAN,
    ADD COLUMN IF NOT EXISTS image_url TEXT;

-- 3. Expand md_outlets (branches)
ALTER TABLE public.md_outlets 
    ADD COLUMN IF NOT EXISTS location_name TEXT,
    ADD COLUMN IF NOT EXISTS stock DECIMAL(15,2),
    ADD COLUMN IF NOT EXISTS available_stock DECIMAL(15,2);

-- 4. Expand md_employees
ALTER TABLE public.md_employees 
    ADD COLUMN IF NOT EXISTS employee_group TEXT,
    ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS branch_id VARCHAR(100);

-- 5. Expand md_suppliers
ALTER TABLE public.md_suppliers 
    ADD COLUMN IF NOT EXISTS supplier_category TEXT,
    ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'ACTIVE';

-- Add RLS to engine_settings
ALTER TABLE public.engine_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow read access for authenticated users" ON public.engine_settings FOR SELECT TO authenticated USING (true);
-- Service role handles updates, or allow authenticated users to update:
CREATE POLICY "Allow update for authenticated users" ON public.engine_settings FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
