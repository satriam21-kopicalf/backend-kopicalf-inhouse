DROP TABLE IF EXISTS public.name_normalizations;

CREATE TABLE IF NOT EXISTS public.company_normalizations (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES public.company_configs(id) ON DELETE CASCADE,
    original_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (company_id)
);

CREATE TABLE IF NOT EXISTS public.branch_normalizations (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES public.md_outlets(id) ON DELETE CASCADE,
    original_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (branch_id)
);
