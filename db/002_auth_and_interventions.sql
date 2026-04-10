-- ============================================================
-- SMARTCLICK ERP — Migration 002
-- Auth (API keys + users) + Interventions on-site
-- ============================================================

-- ============================================================
-- AUTH — Utilisateurs et clés API
-- ============================================================

CREATE TYPE user_role AS ENUM ('owner', 'technicien');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    email           VARCHAR(200) UNIQUE NOT NULL,
    role            user_role NOT NULL DEFAULT 'technicien',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE users IS 'Utilisateurs SmartHub. Pour l''instant : Mathieu (owner) + futurs techniciens.';

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash        VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 de la clé brute
    name            VARCHAR(100) NOT NULL,         -- ex: "Desktop Mathieu", "Timer Overlay"
    last_used_at    TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE api_keys IS 'Clés API par appareil/usage. La clé brute n''est jamais stockée — seulement son hash SHA256.';

CREATE INDEX idx_api_keys_hash   ON api_keys(key_hash) WHERE is_active = TRUE;
CREATE INDEX idx_api_keys_user   ON api_keys(user_id);

-- Trigger updated_at sur users
CREATE TRIGGER set_updated_at_users
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ============================================================
-- INTERVENTIONS ON-SITE
-- (distinct de workshop_interventions qui est pour l'atelier)
-- ============================================================

CREATE TYPE onsite_status AS ENUM ('planifiée', 'en_cours', 'terminée', 'annulée');

CREATE TABLE on_site_interventions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id       UUID NOT NULL REFERENCES clients(id),
    site_id         UUID REFERENCES sites(id) ON DELETE SET NULL,
    contract_id     UUID REFERENCES contracts(id) ON DELETE SET NULL,
    session_id      UUID REFERENCES time_sessions(id) ON DELETE SET NULL,
    -- Infos intervention
    titre           VARCHAR(300) NOT NULL,
    description     TEXT,
    status          onsite_status NOT NULL DEFAULT 'planifiée',
    -- Planification
    planned_at      TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    -- Durée calculée en minutes
    elapsed_min     INTEGER GENERATED ALWAYS AS (
                        CASE WHEN ended_at IS NOT NULL AND started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (ended_at - started_at))::INTEGER / 60
                        ELSE NULL END
                    ) STORED,
    -- Reporting
    technicien      VARCHAR(100) NOT NULL DEFAULT 'Mathieu Pleitinx',
    notes_depart    TEXT,   -- Contexte avant intervention
    notes_fin       TEXT,   -- Rapport de fin
    materiel_utilise TEXT,
    is_billable     BOOLEAN NOT NULL DEFAULT TRUE,
    pdf_report_path VARCHAR(500),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE on_site_interventions IS 'Interventions terrain (client-site). Distinct de l''atelier.';

CREATE INDEX idx_onsite_client  ON on_site_interventions(client_id);
CREATE INDEX idx_onsite_status  ON on_site_interventions(status);
CREATE INDEX idx_onsite_date    ON on_site_interventions(planned_at DESC);

CREATE TRIGGER set_updated_at_onsite
    BEFORE UPDATE ON on_site_interventions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- Log automatique des interventions on-site
CREATE OR REPLACE FUNCTION log_onsite_activity()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO activity_log(client_id, site_id, log_type, title, source_type, source_id)
        VALUES (NEW.client_id, NEW.site_id, 'intervention',
                'Intervention : ' || NEW.titre, 'on_site_intervention', NEW.id);
    ELSIF TG_OP = 'UPDATE' AND OLD.status <> NEW.status AND NEW.status = 'terminée' THEN
        INSERT INTO activity_log(client_id, site_id, log_type, title, source_type, source_id)
        VALUES (NEW.client_id, NEW.site_id, 'intervention',
                'Intervention terminée : ' || NEW.titre, 'on_site_intervention', NEW.id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_onsite
    AFTER INSERT OR UPDATE ON on_site_interventions
    FOR EACH ROW EXECUTE FUNCTION log_onsite_activity();

-- ============================================================
-- AS-BUILT (structure de base — module futur)
-- ============================================================

CREATE TYPE asbuilt_type AS ENUM ('reseau', 'serveur', 'poste', 'logiciel', 'autre');

CREATE TABLE as_built (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id       UUID NOT NULL REFERENCES clients(id),
    site_id         UUID REFERENCES sites(id) ON DELETE SET NULL,
    contract_id     UUID REFERENCES contracts(id) ON DELETE SET NULL,
    type            asbuilt_type NOT NULL DEFAULT 'reseau',
    title           VARCHAR(300) NOT NULL,
    version         VARCHAR(20) NOT NULL DEFAULT '1.0',
    content_json    JSONB NOT NULL DEFAULT '{}',  -- Structure modulaire
    nas_path        VARCHAR(500),
    pdf_path        VARCHAR(500),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE as_built IS 'Documentation technique as-built par client/site. Généré depuis SmartHub, stocké sur NAS.';
COMMENT ON COLUMN as_built.content_json IS 'Contenu structuré: {"topology": {...}, "devices": [...], "vlans": [...], "credentials_ref": "NAS/..."}';

CREATE INDEX idx_asbuilt_client ON as_built(client_id);

CREATE TRIGGER set_updated_at_asbuilt
    BEFORE UPDATE ON as_built
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ============================================================
-- DONNÉES INITIALES — Utilisateur owner
-- ============================================================

-- Mathieu = owner par défaut
-- La clé API sera générée au premier démarrage de l'API
INSERT INTO users (name, email, role)
VALUES ('Mathieu Pleitinx', 'mathieu.pleitinx@smartclick.be', 'owner');
