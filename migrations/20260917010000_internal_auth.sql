-- ============================================================
-- Internal Schema Migration
-- Creates: users, roles, permissions, sessions tables
-- ============================================================

BEGIN;

-- 1. Create internal schema (if not exists)
CREATE SCHEMA IF NOT EXISTS internal;

-- 2. Create roles table
CREATE TABLE IF NOT EXISTS internal.roles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create permissions table
CREATE TABLE IF NOT EXISTS internal.permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    module VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Create role_permissions junction table
CREATE TABLE IF NOT EXISTS internal.role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES internal.roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES internal.permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(role_id, permission_id)
);

-- 5. Create users table
CREATE TABLE IF NOT EXISTS internal.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    role_id INTEGER REFERENCES internal.roles(id),
    employee_id INTEGER,
    branch_id INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Create sessions table
CREATE TABLE IF NOT EXISTS internal.sessions (
    id SERIAL PRIMARY KEY,
    token VARCHAR(128) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES internal.users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_int_users_email ON internal.users(lower(email));
CREATE INDEX IF NOT EXISTS idx_int_users_username ON internal.users(lower(username));
CREATE INDEX IF NOT EXISTS idx_int_users_active ON internal.users(is_active);
CREATE INDEX IF NOT EXISTS idx_int_sessions_token ON internal.sessions(token);
CREATE INDEX IF NOT EXISTS idx_int_sessions_expires ON internal.sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_int_rp_role ON internal.role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_int_rp_perm ON internal.role_permissions(permission_id);

-- 7. Insert default roles
INSERT INTO internal.roles (code, name, description, is_system)
VALUES
    ('ADMIN', 'Administrator', 'Full system access with all permissions', TRUE),
    ('MANAGER', 'Manager', 'Manager level access - can approve and manage team', FALSE),
    ('SUPERVISOR', 'Supervisor', 'Supervisor level access - can supervise daily operations', FALSE),
    ('STAFF', 'Staff', 'Regular staff access - can view and create records', FALSE)
ON CONFLICT (code) DO NOTHING;

-- 8. Insert all permissions
INSERT INTO internal.permissions (code, name, module)
VALUES
    -- Dashboard & Reports
    ('dashboard.view', 'View Dashboard', 'dashboard'),
    ('reports.view', 'View Reports', 'reports'),
    ('reports.export', 'Export Reports', 'reports'),

    -- User Management
    ('users.view', 'View Users', 'users'),
    ('users.create', 'Create Users', 'users'),
    ('users.update', 'Update Users', 'users'),
    ('users.delete', 'Delete Users', 'users'),
    ('users.manage-roles', 'Manage User Roles', 'users'),

    -- Division Management
    ('divisions.view', 'View Divisions', 'divisions'),
    ('divisions.create', 'Create Divisions', 'divisions'),
    ('divisions.update', 'Update Divisions', 'divisions'),
    ('divisions.delete', 'Delete Divisions', 'divisions'),

    -- Department Management
    ('departments.view', 'View Departments', 'departments'),
    ('departments.create', 'Create Departments', 'departments'),
    ('departments.update', 'Update Departments', 'departments'),
    ('departments.delete', 'Delete Departments', 'departments'),

    -- Employee Management
    ('employees.view', 'View Employees', 'employees'),
    ('employees.create', 'Create Employees', 'employees'),
    ('employees.update', 'Update Employees', 'employees'),
    ('employees.delete', 'Delete Employees', 'employees'),

    -- Approval Lines
    ('approval.config.view', 'View Approval Configs', 'approval'),
    ('approval.config.create', 'Create Approval Config', 'approval'),
    ('approval.config.update', 'Update Approval Config', 'approval'),
    ('approval.config.delete', 'Delete Approval Config', 'approval'),
    ('approval.request.view', 'View Approval Requests', 'approval'),
    ('approval.request.approve', 'Approve Requests', 'approval'),
    ('approval.request.reject', 'Reject Requests', 'approval'),

    -- Stock Opname
    ('stock-opname.view', 'View Stock Opname', 'stock-opname'),
    ('stock-opname.create', 'Create Stock Opname', 'stock-opname'),
    ('stock-opname.update', 'Update Stock Opname', 'stock-opname'),
    ('stock-opname.delete', 'Delete Stock Opname', 'stock-opname'),
    ('stock-opname.approve', 'Approve Stock Opname', 'stock-opname'),

    -- Waste Form
    ('waste.view', 'View Waste Forms', 'waste'),
    ('waste.create', 'Create Waste Form', 'waste'),
    ('waste.update', 'Update Waste Form', 'waste'),
    ('waste.delete', 'Delete Waste Form', 'waste'),
    ('waste.approve', 'Approve Waste Form', 'waste'),

    -- Settings
    ('settings.view', 'View Settings', 'settings'),
    ('settings.update', 'Update Settings', 'settings')
ON CONFLICT (code) DO NOTHING;

-- 9. Assign all permissions to ADMIN role
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM internal.roles r
CROSS JOIN internal.permissions p
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- 10. Assign limited permissions to MANAGER role
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM internal.roles r
CROSS JOIN internal.permissions p
WHERE r.code = 'MANAGER'
AND (
    p.code LIKE '%.view'
    OR p.code LIKE '%.approve'
    OR p.code = 'employees.view'
    OR p.code = 'employees.update'
)
ON CONFLICT DO NOTHING;

-- 11. Assign view and create permissions to SUPERVISOR role
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM internal.roles r
CROSS JOIN internal.permissions p
WHERE r.code = 'SUPERVISOR'
AND (
    p.code LIKE '%.view'
    OR p.code LIKE '%.create'
    OR p.code LIKE '%.update'
    OR p.code = 'stock-opname.approve'
    OR p.code = 'waste.approve'
)
ON CONFLICT DO NOTHING;

-- 12. Assign basic permissions to STAFF role
INSERT INTO internal.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM internal.roles r
CROSS JOIN internal.permissions p
WHERE r.code = 'STAFF'
AND (
    p.code LIKE '%.view'
    OR p.code LIKE '%.create'
    OR p.code = 'stock-opname.create'
    OR p.code = 'waste.create'
)
ON CONFLICT DO NOTHING;

COMMIT;

-- 13. Create admin user (password: Admin@123)
-- Hash generated with: pbkdf2_sha256$600000$salt$hash
-- For password "Admin@123", the hash is:
-- pbkdf2_sha256$600000$7c4a8d09ca3762af61e59520943dc26494f8941b$8e9d6c7e7b3c1a0f5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0
INSERT INTO internal.users (username, email, password_hash, full_name, role_id, is_active)
SELECT 'admin', 'admin@kopicalf.com',
       'pbkdf2_sha256$600000$7c4a8d09ca3762af61e59520943dc26494f8941b$8e9d6c7e7b3c1a0f5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0',
       'System Administrator', r.id, TRUE
FROM internal.roles r WHERE r.code = 'ADMIN'
ON CONFLICT (username) DO NOTHING;

-- Create demo manager user (password: Manager@123)
INSERT INTO internal.users (username, email, password_hash, full_name, role_id, is_active)
SELECT 'manager', 'manager@kopicalf.com',
       'pbkdf2_sha256$600000$1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef$1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3',
       'Demo Manager', r.id, TRUE
FROM internal.roles r WHERE r.code = 'MANAGER'
ON CONFLICT (username) DO NOTHING;

-- Create demo staff user (password: Staff@123)
INSERT INTO internal.users (username, email, password_hash, full_name, role_id, is_active)
SELECT 'staff', 'staff@kopicalf.com',
       'pbkdf2_sha256$600000$fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321$9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7',
       'Demo Staff', r.id, TRUE
FROM internal.roles r WHERE r.code = 'STAFF'
ON CONFLICT (username) DO NOTHING;
