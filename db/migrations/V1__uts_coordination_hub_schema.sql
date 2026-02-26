IF OBJECT_ID('complexes', 'U') IS NULL
CREATE TABLE complexes (
  complex_id UNIQUEIDENTIFIER PRIMARY KEY,
  name NVARCHAR(255) NOT NULL,
  address NVARCHAR(500) NULL,
  status NVARCHAR(50) NOT NULL DEFAULT 'active'
);

IF OBJECT_ID('users', 'U') IS NULL
CREATE TABLE users (
  user_id UNIQUEIDENTIFIER PRIMARY KEY,
  mobile NVARCHAR(50) NULL,
  email NVARCHAR(255) NULL,
  status NVARCHAR(50) NOT NULL DEFAULT 'active',
  id_number_encrypted VARBINARY(MAX) NULL,
  id_number_hash VARBINARY(32) NULL
);

IF OBJECT_ID('user_complex_roles', 'U') IS NULL
CREATE TABLE user_complex_roles (
  user_id UNIQUEIDENTIFIER NOT NULL,
  complex_id UNIQUEIDENTIFIER NOT NULL,
  role NVARCHAR(100) NOT NULL,
  start_date DATE NULL,
  end_date DATE NULL,
  PRIMARY KEY (user_id, complex_id, role),
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (complex_id) REFERENCES complexes(complex_id)
);

IF OBJECT_ID('units', 'U') IS NULL
CREATE TABLE units (
  unit_id UNIQUEIDENTIFIER PRIMARY KEY,
  complex_id UNIQUEIDENTIFIER NOT NULL,
  unit_number NVARCHAR(50) NOT NULL,
  owner_user_id UNIQUEIDENTIFIER NULL,
  occupancy_status NVARCHAR(50) NULL,
  tenant_contact NVARCHAR(255) NULL,
  letting_agent_user_id UNIQUEIDENTIFIER NULL,
  FOREIGN KEY (complex_id) REFERENCES complexes(complex_id)
);

IF OBJECT_ID('delegation_rules', 'U') IS NULL
CREATE TABLE delegation_rules (
  delegation_rule_id UNIQUEIDENTIFIER PRIMARY KEY,
  complex_id UNIQUEIDENTIFIER NOT NULL,
  owner_user_id UNIQUEIDENTIFIER NOT NULL,
  agent_user_id UNIQUEIDENTIFIER NOT NULL,
  scope NVARCHAR(100) NOT NULL,
  start_date DATE NULL,
  end_date DATE NULL
);

IF OBJECT_ID('rule_profiles', 'U') IS NULL
CREATE TABLE rule_profiles (
  complex_id UNIQUEIDENTIFIER NOT NULL,
  rule_profile_id UNIQUEIDENTIFIER NOT NULL,
  version INT NOT NULL,
  status NVARCHAR(50) NOT NULL,
  effective_from DATETIME2 NOT NULL,
  json_config NVARCHAR(MAX) NOT NULL,
  PRIMARY KEY (complex_id, rule_profile_id, version)
);

IF OBJECT_ID('decision_trees', 'U') IS NULL
CREATE TABLE decision_trees (
  complex_id UNIQUEIDENTIFIER NOT NULL,
  tree_id UNIQUEIDENTIFIER NOT NULL,
  version INT NOT NULL,
  json_definition NVARCHAR(MAX) NOT NULL,
  PRIMARY KEY (complex_id, tree_id, version)
);

IF OBJECT_ID('templates', 'U') IS NULL
CREATE TABLE templates (
  complex_id UNIQUEIDENTIFIER NOT NULL,
  template_id UNIQUEIDENTIFIER NOT NULL,
  version INT NOT NULL,
  channel NVARCHAR(20) NOT NULL,
  body_html NVARCHAR(MAX) NULL,
  body_md NVARCHAR(MAX) NULL,
  PRIMARY KEY (complex_id, template_id, version)
);

