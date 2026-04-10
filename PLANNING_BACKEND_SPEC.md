# SmartHub — Spec backend Planning

> **À destination du dev backend (autre session Claude Code)**.
> Cette spec décrit ce que le frontend SmartHub Workspace attend pour le module **Planning**.
>
> Le frontend est **déjà codé et fonctionnel** en mode "stub local JSON" — voir
> [smarthub/planning_api.py](smarthub/planning_api.py) et [smarthub/views/planning.py](smarthub/views/planning.py).
> Quand les endpoints décrits ici seront en place, il suffira de basculer la
> constante `PLANNING_BACKEND = True` dans `planning_api.py` pour passer en
> mode prod — aucun changement de vue requis.

---

## 0. Contexte fonctionnel

Le module **Planning** est l'organisation prévisionnelle du temps d'un technicien.
Il s'inscrit entre les **Dossiers** (objet métier — un projet client à traiter)
et le **Timetrack** (réalité — sessions de travail effectivement effectuées).

```
Dossier ─────► Planning ─────► Timetrack
(quoi)         (quand)         (réel)
```

**Règle fondamentale** : ne jamais mélanger prévu (Planning) et réel (Timetrack).
Le Timetrack reste la **source de vérité**. Le Planning n'est que de l'organisation.

**Flux principal** :
1. L'utilisateur planifie un créneau (créé manuellement ou depuis un dossier)
2. Le créneau apparaît dans la vue jour/semaine
3. À l'heure dite, l'utilisateur clique ▶ "Démarrer" → une **session timetrack**
   est créée et **liée au créneau** (`planning_slot_id`)
4. Quand la session se termine, le créneau passe à `done`, et l'on peut comparer
   `duration_min` (prévu) vs `actual_duration_min` (réel)
5. Si le créneau est passé sans avoir été démarré → statut `missed`
6. Si la session a duré significativement plus longtemps que prévu → `overrun`

---

## 1. Schéma base de données

### Table `planning_slots`

```sql
CREATE TABLE planning_slots (
    id                    UUID PRIMARY KEY,                    -- ou serial, au choix
    title                 VARCHAR(255) NOT NULL,
    client_id             INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    dossier_id            INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    -- contexte source du créneau (dossier, intervention, atelier, forensics, manuel)
    context_type          VARCHAR(32) NOT NULL DEFAULT 'manuel',
    context_id            INTEGER,
    context_ref           VARCHAR(255),

    start_at              TIMESTAMP NOT NULL,                  -- début prévu (timezone à préciser)
    duration_min          INTEGER NOT NULL,                    -- durée prévue en minutes

    status                VARCHAR(16) NOT NULL DEFAULT 'planned',
    -- planned | in_progress | done | missed | overrun

    notes                 TEXT,

    -- Récurrence : voir section 3
    recurrence_rule_id    INTEGER REFERENCES recurrence_rules(id) ON DELETE SET NULL,
    recurrence_parent_id  UUID REFERENCES planning_slots(id) ON DELETE CASCADE,
    -- recurrence_parent_id sert pour les EXCEPTIONS d'une série récurrente
    -- (un slot dérogatoire qui remplace une occurrence d'une série)

    -- Lien vers la session timetrack qui a été démarrée depuis ce créneau
    actual_session_id     INTEGER REFERENCES timetrack_sessions(id) ON DELETE SET NULL,
    actual_duration_min   INTEGER,                             -- snapshot quand session terminée

    created_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by            INTEGER REFERENCES users(id),

    INDEX idx_planning_start_at (start_at),
    INDEX idx_planning_client (client_id),
    INDEX idx_planning_dossier (dossier_id)
);
```

### Table `recurrence_rules`

```sql
CREATE TABLE recurrence_rules (
    id          SERIAL PRIMARY KEY,
    -- Format simple en phase 1 : "daily" | "weekly" | "monthly"
    -- Évolution future : RRULE iCal (RFC 5545) pour cas complexes
    rrule       VARCHAR(255) NOT NULL,
    -- Date de fin de la série (optionnel — null = infini)
    until_date  DATE,
    -- Pour les exceptions : liste de dates où la série ne s'applique pas
    -- (sérialisée en JSON, ex: ["2026-04-15", "2026-04-22"])
    exceptions  JSON,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Pourquoi un séparation `planning_slots` ↔ `recurrence_rules`** : un slot
récurrent est stocké **une seule fois** en base avec sa règle. Le serveur
matérialise les occurrences à la volée lors d'un `GET /planning/expanded`.
Ça évite l'explosion du nombre de lignes pour une règle "tous les lundis pendant 2 ans".

**Exceptions** : si l'utilisateur déplace ou supprime **une occurrence précise**
d'une série récurrente :
- **Suppression d'une occurrence** : ajouter la date à `recurrence_rules.exceptions`
- **Déplacement / modification d'une occurrence** : créer un nouveau slot avec
  `recurrence_parent_id` = id du slot série, et ajouter la date originale aux
  `exceptions` du parent

### Modification de la table `timetrack_sessions`

```sql
ALTER TABLE timetrack_sessions
    ADD COLUMN planning_slot_id UUID REFERENCES planning_slots(id) ON DELETE SET NULL;

