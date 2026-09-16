-- ============================================================
-- Approval Lines Migration
-- Creates tables for multi-level approval workflows
-- ============================================================
BEGIN;

-- 1. Approval Configurations
CREATE TABLE IF NOT EXISTS internal.approval_configurations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    form_type VARCHAR(100) NOT NULL,  -- FACILITY_REQUEST, TOOL_REQUEST, PURCHASE_REQUEST, etc.
    department_id INTEGER REFERENCES internal.departments(id) ON DELETE SET NULL,
    division_id INTEGER REFERENCES internal.divisions(id) ON DELETE SET NULL,
    branch_id INTEGER REFERENCES esb_data.master_branch(id) ON DELETE SET NULL,
    min_amount DECIMAL(15,2),  -- Optional minimum amount threshold
    max_amount DECIMAL(15,2),  -- Optional maximum amount threshold
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR(255),
    UNIQUE(name)
);

COMMENT ON TABLE internal.approval_configurations IS 'Stores approval workflow configurations per form type/department/division';
COMMENT ON COLUMN internal.approval_configurations.form_type IS 'FACILITY_REQUEST, TOOL_REQUEST, PURCHASE_REQUEST, LEAVE_REQUEST, OVERTIME_REQUEST, EXPENSE_REQUEST';
COMMENT ON COLUMN internal.approval_configurations.min_amount IS 'Minimum transaction amount to trigger this config (NULL = always)';
COMMENT ON COLUMN internal.approval_configurations.max_amount IS 'Maximum transaction amount (NULL = no limit)';

CREATE INDEX IF NOT EXISTS idx_approval_configs_form_type ON internal.approval_configurations(form_type);
CREATE INDEX IF NOT EXISTS idx_approval_configs_dept ON internal.approval_configurations(department_id);
CREATE INDEX IF NOT EXISTS idx_approval_configs_active ON internal.approval_configurations(is_active);

-- 2. Approval Levels
CREATE TABLE IF NOT EXISTS internal.approval_levels (
    id SERIAL PRIMARY KEY,
    config_id INTEGER NOT NULL REFERENCES internal.approval_configurations(id) ON DELETE CASCADE,
    level INTEGER NOT NULL CHECK (level > 0),
    name VARCHAR(255) NOT NULL,  -- 'Manager Approval', 'Director Approval', etc.
    approver_type VARCHAR(50) NOT NULL,  -- USER, ROLE, DEPARTMENT_HEAD, DIVISION_HEAD, AUTO
    approver_id INTEGER,  -- user_id or role_id depending on approver_type
    is_auto_approve BOOLEAN DEFAULT FALSE,
    timeout_hours INTEGER,  -- Auto-escalate after N hours
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR(255),
    UNIQUE(config_id, level)
);

COMMENT ON TABLE internal.approval_levels IS 'Defines approval levels within a configuration (Level 1, Level 2, etc.)';
COMMENT ON COLUMN internal.approval_levels.approver_type IS 'USER=specific user, ROLE=users with role, DEPARTMENT_HEAD=auto from dept, DIVISION_HEAD=auto from division, AUTO=self-approve';

CREATE INDEX IF NOT EXISTS idx_approval_levels_config ON internal.approval_levels(config_id);
CREATE INDEX IF NOT EXISTS idx_approval_levels_order ON internal.approval_levels(config_id, level);

