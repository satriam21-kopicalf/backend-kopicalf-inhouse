-- Add company_id to sync_history to support multi-tenant tracking
ALTER TABLE public.sync_history ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES public.company_configs(id) ON DELETE CASCADE;
