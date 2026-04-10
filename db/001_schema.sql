-- ============================================================
-- SMARTCLICK ERP — PostgreSQL Schema v1.0
-- Mathieu Pleitinx · Smartclick BV · BE0746385009
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- pour la recherche full-text

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE client_status      AS ENUM ('actif', 'dormant', 'inactif', 'contentieux', 'décédé');
CREATE TYPE client_type        AS ENUM ('entreprise', 'asbl', 'particulier', 'interne');
CREATE TYPE contract_type      AS ENUM ('maintenance', 'lm_forensics', 'lm_datashredding', 'lm_dev', 'lm_it_management', 'devis', 'autre');
CREATE TYPE contract_status    AS ENUM ('brouillon', 'envoyé', 'signé', 'actif', 'expiré', 'résilié');
CREATE TYPE billing_type       AS ENUM ('forfait_mensuel', 'forfait_projet', 'regie', 'inclus');
CREATE TYPE project_status     AS ENUM ('open', 'waiting_third_party', 'to_invoice', 'done', 'archived');
CREATE TYPE project_priority   AS ENUM ('low', 'normal', 'high', 'urgent');
CREATE TYPE equipment_type     AS ENUM ('desktop', 'laptop', 'server', 'nas', 'switch', 'router', 'printer', 'other');
CREATE TYPE equipment_status   AS ENUM ('active', 'in_repair', 'retired', 'shredded');
CREATE TYPE intervention_type  AS ENUM ('maintenance', 'repair', 'datashredding', 'forensics_prep', 'other');
CREATE TYPE forensics_status   AS ENUM ('ouvert', 'en_cours', 'en_attente', 'clôturé');
CREATE TYPE evidence_type      AS ENUM ('disque_dur', 'usb', 'fichier', 'email', 'log', 'autre');
CREATE TYPE document_type      AS ENUM ('CM', 'LM_FOR', 'LM_DS', 'LM_DEV', 'LM_IT', 'DEVIS', 'RAP_ATELIER', 'RAP_FORENSICS', 'AUTRE');
CREATE TYPE docuseal_status    AS ENUM ('pending', 'signed', 'declined', 'expired');
CREATE TYPE falco_status       AS ENUM ('pending', 'accepted', 'rejected', 'failed');
CREATE TYPE activity_log_type  AS ENUM ('session', 'document', 'contrat', 'signature', 'note', 'email', 'intervention', 'forensics');

-- ============================================================
-- CORE — CLIENTS & SITES
-- ============================================================