-- 3. Approval Approvers (Many-to-Many for levels)
CREATE TABLE IF NOT EXISTS internal.approval_approvers (
    id SERIAL PRIMARY KEY,
    level_id INTEGER NOT NULL REFERENCES internal.approval_levels(id) ON DELETE CASCADE,
    approver_type VARCHAR(50) NOT NULL,  -- USER, ROLE, DEPARTMENT_HEAD, DIVISION_HEAD
    approver_id INTEGER NOT NULL,  -- user_id or role_id
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE internal.approval_approvers IS 'Assigns multiple approvers per level (alternative approvers)';

CREATE INDEX IF NOT EXISTS idx_approval_approvers_level ON internal.approval_approvers(level_id);
CREATE INDEX IF NOT EXISTS idx_approval_approvers_lookup ON internal.approval_approvers(approver_type, approver_id);

-- 4. Approval Requests (submitted forms awaiting approval)
CREATE TABLE IF NOT EXISTS internal.approval_requests (
    id SERIAL PRIMARY KEY,
    config_id INTEGER REFERENCES internal.approval_configurations(id) ON DELETE SET NULL,
    form_type VARCHAR(100) NOT NULL,
    reference_id VARCHAR(255) NOT NULL,  -- ID of the original form record
    requester_id INTEGER NOT NULL REFERENCES internal.users(id),
    department_id INTEGER REFERENCES internal.departments(id) ON DELETE SET NULL,
    division_id INTEGER REFERENCES internal.divisions(id) ON DELETE SET NULL,
    branch_id INTEGER REFERENCES esb_data.master_branch(id) ON DELETE SET NULL,
    amount DECIMAL(15,2),  -- Transaction amount
    data_json JSONB,  -- Serialized form data for audit
    current_level INTEGER DEFAULT 1,  -- Current approval level
    status VARCHAR(50) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    rejection_reason TEXT,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR(255)
);

COMMENT ON TABLE internal.approval_requests IS 'Tracks submitted approval requests and their current status';
COMMENT ON COLUMN internal.approval_requests.status IS 'PENDING=waiting approval, APPROVED=fully approved, REJECTED=rejected, CANCELLED=withdrawn';

CREATE INDEX IF NOT EXISTS idx_approval_requests_config ON internal.approval_requests(config_id);
CREATE INDEX IF NOT EXISTS idx_approval_requests_requester ON internal.approval_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON internal.approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requests_ref ON internal.approval_requests(form_type, reference_id);

-- 5. Approval History (audit trail)
CREATE TABLE IF NOT EXISTS internal.approval_history (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES internal.approval_requests(id) ON DELETE CASCADE,
    level_id INTEGER REFERENCES internal.approval_levels(id) ON DELETE SET NULL,
    actor_id INTEGER REFERENCES internal.users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('SUBMIT', 'APPROVE', 'REJECT', 'REQUEST_INFO', 'CANCEL', 'ESCALATE', 'AUTO_APPROVE')),
    note TEXT,
    metadata JSONB,  -- Additional context (e.g., attached files)
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE internal.approval_history IS 'Complete audit trail of all actions on approval requests';

CREATE INDEX IF NOT EXISTS idx_approval_history_request ON internal.approval_history(request_id);
CREATE INDEX IF NOT EXISTS idx_approval_history_actor ON internal.approval_history(actor_id);
CREATE INDEX IF NOT EXISTS idx_approval_history_time ON internal.approval_history(created_at);

-- 6. Approval Permissions (RBAC for approval system)
CREATE TABLE IF NOT EXISTS internal.approval_permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    module VARCHAR(100) NOT NULL,  -- approval, approval.config, approval.request, approval.rbac
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE internal.approval_permissions IS 'Permission definitions for the approval system';

CREATE INDEX IF NOT EXISTS idx_approval_perms_module ON internal.approval_permissions(module);

-- Insert default approval permissions
INSERT INTO internal.approval_permissions (code, name, module, description, is_system) VALUES
    -- Config management
    ('approval.config.view', 'View Approval Configurations', 'approval.config', 'View list of approval configurations', TRUE),
    ('approval.config.create', 'Create Approval Configuration', 'approval.config', 'Create new approval configuration', TRUE),
    ('approval.config.update', 'Update Approval Configuration', 'approval.config', 'Edit existing approval configuration', TRUE),
    ('approval.config.delete', 'Delete Approval Configuration', 'approval.config', 'Delete approval configuration', TRUE),
    -- Request management
    ('approval.request.view', 'View Approval Requests', 'approval.request', 'View list of approval requests', TRUE),
    ('approval.request.create', 'Create Approval Request', 'approval.request', 'Submit new approval request', TRUE),
    ('approval.request.approve', 'Approve Request', 'approval.request', 'Approve an approval request', TRUE),
    ('approval.request.reject', 'Reject Request', 'approval.request', 'Reject an approval request', TRUE),
    ('approval.request.cancel', 'Cancel Own Request', 'approval.request', 'Cancel own approval request', TRUE),
    -- RBAC
    ('approval.rbac.view', 'View RBAC Settings', 'approval.rbac', 'View approval RBAC settings', TRUE),
    ('approval.rbac.manage', 'Manage RBAC Settings', 'approval.rbac', 'Manage roles and permissions for approval', TRUE)
ON CONFLICT (code) DO NOTHING;

-- 7. Role Permission Assignments (extend existing role_permissions)
-- This creates a separate table for approval-specific role permissions
CREATE TABLE IF NOT EXISTS internal.approval_role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES internal.roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES internal.approval_permissions(id) ON DELETE CASCADE,
    granted_by INTEGER REFERENCES internal.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(role_id, permission_id)
);

