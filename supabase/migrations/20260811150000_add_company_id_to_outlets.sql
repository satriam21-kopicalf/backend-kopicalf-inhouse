ALTER TABLE public.md_outlets ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES public.company_configs(id) ON DELETE SET NULL;