CREATE TABLE clients (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(200) NOT NULL,
    status              client_status NOT NULL DEFAULT 'actif',
    client_type         client_type NOT NULL DEFAULT 'entreprise',
    vat_number          VARCHAR(30) UNIQUE,
    address             TEXT,
    phone               VARCHAR(50),
    email               VARCHAR(200),
    -- NAS
    nas_path            VARCHAR(500),
    -- Intégrations
    falco_customer_id   VARCHAR(100) UNIQUE,
    -- Gestion
    notes               TEXT,
    inactive_reason     TEXT,
    outstanding_debt    DECIMAL(10,2) NOT NULL DEFAULT 0,
    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE clients IS 'Entité centrale. Tous les autres modules y font référence.';
COMMENT ON COLUMN clients.nas_path IS 'Chemin Synology Drive ex: /1. Smartclick Clients/Groupe ML/';
COMMENT ON COLUMN clients.outstanding_debt IS 'Montant dû non récupéré. Ex: 20STM = 5000€';

-- ──────────────────────────────────────────────────────────

CREATE TABLE sites (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    address     TEXT,
    nas_path    VARCHAR(500),
    is_primary  BOOLEAN NOT NULL DEFAULT FALSE,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sites IS 'Sous-entités géographiques. Ex: Groupe ML → Grimbergen, Kortenberg, Perwez.';

-- ──────────────────────────────────────────────────────────

CREATE TABLE contacts (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    site_id     UUID REFERENCES sites(id) ON DELETE SET NULL,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(200),
    phone       VARCHAR(50),
    role        VARCHAR(100),
    is_primary  BOOLEAN NOT NULL DEFAULT FALSE,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CONTRATS & LETTRES DE MISSION
-- ============================================================

CREATE TABLE contracts (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id               UUID NOT NULL REFERENCES clients(id),
    site_id                 UUID REFERENCES sites(id) ON DELETE SET NULL,
    contract_type           contract_type NOT NULL,
    reference               VARCHAR(100) UNIQUE NOT NULL,
    title                   VARCHAR(300) NOT NULL,
    status                  contract_status NOT NULL DEFAULT 'brouillon',
    -- Durée
    start_date              DATE,
    end_date                DATE,
    renewal_reminder_days   INTEGER NOT NULL DEFAULT 30,
    -- Financier
    billing_type            billing_type NOT NULL,
    sold_hours              DECIMAL(8,2),
    sold_budget             DECIMAL(10,2),
    hourly_rate             DECIMAL(8,2),
    monthly_amount          DECIMAL(10,2),
    -- Intégrations
    falco_project_id        VARCHAR(100),
    docuseal_document_id    VARCHAR(100),
    signed_at               TIMESTAMPTZ,
    signed_by_name          VARCHAR(200),
    signed_by_email         VARCHAR(200),
    signed_pdf_path         VARCHAR(500),
    -- Contenu
    notes                   TEXT,
    template_data           JSONB,  -- données pour génération du document
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN contracts.reference IS 'Généré auto: CM-GML-2026-001, LM-FOR-FC-2026-001, etc.';
COMMENT ON COLUMN contracts.template_data IS 'JSON des champs remplis lors de la création du contrat (utilisateurs, services inclus, etc.)';

-- ──────────────────────────────────────────────────────────

CREATE TABLE contract_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_id     UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    description     TEXT NOT NULL,
    unit_price      DECIMAL(10,2),
    quantity        DECIMAL(8,2) NOT NULL DEFAULT 1,
    unit            VARCHAR(50),  -- utilisateur/mois, heure, forfait
    is_included     BOOLEAN NOT NULL DEFAULT TRUE,
    position        INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- TIME TRACKING
-- ============================================================

CREATE TABLE time_sessions (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id                   UUID NOT NULL REFERENCES clients(id),
    site_id                     UUID REFERENCES sites(id) ON DELETE SET NULL,
    contract_id                 UUID REFERENCES contracts(id) ON DELETE SET NULL,
    project_id                  UUID,  -- FK ajoutée après création table projects
    activity                    VARCHAR(200) NOT NULL,
    description                 TEXT,
    started_at                  TIMESTAMPTZ NOT NULL,
    ended_at                    TIMESTAMPTZ,
    duration_minutes            INTEGER GENERATED ALWAYS AS (
                                    CASE WHEN ended_at IS NOT NULL
                                    THEN EXTRACT(EPOCH FROM (ended_at - started_at))::INTEGER / 60
                                    ELSE NULL END
                                ) STORED,
    is_billable                 BOOLEAN NOT NULL DEFAULT TRUE,
    is_included_in_contract     BOOLEAN NOT NULL DEFAULT FALSE,
    hourly_rate_applied         DECIMAL(8,2),
    amount                      DECIMAL(10,2) GENERATED ALWAYS AS (
                                    CASE WHEN ended_at IS NOT NULL AND hourly_rate_applied IS NOT NULL
                                    THEN ROUND(
                                        (EXTRACT(EPOCH FROM (ended_at - started_at)) / 3600.0) * hourly_rate_applied,
                                    2)
                                    ELSE NULL END
                                ) STORED,
    tags                        TEXT[],
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN time_sessions.duration_minutes IS 'Calculé automatiquement depuis started_at/ended_at';
COMMENT ON COLUMN time_sessions.amount IS 'Calculé automatiquement: (minutes/60) * taux horaire';

-- ──────────────────────────────────────────────────────────

CREATE TABLE session_reports (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID NOT NULL UNIQUE REFERENCES time_sessions(id) ON DELETE CASCADE,
    work_done           TEXT NOT NULL,
    work_pending        TEXT,
    blockers            TEXT,
    next_action         TEXT,
    client_notified     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE session_reports IS 'La fonctionnalité manquante dans Kimai — rapport de fin de session.';

-- ============================================================
-- PROJETS & KANBAN
-- ============================================================

CREATE TABLE kanban_columns (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                  VARCHAR(100) NOT NULL,
    color                 VARCHAR(7) NOT NULL DEFAULT '#607D8B',
    position              INTEGER NOT NULL,
    auto_escalate_days    INTEGER
);

COMMENT ON COLUMN kanban_columns.auto_escalate_days IS 'Nb jours avant mise en évidence rouge automatique si carte immobile';

-- ──────────────────────────────────────────────────────────

CREATE TABLE projects (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id           UUID REFERENCES clients(id) ON DELETE SET NULL,
    contract_id         UUID REFERENCES contracts(id) ON DELETE SET NULL,
    title               VARCHAR(300) NOT NULL,
    description         TEXT,
    status              project_status NOT NULL DEFAULT 'open',
    priority            project_priority NOT NULL DEFAULT 'normal',
    kanban_column_id    UUID REFERENCES kanban_columns(id) ON DELETE SET NULL,
    -- Suivi blocage
    waiting_for         VARCHAR(200),
    waiting_since       DATE,
    auto_remind_days    INTEGER NOT NULL DEFAULT 5,
    last_reminded_at    TIMESTAMPTZ,
    -- Planification
    due_date            DATE,
    estimated_hours     DECIMAL(6,2),
    tags                TEXT[],
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN projects.waiting_for IS 'Tiers bloquant ex: Pootsy, OVH, client, comptable';
COMMENT ON COLUMN projects.auto_remind_days IS 'Après N jours sans mouvement → alerte dashboard + todo automatique';

-- FK retardée sur time_sessions
ALTER TABLE time_sessions ADD CONSTRAINT fk_time_sessions_project
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL;

-- ============================================================
-- ATELIER & PARC IT
-- ============================================================

CREATE TABLE equipment (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id       UUID NOT NULL REFERENCES clients(id),
    site_id         UUID REFERENCES sites(id) ON DELETE SET NULL,
    serial_number   VARCHAR(200) UNIQUE,
    asset_tag       VARCHAR(100),
    type            equipment_type NOT NULL,
    brand           VARCHAR(100),
    model           VARCHAR(200),
    specs_json      JSONB,  -- CPU, RAM, stockage, OS — récupéré par IA
    purchase_date   DATE,
    warranty_until  DATE,
    status          equipment_status NOT NULL DEFAULT 'active',
    nas_path        VARCHAR(500),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN equipment.specs_json IS 'Exemple: {"cpu":"i7-10700","ram_gb":16,"storage":"512GB SSD","os":"Windows 11 Pro"}';

-- ──────────────────────────────────────────────────────────

CREATE TABLE workshop_interventions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id            UUID NOT NULL REFERENCES equipment(id),
    contract_id             UUID REFERENCES contracts(id) ON DELETE SET NULL,
    session_id              UUID REFERENCES time_sessions(id) ON DELETE SET NULL,
    intervention_type       intervention_type NOT NULL,
    intervention_date       DATE NOT NULL,
    technician              VARCHAR(100) NOT NULL DEFAULT 'Mathieu Pleitinx',
    summary                 TEXT,
    checks_json             JSONB,
    hdshredder_report_path  VARCHAR(500),
    pdf_report_path         VARCHAR(500),
    pdf_generated_at        TIMESTAMPTZ,
    is_billable             BOOLEAN NOT NULL DEFAULT TRUE,
    billed_amount           DECIMAL(10,2),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN workshop_interventions.checks_json IS 'Ex: {"nettoyage":true,"thermal_paste":true,"ram_test":true,"hdd_scan":false}';

-- ============================================================
-- FORENSICS
-- ============================================================

CREATE TABLE forensics_cases (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id                   UUID NOT NULL REFERENCES clients(id),
    contract_id                 UUID NOT NULL REFERENCES contracts(id),  -- LM signée OBLIGATOIRE
    case_reference              VARCHAR(100) UNIQUE NOT NULL,
    title                       VARCHAR(300) NOT NULL,
    objectives                  TEXT NOT NULL,
    scope                       TEXT,
    status                      forensics_status NOT NULL DEFAULT 'ouvert',
    opened_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at                   TIMESTAMPTZ,
    final_report_path           VARCHAR(500),
    chain_of_custody_notes      TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN forensics_cases.contract_id IS 'OBLIGATOIRE — doit être de type lm_forensics et statut signé. Vérifié par trigger.';
COMMENT ON COLUMN forensics_cases.objectives IS 'Auto-extrait de la LM via OCR/IA au moment de la création du dossier';

-- ──────────────────────────────────────────────────────────

CREATE TABLE forensics_evidence (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id             UUID NOT NULL REFERENCES forensics_cases(id) ON DELETE CASCADE,
    evidence_number     VARCHAR(50) NOT NULL,
    description         TEXT NOT NULL,
    type                evidence_type NOT NULL,
    serial_number       VARCHAR(200),
    hash_md5            VARCHAR(32),
    hash_sha256         VARCHAR(64),
    acquisition_date    TIMESTAMPTZ NOT NULL,
    acquisition_tool    VARCHAR(100),
    storage_location    TEXT,
    nas_path            VARCHAR(500),
    notes               TEXT,
    UNIQUE(case_id, evidence_number)
);

-- ============================================================
-- DOCUMENTS & NAS
-- ============================================================

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id       UUID NOT NULL REFERENCES clients(id),
    site_id         UUID REFERENCES sites(id) ON DELETE SET NULL,
    document_type   document_type NOT NULL,
    reference       VARCHAR(100) UNIQUE NOT NULL,
    title           VARCHAR(300) NOT NULL,
    source_type     VARCHAR(50),  -- 'contract', 'intervention', 'forensics_case'
    source_id       UUID,         -- ID polymorphe vers l'entité source
    nas_path        VARCHAR(500) NOT NULL,
    file_size_bytes INTEGER,
    docuseal_id     VARCHAR(100),
    signed_at       TIMESTAMPTZ,
    signed_by_name  VARCHAR(200),
    signed_by_email VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- JOURNAL D'ACTIVITÉ CLIENT
-- ============================================================

CREATE TABLE activity_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    site_id         UUID REFERENCES sites(id) ON DELETE SET NULL,
    log_type        activity_log_type NOT NULL,
    title           VARCHAR(300) NOT NULL,
    description     TEXT,
    source_type     VARCHAR(50),
    source_id       UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE activity_log IS 'Fil chronologique par client. Alimenté automatiquement par triggers sur les autres tables.';

-- ============================================================
-- INTÉGRATIONS
-- ============================================================

CREATE TABLE falco_sync (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id               UUID NOT NULL REFERENCES clients(id),
    contract_id             UUID REFERENCES contracts(id) ON DELETE SET NULL,
    falco_invoice_id        VARCHAR(100) UNIQUE,
    invoice_number          VARCHAR(100),
    amount_htva             DECIMAL(10,2),
    amount_tvac             DECIMAL(10,2),
    status                  falco_status,
    invoice_date            DATE,
    due_date                DATE,
    peppol_delivery_status  VARCHAR(50),
    raw_payload             JSONB,
    synced_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────

CREATE TABLE docuseal_requests (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id             UUID NOT NULL REFERENCES documents(id),
    docuseal_submission_id  VARCHAR(100) UNIQUE,
    sent_to_email           VARCHAR(200) NOT NULL,
    sent_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signed_at               TIMESTAMPTZ,
    reminder_sent_at        TIMESTAMPTZ,
    status                  docuseal_status NOT NULL DEFAULT 'pending',
    webhook_payload         JSONB
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Clients
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_clients_name_trgm ON clients USING gin(name gin_trgm_ops);

-- Sites
CREATE INDEX idx_sites_client ON sites(client_id);

-- Contacts
CREATE INDEX idx_contacts_client ON contacts(client_id);

-- Contracts
CREATE INDEX idx_contracts_client ON contracts(client_id);
CREATE INDEX idx_contracts_end_date ON contracts(end_date) WHERE end_date IS NOT NULL;
CREATE INDEX idx_contracts_status ON contracts(status);

-- Time sessions
CREATE INDEX idx_sessions_client_date ON time_sessions(client_id, started_at DESC);
CREATE INDEX idx_sessions_contract ON time_sessions(contract_id);
CREATE INDEX idx_sessions_project ON time_sessions(project_id);
CREATE INDEX idx_sessions_active ON time_sessions(started_at) WHERE ended_at IS NULL;

-- Projects
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_client ON projects(client_id);
CREATE INDEX idx_projects_waiting ON projects(waiting_since) WHERE status = 'waiting_third_party';
CREATE INDEX idx_projects_kanban ON projects(kanban_column_id);

-- Equipment
CREATE INDEX idx_equipment_client ON equipment(client_id);
CREATE INDEX idx_equipment_serial ON equipment(serial_number);

-- Workshop
CREATE INDEX idx_workshop_equipment ON workshop_interventions(equipment_id);
CREATE INDEX idx_workshop_date ON workshop_interventions(intervention_date DESC);

-- Forensics
CREATE INDEX idx_forensics_client ON forensics_cases(client_id);
CREATE INDEX idx_forensics_status ON forensics_cases(status);

-- Documents
CREATE INDEX idx_documents_client_type ON documents(client_id, document_type);
CREATE INDEX idx_documents_source ON documents(source_type, source_id);

-- Activity log
CREATE INDEX idx_activity_client_date ON activity_log(client_id, created_at DESC);

-- Falco
CREATE INDEX idx_falco_client_date ON falco_sync(client_id, invoice_date DESC);

-- ============================================================
-- TRIGGERS — updated_at automatique
-- ============================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_clients
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_contracts
    BEFORE UPDATE ON contracts
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_projects
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_equipment
    BEFORE UPDATE ON equipment
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_forensics
    BEFORE UPDATE ON forensics_cases
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ============================================================
-- TRIGGER — Contrainte forensics : LM signée obligatoire
-- ============================================================

CREATE OR REPLACE FUNCTION check_forensics_contract()
RETURNS TRIGGER AS $$
DECLARE
    v_type   contract_type;
    v_status contract_status;
BEGIN
    SELECT contract_type, status
    INTO   v_type, v_status
    FROM   contracts
    WHERE  id = NEW.contract_id;

    IF v_type <> 'lm_forensics' THEN
        RAISE EXCEPTION 'Un dossier forensics nécessite un contrat de type lm_forensics (reçu: %)', v_type;
    END IF;

    IF v_status <> 'signé' AND v_status <> 'actif' THEN
        RAISE EXCEPTION 'La lettre de mission forensics doit être signée avant d''ouvrir un dossier (statut actuel: %)', v_status;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_forensics_lm
    BEFORE INSERT OR UPDATE ON forensics_cases
    FOR EACH ROW EXECUTE FUNCTION check_forensics_contract();

-- ============================================================
-- TRIGGER — Journal d'activité automatique
-- ============================================================

CREATE OR REPLACE FUNCTION log_contract_activity()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO activity_log(client_id, log_type, title, source_type, source_id)
        VALUES (NEW.client_id, 'contrat', 'Contrat créé : ' || NEW.reference, 'contract', NEW.id);
    ELSIF TG_OP = 'UPDATE' AND OLD.status <> NEW.status THEN
        INSERT INTO activity_log(client_id, log_type, title, source_type, source_id)
        VALUES (NEW.client_id, 'contrat', 'Contrat ' || NEW.reference || ' → ' || NEW.status, 'contract', NEW.id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_contracts
    AFTER INSERT OR UPDATE ON contracts
    FOR EACH ROW EXECUTE FUNCTION log_contract_activity();

-- ──────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION log_session_activity()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO activity_log(client_id, log_type, title, source_type, source_id)
        VALUES (NEW.client_id, 'session', 'Session : ' || NEW.activity, 'time_session', NEW.id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_sessions
    AFTER INSERT ON time_sessions
    FOR EACH ROW EXECUTE FUNCTION log_session_activity();

-- ============================================================
-- VUES — Rentabilité
-- ============================================================

CREATE OR REPLACE VIEW v_contract_profitability AS
SELECT
    c.id                                                    AS contract_id,
    c.reference,
    c.title,
    c.client_id,
    cl.name                                                 AS client_name,
    c.contract_type,
    c.billing_type,
    c.sold_budget,
    c.sold_hours,
    c.hourly_rate,
    c.monthly_amount,
    c.start_date,
    c.end_date,
    c.status,
    -- Heures prestées
    COALESCE(SUM(ts.duration_minutes), 0) / 60.0           AS hours_worked,
    -- Montant factorable
    COALESCE(SUM(CASE WHEN ts.is_billable THEN ts.amount ELSE 0 END), 0)     AS amount_billable,
    -- Montant inclus contrat
    COALESCE(SUM(CASE WHEN ts.is_included_in_contract THEN ts.amount ELSE 0 END), 0) AS amount_included,
    -- Dépassement
    COALESCE(SUM(CASE WHEN ts.is_billable AND NOT ts.is_included_in_contract THEN ts.amount ELSE 0 END), 0) AS amount_overage,
    -- Solde heures restantes
    CASE WHEN c.sold_hours IS NOT NULL
         THEN c.sold_hours - COALESCE(SUM(CASE WHEN ts.is_included_in_contract THEN ts.duration_minutes ELSE 0 END), 0) / 60.0
         ELSE NULL END                                      AS hours_remaining,
    -- P&L simplifié
    CASE WHEN c.sold_budget IS NOT NULL
         THEN c.sold_budget - COALESCE(SUM(CASE WHEN ts.is_included_in_contract THEN ts.amount ELSE 0 END), 0)
         ELSE NULL END                                      AS budget_remaining
FROM contracts c
JOIN clients cl ON cl.id = c.client_id
LEFT JOIN time_sessions ts ON ts.contract_id = c.id
GROUP BY c.id, cl.name;

COMMENT ON VIEW v_contract_profitability IS 'Vue rentabilité en temps réel par contrat. Base du dashboard.';

-- ──────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_projects_waiting AS
SELECT
    p.id,
    p.title,
    p.status,
    p.priority,
    p.waiting_for,
    p.waiting_since,
    p.auto_remind_days,
    NOW()::DATE - p.waiting_since                           AS days_waiting,
    CASE WHEN (NOW()::DATE - p.waiting_since) >= p.auto_remind_days
         THEN TRUE ELSE FALSE END                           AS needs_reminder,
    c.name                                                  AS client_name,
    kc.name                                                 AS kanban_column
FROM projects p
LEFT JOIN clients c ON c.id = p.client_id
LEFT JOIN kanban_columns kc ON kc.id = p.kanban_column_id
WHERE p.status = 'waiting_third_party'
  AND p.waiting_since IS NOT NULL
ORDER BY days_waiting DESC;

COMMENT ON VIEW v_projects_waiting IS 'Projets en attente tiers classés par ancienneté. Alimente les rappels automatiques.';

-- ──────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_contracts_renewal AS
SELECT
    c.id,
    c.reference,
    c.title,
    c.client_id,
    cl.name     AS client_name,
    c.end_date,
    c.end_date - NOW()::DATE    AS days_until_expiry,
    c.renewal_reminder_days,
    c.status
FROM contracts c
JOIN clients cl ON cl.id = c.client_id
WHERE c.end_date IS NOT NULL
  AND c.status = 'actif'
  AND c.end_date - NOW()::DATE <= c.renewal_reminder_days
ORDER BY days_until_expiry ASC;

COMMENT ON VIEW v_contracts_renewal IS 'Contrats à renouveler prochainement. Scannée par le job cron quotidien.';

-- ============================================================
-- DONNÉES INITIALES — Kanban columns
-- ============================================================

INSERT INTO kanban_columns (name, color, position, auto_escalate_days) VALUES
    ('En cours',            '#2196F3', 1, NULL),
    ('En attente tiers',    '#FF9800', 2, 5),
    ('À relancer',          '#F44336', 3, NULL),
    ('À facturer',          '#9C27B0', 4, NULL),
    ('Terminé',             '#4CAF50', 5, NULL);

-- ============================================================
-- DONNÉES INITIALES — Client Smartclick (interne)
-- ============================================================

INSERT INTO clients (name, status, client_type, vat_number, nas_path, notes)
VALUES (
    'Smartclick',
    'actif',
    'interne',
    'BE0746385009',
    '/homes/mathieu.pleitinx/Drive/workfolder/',
    'Entité interne Smartclick BV. Mathieu Pleitinx. Sessions R&D, admin, communication.'
);

-- ============================================================
-- FIN DU SCHÉMA
-- ============================================================