COMMENT ON TABLE internal.approval_role_permissions IS 'Maps roles to approval permissions (extends internal.role_permissions)';

CREATE INDEX IF NOT EXISTS idx_approval_role_perms_role ON internal.approval_role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_approval_role_perms_perm ON internal.approval_role_permissions(permission_id);

-- 8. Page Access Control (for granular page-level RBAC)
CREATE TABLE IF NOT EXISTS internal.approval_page_access (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES internal.roles(id) ON DELETE CASCADE,
    page_path VARCHAR(255) NOT NULL,  -- '/management/approval-lines', '/management/users', etc.
    can_view BOOLEAN DEFAULT FALSE,
    can_create BOOLEAN DEFAULT FALSE,
    can_edit BOOLEAN DEFAULT FALSE,
    can_delete BOOLEAN DEFAULT FALSE,
    granted_by INTEGER REFERENCES internal.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(role_id, page_path)
);

COMMENT ON TABLE internal.approval_page_access IS 'Granular page-level access control per role (view/create/edit/delete)';
COMMENT ON COLUMN internal.approval_page_access.page_path IS 'Application path, e.g. /management/approval-lines, /operational/form/facility-request';

CREATE INDEX IF NOT EXISTS idx_approval_page_access_role ON internal.approval_page_access(role_id);
CREATE INDEX IF NOT EXISTS idx_approval_page_access_path ON internal.approval_page_access(page_path);

-- 9. User Page Access Override (individual user overrides)
CREATE TABLE IF NOT EXISTS internal.approval_user_page_access (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES internal.users(id) ON DELETE CASCADE,
    page_path VARCHAR(255) NOT NULL,
    can_view BOOLEAN DEFAULT FALSE,
    can_create BOOLEAN DEFAULT FALSE,
    can_edit BOOLEAN DEFAULT FALSE,
    can_delete BOOLEAN DEFAULT FALSE,
    granted_by INTEGER REFERENCES internal.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, page_path)
);

COMMENT ON TABLE internal.approval_user_page_access IS 'Individual user overrides for page access (takes precedence over role)';

CREATE INDEX IF NOT EXISTS idx_approval_user_page_access_user ON internal.approval_user_page_access(user_id);

-- 10. Departments (if not exists)
CREATE TABLE IF NOT EXISTS internal.departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    division_id INTEGER REFERENCES internal.divisions(id) ON DELETE SET NULL,
    head_user_id INTEGER REFERENCES internal.users(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_departments_division ON internal.departments(division_id);

-- 11. Divisions (if not exists)
CREATE TABLE IF NOT EXISTS internal.divisions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    head_user_id INTEGER REFERENCES internal.users(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert sample departments and divisions
INSERT INTO internal.divisions (name, code) VALUES
    ('Operations', 'OPS'),
    ('Finance', 'FIN'),
    ('Human Resources', 'HR'),
    ('Marketing', 'MKT')
ON CONFLICT (code) DO NOTHING;

INSERT INTO internal.departments (name, code, division_id) VALUES
    ('Kitchen', 'KIT', (SELECT id FROM internal.divisions WHERE code = 'OPS')),
    ('Service', 'SVC', (SELECT id FROM internal.divisions WHERE code = 'OPS')),
    ('Inventory', 'INV', (SELECT id FROM internal.divisions WHERE code = 'OPS')),
    ('Accounting', 'ACC', (SELECT id FROM internal.divisions WHERE code = 'FIN')),
    ('General Affair', 'GA', (SELECT id FROM internal.divisions WHERE code = 'FIN')),
    ('Recruitment', 'REC', (SELECT id FROM internal.divisions WHERE code = 'HR')),
    ('Training', 'TRN', (SELECT id FROM internal.divisions WHERE code = 'HR'))
ON CONFLICT (code) DO NOTHING;

COMMIT;
