-- ============================================================
-- SMARTCLICK ERP — Migration 003
-- Module Planning : créneaux prévisionnels + récurrences
-- + lien vers timetrack_sessions (jointure prévu/réel)
-- ============================================================
--
-- NOTE conventions ID :
-- La spec PLANNING_BACKEND_SPEC.md décrit les FK clients/projects
-- en INTEGER. Le schéma réel SmartHub utilise UUID partout, donc
-- on aligne sur UUID pour rester cohérent avec l'existant.
-- ============================================================

CREATE TYPE planning_status AS ENUM ('planned', 'in_progress', 'done', 'missed', 'overrun');

-- ── Règles de récurrence ──────────────────────────────────
CREATE TABLE recurrence_rules (
    id          SERIAL PRIMARY KEY,
    -- "daily" | "weekly" | "monthly" en phase 1
    -- évolution future : RRULE iCal RFC 5545
    rrule       VARCHAR(255) NOT NULL,
    until_date  DATE,
    -- Liste de dates "YYYY-MM-DD" où la série ne s'applique pas
    exceptions  JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE recurrence_rules IS
    'Règles de récurrence pour planning_slots. Les occurrences sont matérialisées à la volée par /planning/expanded.';
COMMENT ON COLUMN recurrence_rules.exceptions IS
    'Dates "YYYY-MM-DD" exclues de la série (suppression ou déplacement d''une occurrence).';

-- ── Créneaux planifiés ────────────────────────────────────
CREATE TABLE planning_slots (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title                 VARCHAR(255) NOT NULL,

    client_id             UUID REFERENCES clients(id)  ON DELETE SET NULL,
    dossier_id            UUID REFERENCES projects(id) ON DELETE SET NULL,

    -- Source du créneau (dossier, intervention, atelier, forensics, manuel)
    context_type          VARCHAR(32) NOT NULL DEFAULT 'manuel',
    context_id            UUID,
    context_ref           VARCHAR(255),

    start_at              TIMESTAMPTZ NOT NULL,
    duration_min          INTEGER NOT NULL CHECK (duration_min > 0),

    status                planning_status NOT NULL DEFAULT 'planned',
    notes                 TEXT,

    -- Récurrence
    recurrence_rule_id    INTEGER REFERENCES recurrence_rules(id) ON DELETE SET NULL,
    -- Pointer un slot "parent" pour les exceptions de série
    -- (occurrence déplacée → nouveau slot enfant qui remplace celle du parent)
    recurrence_parent_id  UUID REFERENCES planning_slots(id) ON DELETE CASCADE,

    -- Lien prévu↔réel
    actual_session_id     UUID REFERENCES time_sessions(id) ON DELETE SET NULL,
    actual_duration_min   INTEGER,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by            UUID REFERENCES users(id) ON DELETE SET NULL
);

COMMENT ON TABLE planning_slots IS
    'Créneaux prévisionnels du planning. Un slot récurrent n''a qu''une ligne — les occurrences sont expansées à la volée.';

CREATE INDEX idx_planning_start_at ON planning_slots(start_at);
CREATE INDEX idx_planning_client   ON planning_slots(client_id);
CREATE INDEX idx_planning_dossier  ON planning_slots(dossier_id);
CREATE INDEX idx_planning_parent   ON planning_slots(recurrence_parent_id);
CREATE INDEX idx_planning_rule     ON planning_slots(recurrence_rule_id);

CREATE TRIGGER set_updated_at_planning
    BEFORE UPDATE ON planning_slots
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ── Google Calendar sync ──────────────────────────────────
ALTER TABLE planning_slots
    ADD COLUMN IF NOT EXISTS gcal_event_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_planning_gcal
    ON planning_slots(gcal_event_id);

-- ── Lien depuis time_sessions ─────────────────────────────
ALTER TABLE time_sessions
    ADD COLUMN IF NOT EXISTS planning_slot_id UUID
        REFERENCES planning_slots(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_timetrack_planning_slot
    ON time_sessions(planning_slot_id);