CREATE INDEX idx_timetrack_planning_slot ON timetrack_sessions(planning_slot_id);
```

→ Permet la jointure prévu↔réel pour la vue Analyse.

---

## 2. Endpoints REST

Toutes les routes sont sous `/api/v1/planning/`. Authentification par header
`X-API-Key` (déjà en place).

### `GET /planning/expanded`

**Le seul endpoint que la vue jour/semaine appelle pour afficher des créneaux.**

Retourne tous les créneaux dans la fenêtre `[date_from, date_to]`, **récurrences expandées**.
Le serveur fait le travail de générer les occurrences à partir des règles.

**Query params**
- `date_from` (string ISO `YYYY-MM-DD`, requis)
- `date_to` (string ISO `YYYY-MM-DD`, requis)
- `client_id` (int, optionnel) — filtre
- `dossier_id` (int, optionnel) — filtre

**Réponse 200** — liste plate de slots, chaque occurrence étant un dict :

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Maintenance hebdo Client X",
    "client_id": 42,
    "client_name": "Client X SA",
    "dossier_id": 17,
    "dossier_title": "Maintenance 2026",
    "context_type": "dossier",
    "context_id": 17,
    "context_ref": "Maintenance 2026",
    "start_at": "2026-04-13T09:00:00",
    "duration_min": 60,
    "status": "planned",
    "notes": "Vérifier sauvegardes + MAJ système",
    "recurrence_rule": "weekly",
    "recurrence_parent_id": null,
    "actual_session_id": null,
    "actual_duration_min": null,
    "_is_occurrence": true,
    "_occurrence_of": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-04-01T10:00:00",
    "updated_at": "2026-04-01T10:00:00"
  }
]
```

**Champs `_is_occurrence` et `_occurrence_of`** : permettent au frontend de
savoir qu'un slot affiché est une occurrence virtuelle d'une série, pas un slot
"physique" en BDD. Quand l'utilisateur clique pour éditer une occurrence, le
front renvoie l'`_occurrence_of` au lieu de l'`id` virtuel.

`status` est calculé côté backend en fonction de l'heure courante et de la
session liée (voir section 4).

### `GET /planning/{id}`

Détail d'un créneau (slot physique, pas occurrence).

**Réponse 200** : un seul dict, mêmes champs que ci-dessus + champ optionnel
`actual_session` (objet timetrack_session complet) si le créneau a été démarré.

### `POST /planning/`

Crée un nouveau créneau.

**Body**
```json
{
  "title": "Intervention chez Client Y",
  "client_id": 42,
  "dossier_id": 17,
  "context_type": "dossier",
  "context_id": 17,
  "context_ref": "Migration Office 365",
  "start_at": "2026-04-15T14:00:00",
  "duration_min": 120,
  "notes": "Apporter le NAS de test",
  "recurrence_rule": ""
}
```

`recurrence_rule` accepte : `""` (pas de récurrence), `"daily"`, `"weekly"`, `"monthly"`.

**Réponse 201** : le slot créé avec son `id`, `status: "planned"`, timestamps.

### `PATCH /planning/{id}`

Modifie un créneau existant. Body : tous les champs optionnels (mêmes que POST).

**Cas spécial — modification d'une occurrence d'une série récurrente** :
- Si `id` correspond à un slot avec `recurrence_rule_id != null`, et que le
  client envoie un `start_at` différent de l'original → c'est une **exception**.
  Le backend doit :
  1. Créer un nouveau slot avec `recurrence_parent_id = id`
  2. Ajouter la date originale aux `recurrence_rules.exceptions` du parent
  3. Renvoyer le nouveau slot

### `DELETE /planning/{id}`

Supprime un créneau.

