-- ============================================================
-- Master Tables Migration for CALF Ecosystem
-- Creates: master_division, master_department, master_employee
-- ============================================================

-- 1. Create master_division table
CREATE TABLE IF NOT EXISTS esb_data.master_division (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    manager_id INTEGER,
    manager_name VARCHAR(200),
    department_count INTEGER DEFAULT 0,
    total_headcount INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create master_department table
CREATE TABLE IF NOT EXISTS esb_data.master_department (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    division_id INTEGER REFERENCES esb_data.master_division(id),
    division_name VARCHAR(200),
    manager_id INTEGER,
    manager_name VARCHAR(200),
    employee_count INTEGER DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create internal_employee table (for user management)
CREATE TABLE IF NOT EXISTS esb_data.internal_employee (
    id SERIAL PRIMARY KEY,
    employee_code VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(200) UNIQUE,
    phone VARCHAR(50),
    division_id INTEGER REFERENCES esb_data.master_division(id),
    division_name VARCHAR(200),
    department_id INTEGER REFERENCES esb_data.master_department(id),
    department_name VARCHAR(200),
    position VARCHAR(200),
    employee_type VARCHAR(50) DEFAULT 'STAFF',
    rate_class VARCHAR(50),
    base_salary NUMERIC(15, 2),
    salary_type VARCHAR(20) DEFAULT 'MONTHLY',
    join_date DATE,
    resign_date DATE,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    branch_id INTEGER REFERENCES esb_data.master_branch(id),
    branch_name VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Create internal_user table
CREATE TABLE IF NOT EXISTS esb_data.internal_user (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES esb_data.internal_employee(id),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    full_name VARCHAR(200),
    role VARCHAR(50) DEFAULT 'USER',
    role_id INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Create master_role table
CREATE TABLE IF NOT EXISTS esb_data.master_role (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Create master_permission table
CREATE TABLE IF NOT EXISTS esb_data.master_permission (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    module VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Create role_permission junction table
CREATE TABLE IF NOT EXISTS esb_data.role_permission (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES esb_data.master_role(id),
    permission_id INTEGER NOT NULL REFERENCES esb_data.master_permission(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(role_id, permission_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_md_division_active ON esb_data.master_division(is_active);
CREATE INDEX IF NOT EXISTS idx_md_department_division ON esb_data.master_department(division_id);
CREATE INDEX IF NOT EXISTS idx_md_department_active ON esb_data.master_department(is_active);
CREATE INDEX IF NOT EXISTS idx_ie_employee_status ON esb_data.internal_employee(status);
CREATE INDEX IF NOT EXISTS idx_ie_branch ON esb_data.internal_employee(branch_id);
CREATE INDEX IF NOT EXISTS idx_iu_user_active ON esb_data.internal_user(is_active);
CREATE INDEX IF NOT EXISTS idx_iu_user_email ON esb_data.internal_user(email);

-- Insert seed data for divisions
INSERT INTO esb_data.master_division (code, name, manager_name, department_count, total_headcount, is_active)
VALUES
    ('DIV-OPS', 'Operations', 'Andi Wijaya', 3, 45, TRUE),
    ('DIV-MKT', 'Marketing', 'Budi Santoso', 2, 12, TRUE),
    ('DIV-FIN', 'Finance', 'Citra Dewi', 2, 8, TRUE),
    ('DIV-HR', 'Human Resources', 'Eva Marlina', 2, 6, TRUE),
    ('DIV-IT', 'Information Technology', 'Fajar Rahman', 3, 15, TRUE),
    ('DIV-QA', 'Quality Assurance', 'Gita Pratiwi', 2, 10, TRUE),
    ('DIV-SCM', 'Supply Chain', 'Hadi Prasetyo', 2, 18, TRUE)
ON CONFLICT (code) DO NOTHING;

-- Insert seed data for departments
INSERT INTO esb_data.master_department (code, name, division_id, division_name, manager_name, employee_count, is_active)
SELECT
    d.code, d.name, dv.id, dv.name, d.manager, d.headcount, TRUE
FROM (
    VALUES
        ('OPS-MGT', 'Operations Management', 'DIV-OPS', 'Operations', 'Andi Wijaya', 5),
        ('OPS-KTN', 'Kitchen Operations', 'DIV-OPS', 'Operations', 'Dedi Kurniawan', 20),
        ('OPS-SVC', 'Service Quality', 'DIV-OPS', 'Operations', 'Budi Santoso', 20),
        ('MKT-STR', 'Marketing Strategy', 'DIV-MKT', 'Marketing', '-', 6),
        ('MKT-DGT', 'Digital Marketing', 'DIV-MKT', 'Marketing', '-', 6),
        ('FIN-PLN', 'Financial Planning', 'DIV-FIN', 'Finance', 'Citra Dewi', 4),
        ('FIN-ACC', 'Accounting', 'DIV-FIN', 'Finance', '-', 4),
        ('HR-REC', 'Recruitment', 'DIV-HR', 'Human Resources', 'Eva Marlina', 3),
        ('HR-DEV', 'People Development', 'DIV-HR', 'Human Resources', '-', 3),
        ('IT-INF', 'IT Infrastructure', 'DIV-IT', 'Information Technology', 'Fajar Rahman', 5),
        ('IT-DEV', 'Software Development', 'DIV-IT', 'Information Technology', '-', 6),
        ('IT-SUP', 'IT Support', 'DIV-IT', 'Information Technology', '-', 4),
        ('QA-QC', 'Quality Control', 'DIV-QA', 'Quality Assurance', 'Gita Pratiwi', 5),
        ('QA-FS', 'Food Safety', 'DIV-QA', 'Quality Assurance', '-', 5),
        ('SCM-PRO', 'Procurement', 'DIV-SCM', 'Supply Chain', 'Hadi Prasetyo', 8),
        ('SCM-WH', 'Warehouse', 'DIV-SCM', 'Supply Chain', '-', 10)
) AS d(code, name, div_code, div_name, manager, headcount)
JOIN esb_data.master_division dv ON dv.code = d.div_code
ON CONFLICT (code) DO NOTHING;

-- Insert seed data for roles
INSERT INTO esb_data.master_role (code, name, description, is_system)
VALUES
    ('ADMIN', 'Administrator', 'Full system access', TRUE),
    ('MANAGER', 'Manager', 'Manager level access', FALSE),
    ('SUPERVISOR', 'Supervisor', 'Supervisor level access', FALSE),
    ('STAFF', 'Staff', 'Regular staff access', FALSE)
ON CONFLICT (code) DO NOTHING;

-- Insert seed data for permissions
INSERT INTO esb_data.master_permission (code, name, module)
VALUES
    -- Approval permissions
    ('approval.config.view', 'View Approval Configurations', 'approval.config'),
    ('approval.config.create', 'Create Approval Configuration', 'approval.config'),
    ('approval.config.update', 'Update Approval Configuration', 'approval.config'),
    ('approval.config.delete', 'Delete Approval Configuration', 'approval.config'),
    ('approval.request.view', 'View Approval Requests', 'approval.request'),
    ('approval.request.create', 'Create Approval Request', 'approval.request'),
    ('approval.request.approve', 'Approve Request', 'approval.request'),
    ('approval.request.reject', 'Reject Request', 'approval.request'),
    ('approval.rbac.view', 'View RBAC Settings', 'approval.rbac'),
    ('approval.rbac.manage', 'Manage RBAC Settings', 'approval.rbac'),
    -- User management permissions
    ('user.view', 'View Users', 'user'),
    ('user.create', 'Create User', 'user'),
    ('user.update', 'Update User', 'user'),
    ('user.delete', 'Delete User', 'user'),
    -- Department permissions
    ('department.view', 'View Departments', 'department'),
    ('department.create', 'Create Department', 'department'),
    ('department.update', 'Update Department', 'department'),
    ('department.delete', 'Delete Department', 'department'),
    -- Division permissions
    ('division.view', 'View Divisions', 'division'),
    ('division.create', 'Create Division', 'division'),
    ('division.update', 'Update Division', 'division'),
    ('division.delete', 'Delete Division', 'division'),
    -- Stock & Waste permissions
    ('stock.view', 'View Stock Opname', 'stock'),
    ('stock.create', 'Create Stock Opname', 'stock'),
    ('stock.approve', 'Approve Stock Opname', 'stock'),
    ('waste.view', 'View Waste Form', 'waste'),
    ('waste.create', 'Create Waste Form', 'waste'),
    ('waste.approve', 'Approve Waste Form', 'waste')
ON CONFLICT (code) DO NOTHING;

-- Assign all permissions to Admin role
INSERT INTO esb_data.role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM esb_data.master_role r
CROSS JOIN esb_data.master_permission p
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- Assign view permissions to Manager role
INSERT INTO esb_data.role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM esb_data.master_role r
CROSS JOIN esb_data.master_permission p
WHERE r.code = 'MANAGER'
AND (p.code LIKE '%.view' OR p.code LIKE '%.approve')
ON CONFLICT DO NOTHING;

-- Assign view and create permissions to Staff role
INSERT INTO esb_data.role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM esb_data.master_role r
CROSS JOIN esb_data.master_permission p
WHERE r.code = 'STAFF'
AND (p.code LIKE '%.view' OR p.code LIKE '%.create')
ON CONFLICT DO NOTHING;

-- Update department counts in divisions
UPDATE esb_data.master_division d
SET department_count = sub.count,
    updated_at = NOW()
FROM (
    SELECT division_id, COUNT(*) as count
    FROM esb_data.master_department
    WHERE is_active = TRUE
    GROUP BY division_id
) sub
WHERE d.id = sub.division_id;

-- Update headcount in departments
UPDATE esb_data.master_department d
SET employee_count = sub.count,
    updated_at = NOW()
FROM (
    SELECT department_id, COUNT(*) as count
    FROM esb_data.internal_employee
    WHERE status = 'ACTIVE'
    GROUP BY department_id
) sub
WHERE d.id = sub.department_id;

-- Update total headcount in divisions
UPDATE esb_data.master_division d
SET total_headcount = sub.count,
    updated_at = NOW()
FROM (
    SELECT division_id, COUNT(*) as count
    FROM esb_data.internal_employee
    WHERE status = 'ACTIVE'
    GROUP BY division_id
) sub
WHERE d.id = sub.division_id;

COMMIT;
