-- 1. Dimensi Divisi (Menyimpan 17 Pilar CALF)
CREATE TABLE public.divisions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) -- e.g., 'Executive', 'Operations', 'Supply'
);

-- Insert 17 Pillars
INSERT INTO public.divisions (name, category) VALUES
('Superadmin', 'Executive'),
('Founder', 'Executive'),
('Co-Founder', 'Executive'),
('Operational', 'Operations'),
('Maintenance', 'Operations'),
('Administration', 'Operations'),
('Supply Chain', 'Supply'),
('Central Warehouse', 'Supply'),
('Central Kitchen', 'Supply'),
('Central Roastery', 'Supply'),
('Research and Dev', 'Supply'),
('Human Resources', 'Back-Office'),
('Technology', 'Back-Office'),
('Finance', 'Back-Office'),
('SWOT', 'Back-Office'),
('Supplier', '3rd Party'),
('External', '3rd Party');

-- 2. Dimensi Level (Hierarki Karyawan)
CREATE TABLE public.levels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    rank INTEGER NOT NULL -- Krusial: Angka rank (misal: Top=100, Head=80, Staff=20) 
);

INSERT INTO public.levels (name, rank) VALUES
('Top', 100),
('Head', 80),
('Manager', 60),
('Supervisor', 40),
('PPIC', 30),
('Staff', 20),
('Barista Grade A', 15),
('Barista Grade B', 14),
('Barista Grade C', 13),
('Barista Grade D', 12),
('Vendor', 10);

-- 3. Dimensi Scope (Batasan Lokasi Data)
CREATE TABLE public.scopes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL -- e.g., 'HQ', 'Regional', 'Specific Outlet', 'External'
);

-- 4. User Profiles (Auth Link)
CREATE TABLE public.user_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    employee_id VARCHAR(50) UNIQUE,
    
    -- Injeksi 3 Dimensi:
    division_id INTEGER REFERENCES public.divisions(id),
    level_id INTEGER REFERENCES public.levels(id),
    scope_ids INTEGER[] DEFAULT '{}', -- Tipe data Array agar manajer bisa memegang multi-cabang
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Master Data Placeholders (Untuk Phase 2)
CREATE TABLE public.md_outlets (
    id SERIAL PRIMARY KEY,
    esb_id VARCHAR(100) UNIQUE,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(100),
    status VARCHAR(50) DEFAULT 'ACTIVE'
);

CREATE TABLE public.md_products (
    id SERIAL PRIMARY KEY,
    esb_id VARCHAR(100) UNIQUE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100)
);

CREATE TABLE public.md_employees (
    id SERIAL PRIMARY KEY,
    esb_id VARCHAR(100) UNIQUE,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100)
);

CREATE TABLE public.md_suppliers (
    id SERIAL PRIMARY KEY,
    esb_id VARCHAR(100) UNIQUE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50)
);

-- 6. Dummy Transactional Table for RLS Testing
CREATE TABLE public.transactional_dummy (
    id SERIAL PRIMARY KEY,
    division_id INTEGER REFERENCES public.divisions(id),
    scope_id INTEGER,
    created_by UUID REFERENCES auth.users(id),
    data TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. RLS Policies
ALTER TABLE public.transactional_dummy ENABLE ROW LEVEL SECURITY;

-- Contoh Kebijakan (Policy) Pembatasan Data
CREATE POLICY "Users can only view data within their allowed scope and division"
ON public.transactional_dummy
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.user_profiles 
    WHERE user_id = auth.uid() 
    AND division_id = public.transactional_dummy.division_id
    AND public.transactional_dummy.scope_id = ANY(scope_ids)
  )
);