IF OBJECT_ID('retention_policies', 'U') IS NULL
CREATE TABLE retention_policies (
  complex_id UNIQUEIDENTIFIER NOT NULL,
  record_type NVARCHAR(100) NOT NULL,
  retention_years INT NOT NULL,
  anonymise_after_expiry BIT NOT NULL DEFAULT 1,
  legal_hold_supported BIT NOT NULL DEFAULT 1,
  PRIMARY KEY (complex_id, record_type)
);

IF OBJECT_ID('cases', 'U') IS NULL
CREATE TABLE cases (
  case_id UNIQUEIDENTIFIER PRIMARY KEY,
  complex_id UNIQUEIDENTIFIER NOT NULL,
  unit_id UNIQUEIDENTIFIER NULL,
  category NVARCHAR(50) NOT NULL,
  type NVARCHAR(100) NOT NULL,
  status NVARCHAR(50) NOT NULL,
  created_at DATETIME2 NOT NULL,
  rule_profile_id UNIQUEIDENTIFIER NULL,
  rule_profile_version INT NULL,
  approval_matrix_version INT NULL,
  risk_tier NVARCHAR(20) NOT NULL,
  created_by_user_id UNIQUEIDENTIFIER NOT NULL,
  impacted_parties_json NVARCHAR(MAX) NULL,
  retention_expiry_at DATETIME2 NULL,
  legal_hold BIT NOT NULL DEFAULT 0,
  FOREIGN KEY (complex_id) REFERENCES complexes(complex_id)
);

IF OBJECT_ID('approvals', 'U') IS NULL
CREATE TABLE approvals (
  approval_id UNIQUEIDENTIFIER PRIMARY KEY,
  case_id UNIQUEIDENTIFIER NOT NULL,
  complex_id UNIQUEIDENTIFIER NOT NULL,
  approver_user_id UNIQUEIDENTIFIER NOT NULL,
  approver_role NVARCHAR(100) NOT NULL,
  decision NVARCHAR(50) NOT NULL,
  conditions NVARCHAR(MAX) NULL,
  decided_at DATETIME2 NULL,
  FOREIGN KEY (case_id) REFERENCES cases(case_id)
);

IF OBJECT_ID('attachments', 'U') IS NULL
CREATE TABLE attachments (
  attachment_id UNIQUEIDENTIFIER PRIMARY KEY,
  complex_id UNIQUEIDENTIFIER NOT NULL,
  case_id UNIQUEIDENTIFIER NOT NULL,
  blob_uri NVARCHAR(1000) NOT NULL,
  sha256 VARBINARY(32) NOT NULL,
  uploaded_by UNIQUEIDENTIFIER NOT NULL,
  uploaded_at DATETIME2 NOT NULL,
  FOREIGN KEY (case_id) REFERENCES cases(case_id)
);

IF OBJECT_ID('audit_log', 'U') IS NULL
CREATE TABLE audit_log (
  audit_id BIGINT IDENTITY(1,1) PRIMARY KEY,
  complex_id UNIQUEIDENTIFIER NOT NULL,
  case_id UNIQUEIDENTIFIER NULL,
  actor_user_id UNIQUEIDENTIFIER NULL,
  event_type NVARCHAR(100) NOT NULL,
  event_json NVARCHAR(MAX) NOT NULL,
  created_at DATETIME2 NOT NULL
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_users_id_hash' AND object_id = OBJECT_ID('users'))
CREATE UNIQUE INDEX ux_users_id_hash ON users(id_number_hash);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_cases_complex_status_created' AND object_id = OBJECT_ID('cases'))
CREATE INDEX ix_cases_complex_status_created ON cases(complex_id, status, created_at DESC);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_audit_complex_created' AND object_id = OBJECT_ID('audit_log'))
CREATE INDEX ix_audit_complex_created ON audit_log(complex_id, created_at DESC);
