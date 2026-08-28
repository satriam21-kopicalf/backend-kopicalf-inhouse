-- Drop legacy/unused tables (all verified empty and unreferenced by engine or frontend)
-- Legacy 3D-RBAC auth model (login uses Supabase auth, not these tables)
DROP TABLE IF EXISTS public.transactional_dummy CASCADE;
DROP TABLE IF EXISTS public.user_profiles CASCADE;
DROP TABLE IF EXISTS public.divisions CASCADE;
DROP TABLE IF EXISTS public.levels CASCADE;
DROP TABLE IF EXISTS public.scopes CASCADE;
-- Legacy master detail tables superseded by esb_data.* equivalents
DROP TABLE IF EXISTS public.md_bom_items CASCADE;
DROP TABLE IF EXISTS public.md_employees CASCADE;
DROP TABLE IF EXISTS public.md_branch_products CASCADE;
