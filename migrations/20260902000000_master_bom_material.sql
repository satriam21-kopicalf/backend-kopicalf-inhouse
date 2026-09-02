-- Migration: 20260902000000_master_bom_material.sql
-- Purpose: Store BOM material line items for COGS standard cost calculation
-- API source: GET /product/bom/{bomID} -> bomDetails[]

CREATE TABLE IF NOT EXISTS esb_data.master_bom_material (
    id                      BIGSERIAL PRIMARY KEY,
    company_id              INTEGER NOT NULL,
    bom_esb_id              TEXT NOT NULL,
    line_num                INTEGER NOT NULL DEFAULT 1,
    material_esb_id         TEXT,                          -- productDetailID from ESB
    material_product_esb_id  TEXT,                          -- productID from ESB (base product)
    qty                     NUMERIC(18,4) DEFAULT 0,       -- product qty for this line
    uom_qty                 NUMERIC(18,4) DEFAULT 0,      -- UOM qty
    conversion_qty           NUMERIC(18,4) DEFAULT 0,      -- conversion factor
    uom_name                VARCHAR(100),
    hpp                     NUMERIC(18,4) DEFAULT 0,       -- lastHpp from ESB
    price                   NUMERIC(18,4) DEFAULT 0,       -- price from ESB
    yield_percent           INTEGER DEFAULT 0,             -- waste percentage
    weight_factor           INTEGER DEFAULT 0,
    print_group             VARCHAR(100),
    stock_qty               NUMERIC(18,4) DEFAULT 0,
    raw_data                JSONB,
    synced_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, bom_esb_id, line_num)
);

CREATE INDEX IF NOT EXISTS idx_bom_material_company_bom
    ON esb_data.master_bom_material (company_id, bom_esb_id);
CREATE INDEX IF NOT EXISTS idx_bom_material_company_product
    ON esb_data.master_bom_material (company_id, material_product_esb_id);
CREATE INDEX IF NOT EXISTS idx_bom_material_material_detail
    ON esb_data.master_bom_material (material_esb_id);
