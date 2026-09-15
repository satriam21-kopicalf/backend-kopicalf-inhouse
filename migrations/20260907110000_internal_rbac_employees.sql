-- Internal dashboard: RBAC + employees, in a dedicated `internal` schema.
-- Consumes esb_data where needed (branch_id references esb_data.master_branch).

CREATE SCHEMA IF NOT EXISTS internal;

-- ============ RBAC ============
CREATE TABLE IF NOT EXISTS internal.roles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(40) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS internal.permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(60) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    module VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS internal.role_permissions (
    role_id INTEGER NOT NULL REFERENCES internal.roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES internal.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- ============ Employees ============
CREATE TABLE IF NOT EXISTS internal.employees (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL DEFAULT 1,
    employee_code VARCHAR(30) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150),
    phone VARCHAR(40),
    division VARCHAR(80),
    department VARCHAR(80),
    position VARCHAR(100),
    employee_type VARCHAR(30) NOT NULL DEFAULT 'STAFF'
        CHECK (employee_type IN ('MANAGEMENT','SUPERVISOR','STAFF','BARISTA','KITCHEN','OTHER')),
    rate_class VARCHAR(20)
        CHECK (rate_class IN ('A','B','C','SPECIALTY') OR rate_class IS NULL),
    base_salary NUMERIC(14,2) DEFAULT 0,
    salary_type VARCHAR(20) NOT NULL DEFAULT 'MONTHLY'
        CHECK (salary_type IN ('MONTHLY','DAILY','HOURLY')),
    join_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE','INACTIVE','RESIGNED')),
    branch_id INTEGER REFERENCES esb_data.master_branch(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_employees_company_status ON internal.employees (company_id, status);

-- Work time (shift) configuration per employee
CREATE TABLE IF NOT EXISTS internal.employee_shifts (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES internal.employees(id) ON DELETE CASCADE,
    shift_name VARCHAR(60) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    work_days VARCHAR(20) NOT NULL DEFAULT '1,2,3,4,5',
    break_minutes INTEGER DEFAULT 60,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Deductions & allowances (potongan/iuran)
CREATE TABLE IF NOT EXISTS internal.employee_deductions (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES internal.employees(id) ON DELETE CASCADE,
    deduction_type VARCHAR(40) NOT NULL
        CHECK (deduction_type IN ('LATE','ABSENT','BPJS','TAX','LOAN','ADVANCE','OTHER','ALLOWANCE')),
    amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    period_month VARCHAR(7) NOT NULL,
    note TEXT,
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_deductions_emp_period ON internal.employee_deductions (employee_id, period_month);

-- ============ Users & sessions ============
CREATE TABLE IF NOT EXISTS internal.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(150) UNIQUE NOT NULL,
    username VARCHAR(60) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    employee_id INTEGER REFERENCES internal.employees(id),
    role_id INTEGER NOT NULL REFERENCES internal.roles(id),
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS internal.sessions (
    token VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES internal.users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON internal.sessions (user_id);

-- ============ Seeds ============
INSERT INTO internal.roles (code, name, description, is_system) VALUES
    ('SUPER_ADMIN', 'Super Admin', 'Full access to everything', true),
    ('MANAGEMENT', 'Management', 'Owner / management: full visibility and approvals', true),
    ('SCC', 'Supply Chain & Cost Control', 'SCC team: stock system, opname, waste, reporting', true),
    ('OUTLET_PIC', 'Outlet PIC', 'PIC outlet: entry stock opname & waste, view own data', true),
    ('BARISTA', 'Barista', 'Barista: entry stock opname & waste', true),
    ('VIEWER', 'Viewer', 'Read-only access to dashboards', true)
ON CONFLICT (code) DO NOTHING;

INSERT INTO internal.permissions (code, name, module) VALUES
    ('dashboard.view',        'View Dashboard',              'dashboard'),
    ('data.master.view',      'View Master Data',            'data'),
    ('data.reporting.view',   'View Data Reporting',         'data'),
    ('scc.overview.view',     'View SCC Overview',           'scc'),
    ('scc.stock-system.view', 'View Stock System',           'scc'),
    ('scc.stock-system.edit', 'Edit Stock System',           'scc'),
    ('scc.stock-opname.view', 'View Stock Opname',           'scc'),
    ('scc.stock-opname.approve','Approve Stock Opname',      'scc'),
    ('scc.waste.view',        'View Waste',                  'scc'),
    ('scc.waste.approve',     'Approve Waste',               'scc'),
    ('scc.reporting.view',    'View SCC Reporting',          'scc'),
    ('form.stock-opname',     'Entry Stock Opname',          'forms'),
    ('form.waste',            'Entry Waste',                 'forms'),
    ('operational.view',      'View Operational',            'operational'),
    ('aggregator.view',       'View Aggregator',             'aggregator'),
    ('admin.users',           'Manage Users',                'admin'),
    ('admin.employees',       'Manage Employees',            'admin'),
    ('admin.roles',           'Manage Roles & Permissions',  'admin')
ON CONFLICT (code) DO NOTHING;

-- SUPER_ADMIN & MANAGEMENT: everything
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM internal.roles r, internal.permissions p
WHERE r.code IN ('SUPER_ADMIN','MANAGEMENT')
ON CONFLICT DO NOTHING;

-- SCC: dashboards, all SCC, master data read
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM internal.roles r, internal.permissions p
WHERE r.code = 'SCC' AND p.code IN (
    'dashboard.view','data.master.view','scc.overview.view','scc.stock-system.view',
    'scc.stock-system.edit','scc.stock-opname.view','scc.stock-opname.approve',
    'scc.waste.view','scc.waste.approve','scc.reporting.view',
    'form.stock-opname','form.waste'
)
ON CONFLICT DO NOTHING;

-- OUTLET_PIC: dashboard, own lists, entry forms
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM internal.roles r, internal.permissions p
WHERE r.code = 'OUTLET_PIC' AND p.code IN (
    'dashboard.view','scc.stock-opname.view','scc.waste.view','form.stock-opname','form.waste'
)
ON CONFLICT DO NOTHING;

-- BARISTA: dashboard, entry forms only
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM internal.roles r, internal.permissions p
WHERE r.code = 'BARISTA' AND p.code IN ('dashboard.view','form.stock-opname','form.waste')
ON CONFLICT DO NOTHING;

-- VIEWER: read-only everywhere
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM internal.roles r, internal.permissions p
WHERE r.code = 'VIEWER' AND p.code LIKE '%.view'
ON CONFLICT DO NOTHING;