**Cas spécial — suppression d'une occurrence d'une série** :
- Param query `?occurrence_date=2026-04-15` → ne supprime pas le slot série,
  mais ajoute cette date aux `exceptions` de la règle de récurrence.
- Sans param → supprime tout le slot (et toutes ses occurrences).

### `POST /planning/{id}/start`

Démarre une session timetrack depuis ce créneau.

**Body** : optionnel, mêmes champs que `/timetrack/start` (peut être vide pour
hériter du contexte du créneau).

**Logique backend** :
1. Vérifier qu'il n'y a pas déjà une session timetrack active (sinon 409)
2. Créer une `timetrack_session` avec :
   - `client_id`, `activity`, `context_type`, `context_id` hérités du slot
   - `planning_slot_id` = id du slot
   - `started_at` = NOW()
3. Mettre à jour le slot : `status = "in_progress"`
4. Renvoyer la session créée (mêmes champs que `/timetrack/start`)

### Hook côté `/timetrack/stop`

Quand une session se termine et que `planning_slot_id` est rempli, le backend doit :
1. Calculer `actual_duration_min = (ended_at - started_at) / 60`
2. Mettre à jour le slot lié :
   - `actual_session_id` = id de la session
   - `actual_duration_min` = calculé
   - `status` = `"overrun"` si `actual > duration_min * 1.15`, sinon `"done"`

### `GET /planning/analytics` (Phase C — vue Analyse)

Agrégation prévu vs réel sur une période.

**Query params** : `date_from`, `date_to`, `client_id` (optionnel), `dossier_id` (optionnel)

**Réponse 200**
```json
{
  "totals": {
    "planned_min": 2400,
    "actual_min": 2680,
    "deviation_pct": 11.7,
    "slots_total": 42,
    "slots_done": 38,
    "slots_missed": 3,
    "slots_overrun": 5
  },
  "by_client": [
    {
      "client_id": 42, "client_name": "Client X",
      "planned_min": 600, "actual_min": 720, "deviation_pct": 20.0
    }
  ],
  "by_dossier": [...]
}
```

---

## 3. Logique de matérialisation des récurrences

Le serveur reçoit `GET /planning/expanded?date_from=2026-04-13&date_to=2026-04-19`.

**Algorithme**
```python
def expand_slots(date_from, date_to, ...):
    result = []
    for slot in db.query("SELECT * FROM planning_slots WHERE deleted=false"):
        if slot.recurrence_rule_id is None:
            # Slot ponctuel : on l'inclut s'il tombe dans la fenêtre
            if date_from <= slot.start_at.date() <= date_to:
                result.append(slot.to_dict())
        else:
            # Slot récurrent : on génère les occurrences
            rule = db.get_rule(slot.recurrence_rule_id)
            for occ_date in iter_recurrence(slot.start_at, rule, date_from, date_to):
                if occ_date in rule.exceptions:
                    continue  # exception ponctuelle
                # Vérifier qu'il n'y a pas un slot enfant qui remplace cette occurrence
                child = db.find_child(slot.id, occ_date)
                if child:
                    continue  # le slot enfant sera ajouté par sa propre itération
                occ = slot.to_dict()
                occ['start_at'] = occ_date
                occ['_is_occurrence'] = True
                occ['_occurrence_of'] = slot.id
                result.append(occ)
    return sorted(result, key=lambda x: x['start_at'])
```

**Pour `iter_recurrence`** : commencez simple (daily/weekly/monthly).
Plus tard, vous pourrez utiliser la lib Python `dateutil.rrule` pour passer
au format iCal RFC 5545 complet.

---

## 4. Calcul du `status` côté backend

Le backend doit calculer le `status` à chaque GET (ou stocker + mettre à jour
via job de fond, au choix). Logique :

```python
def compute_status(slot, now=None):
    now = now or datetime.now()
    # Si déjà terminé en BDD
    if slot.status == 'done' or slot.actual_session_id is not None:
        if slot.actual_duration_min and slot.actual_duration_min > slot.duration_min * 1.15:
            return 'overrun'
        return 'done'
    end = slot.start_at + timedelta(minutes=slot.duration_min)
    if now < slot.start_at:
        return 'planned'
    if slot.start_at <= now <= end:
        return 'in_progress'
    return 'missed'
```

---

## 5. Permissions & multi-utilisateurs (si applicable)

À voir avec l'archi existante. Pour l'instant single-user, mais penser à
ajouter `created_by` sur les slots si évolution multi-tenant.

---

