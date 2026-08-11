-- Phase 2: ESB Data Hub & Integration

-- 1. Tabel Raw Staging (Data Lake ESB)
-- Menampung 100% data mentah dari ESB persis seperti aslinya
CREATE TABLE IF NOT EXISTS public.esb_raw_staging (
    esb_id VARCHAR(100) PRIMARY KEY, -- Mencegah duplikat secara absolut (Primary Key)
    entity_type VARCHAR(50) NOT NULL, -- e.g., 'OUTLET', 'EMPLOYEE', 'PRODUCT'
    raw_json JSONB NOT NULL, -- Data utuh (tanpa kurang/ubah)
    is_processed BOOLEAN DEFAULT FALSE,
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Tabel Sinkronisasi & Audit
-- Menyimpan riwayat kapan sinkronisasi berjalan dan apa hasilnya
CREATE TABLE IF NOT EXISTS public.sync_history (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL, -- e.g., 'OUTLETS', 'EMPLOYEES'
    status VARCHAR(20) NOT NULL, -- 'SUCCESS', 'PARTIAL', 'FAILED'
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Tabel Dead Letter Queue (DLQ)
-- Tempat pembuangan akhir untuk JSON yang cacat
CREATE TABLE IF NOT EXISTS public.dlq_logs (
    id SERIAL PRIMARY KEY,
    sync_history_id INTEGER REFERENCES public.sync_history(id) ON DELETE CASCADE,
    endpoint_source VARCHAR(255), -- e.g., 'https://esb.kopicalf.com/api/products'
    raw_payload JSONB NOT NULL, -- Menyimpan bentuk ASLI json yang gagal
    error_reason TEXT NOT NULL, -- Pesan error dari Pydantic (e.g., "Harga tidak boleh null")
    is_resolved BOOLEAN DEFAULT FALSE, -- Ditandai TRUE jika tim IT sudah membereskan datanya
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add RLS to these tables
ALTER TABLE public.esb_raw_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dlq_logs ENABLE ROW LEVEL SECURITY;

-- Allow only authenticated users to read (assuming service role bypasses RLS for inserting)
CREATE POLICY "Allow read access for authenticated users" ON public.esb_raw_staging FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.sync_history FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow read access for authenticated users" ON public.dlq_logs FOR SELECT TO authenticated USING (true);
