-- 1. Create company_configs table
CREATE TABLE IF NOT EXISTS public.company_configs (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL UNIQUE,
    esb_token TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Add is_active column to md_outlets
ALTER TABLE public.md_outlets ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 3. Enable RLS on company_configs (if not already enabled)
ALTER TABLE public.company_configs ENABLE ROW LEVEL SECURITY;

-- 4. Create RLS policies for company_configs
CREATE POLICY "Allow read access for authenticated users on company_configs" 
ON public.company_configs FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow insert access for authenticated users on company_configs" 
ON public.company_configs FOR INSERT TO authenticated WITH CHECK (true);

CREATE POLICY "Allow update access for authenticated users on company_configs" 
ON public.company_configs FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Allow delete access for authenticated users on company_configs" 
ON public.company_configs FOR DELETE TO authenticated USING (true);

-- 5. Create/update RLS policies for md_outlets to allow updates from authenticated users
ALTER TABLE public.md_outlets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access for authenticated users on md_outlets" 
ON public.md_outlets FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow update access for authenticated users on md_outlets" 
ON public.md_outlets FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

-- 6. Insert default company config
INSERT INTO public.company_configs (company_name, esb_token)
VALUES ('System Analyst ESB', 'SAErV8dJd3Ospv8NRnSjfQnjwC1LSbdkeVbSgAScae4z26JpYf6eySCdJpfK')
ON CONFLICT (company_name) DO UPDATE 
SET esb_token = EXCLUDED.esb_token;