## 6. Tests à prévoir côté backend

- Créer un slot ponctuel → vérifier `GET /planning/expanded` le retourne sur la bonne fenêtre
- Créer un slot weekly → vérifier que l'expansion génère N occurrences sur 1 mois
- Ajouter une exception → vérifier qu'elle est exclue de l'expansion
- Modifier une occurrence (créer un slot enfant) → vérifier qu'elle apparaît une seule fois (pas en double)
- Supprimer une occurrence sans toucher la série
- Démarrer une session depuis un slot → vérifier `planning_slot_id` rempli + status `in_progress`
- Stop session → vérifier slot passe à `done` avec `actual_duration_min`
- Stop session après dépassement → vérifier statut `overrun`
- Slot dont le `start_at` est dans le passé sans session liée → statut `missed`
- 2 sessions actives → second `POST /planning/{id}/start` doit retourner 409

---

## 7. Migration & déploiement

1. Créer les 2 nouvelles tables (`planning_slots`, `recurrence_rules`)
2. `ALTER TABLE timetrack_sessions ADD planning_slot_id`
3. Mettre en place les endpoints (priorité au `GET /planning/expanded`, `POST`,
   `PATCH`, `DELETE` → suffisant pour 90% de l'usage)
4. Ajouter le hook sur `/timetrack/stop`
5. Endpoint `/planning/{id}/start` (peut être différé si besoin — le frontend
   peut aussi appeler `/timetrack/start` directement avec `planning_slot_id`
   dans le payload, à toi de voir)
6. Côté frontend SmartHub : passer `planning_api.PLANNING_BACKEND = True`
7. Tester les flux complets dans les 2 vues

---

## 8. Phase C — Google Calendar sync (plus tard)

**Sens unique : SmartHub → Google Calendar.**
Surtout pas bidirectionnel au début (compliqué à arbitrer).

**Schéma supplémentaire**
```sql
ALTER TABLE planning_slots ADD COLUMN gcal_event_id VARCHAR(255);
ALTER TABLE planning_slots ADD COLUMN gcal_synced_at TIMESTAMP;
```

**Worker backend**
- Stocker les OAuth refresh tokens Google côté serveur (table `users` ou `integrations`)
- Worker périodique (ou trigger sur INSERT/UPDATE/DELETE de `planning_slots`)
- Push vers `https://www.googleapis.com/calendar/v3/calendars/primary/events`
- Stocker `gcal_event_id` pour pouvoir mettre à jour / supprimer ensuite

**Endpoint frontend**
- `POST /planning/sync-google` : déclencher manuellement une resync complète
- `GET /planning/sync-status` : afficher dans Paramètres l'état de la sync

---

## Résumé des endpoints à implémenter (priorité décroissante)

| Priorité | Endpoint | Notes |
|---|---|---|
| 🔴 P1 | `GET /planning/expanded` | Le plus critique — alimente toute la vue |
| 🔴 P1 | `POST /planning/` | Création |
| 🔴 P1 | `PATCH /planning/{id}` | Modification |
| 🔴 P1 | `DELETE /planning/{id}` | Suppression |
| 🟠 P2 | Hook sur `/timetrack/stop` | Met à jour `actual_duration_min` + status |
| 🟠 P2 | `POST /planning/{id}/start` | Ou ajouter `planning_slot_id` à `/timetrack/start` |
| 🟡 P3 | `GET /planning/{id}` | Pour le détail (utile mais pas bloquant) |
| 🟡 P3 | Logique exceptions récurrence | Quand l'utilisateur déplace/supprime une occurrence |
| 🟢 P4 | `GET /planning/analytics` | Vue Analyse (Phase suivante) |
| 🟢 P4 | Sync Google Calendar | Phase encore après |

**Quand P1 + P2 sont en place, le frontend bascule en mode prod et tout fonctionne.**
P3 et P4 sont des améliorations qu'on peut ajouter au fil de l'eau.

---

## Fichiers frontend à connaître

- [smarthub/planning_api.py](smarthub/planning_api.py) — couche d'abstraction, contient le flag `PLANNING_BACKEND`
- [smarthub/views/planning.py](smarthub/views/planning.py) — vue UI complète (jour/semaine, dialogs)
- [smarthub/views/projects.py](smarthub/views/projects.py) — vue Dossiers (ex-Projets) qui appelle `open_planning_with_payload`
- [workspace.py](workspace.py) — `MainWindow.open_planning_with_payload()` est le pont depuis Dossiers vers Planning
