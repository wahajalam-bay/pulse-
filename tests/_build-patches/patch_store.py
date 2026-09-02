"""Patch store.py: five new case routes, the registers, checklist templates, seeds."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\store.py"
src = open(PATH, encoding="utf-8").read()


def sub(old, new):
    global src
    assert old in src, "anchor missing: " + old[:70]
    src = src.replace(old, new, 1)


S = "\u00a7"      # section sign
DASH = "\u2014"   # em dash
MID = "\u00b7"    # middot

# ══════════════════════════════════════════════════════════════════════════
# 1 · five new routes. The engine does not change — only this table.
# ══════════════════════════════════════════════════════════════════════════
NEW_ROUTES = '''    "VE": {
        "label": "Value Engineering Proposal",
        "source": "Design Manual %(S)s8",
        "value_routed": True,
        "stage": 10,
        "lanes": [
            ("VE trigger %(D)s tender cost over budget", "PM", 0),
            ("Design option study", "Architecture", 7),
            ("Structure & MEP implication check", "Structure", 3),
            ("QS cost comparison per option", "PM", 5),
            ("CFT review and shortlist", "CFT", 3),
            ("Head ZD decision", "Head ZD", 2),
            ("Incorporated into tender drawings and BOQ", "Architecture", 7),
        ],
    },
    "NCR": {
        "label": "Non-Conformance Report",
        # The one route that starts OUTSIDE the department and ends inside it.
        # A site visit that finds non-compliance raises this automatically.
        "source": "Design Manual %(S)s16 (QA/QC coordination)",
        "value_routed": False,
        "stage": 13,
        "lanes": [
            ("Raised on site against approved IFC", "QA/QC", 0),
            ("Design assessment %(D)s deviation or acceptable", "Architecture", 2),
            ("Corrective design instruction issued", "Architecture", 3),
            ("Contractor rectification", "Contractor", 10),
            ("Joint re-inspection", "QA/QC", 2),
            ("Close-out and register update", "Architecture", 1),
        ],
    },
    "BOQ": {
        "label": "BOQ Endorsement",
        "source": "Design Manual %(S)s10",
        "value_routed": True,
        "stage": 10,
        "lanes": [
            ("QS take-off from the tender set", "PM", 10),
            ("Architecture quantity and specification check", "Architecture", 3),
            ("Structure quantity check", "Structure", 3),
            ("MEP quantity check", "MEP", 3),
            ("Head ZD endorsement", "Head ZD", 2),
            ("Released to Supply Chain for tender", "Supply Chain", 1),
        ],
    },
    "SMP": {
        "label": "Material Sample & Mock-up",
        "source": "Design Manual %(S)s12",
        "value_routed": False,
        "stage": 12,
        "lanes": [
            ("Sample submitted by contractor", "Contractor", 0),
            ("Design review against the approved mood board", "Architecture", 3),
            ("Mock-up unit construction", "Contractor", 14),
            ("Joint inspection with QA/QC", "QA/QC", 2),
            ("Approved into the material archive", "Architecture", 1),
        ],
    },
    "ABD": {
        "label": "As-Built & Closeout",
        "source": "Design Manual %(S)s18",
        "value_routed": False,
        "stage": 14,
        "lanes": [
            ("As-built markups from contractor", "Contractor", 0),
            ("Architecture as-built compilation", "Architecture", 15),
            ("Structure as-built compilation", "Structure", 10),
            ("MEP as-built compilation", "MEP", 10),
            ("Design verification against site", "Architecture", 5),
            ("QA/QC concurrence", "QA/QC", 3),
            ("Handover to PM and Property Management", "PM", 2),
        ],
    },
}
''' % {"S": S, "D": DASH}

sub('''            ("Design modification & BOQ revision", "Architecture", 10),
        ],
    },
}
''', '''            ("Design modification & BOQ revision", "Architecture", 10),
        ],
    },
''' + NEW_ROUTES)

# route stage default, so a case always knows which station it belongs to
sub('''INTERNAL_LANES = set(catalog.TEAMS)''',
    '''for _k, _v in ROUTES.items():
    _v.setdefault("stage", 13)

INTERNAL_LANES = set(catalog.TEAMS)''')

# ══════════════════════════════════════════════════════════════════════════
# 2 · one more recurring commitment
# ══════════════════════════════════════════════════════════════════════════
sub('''    ("material_archive", "Annual approved-material archive", "yearly", "department",
     "Design Manual %s12"),
]''' % S,
    '''    ("material_archive", "Annual approved-material archive", "yearly", "department",
     "Design Manual %(S)s12"),
    ("llr_review", "Quarterly lessons-learned review", "quarterly", "department",
     "Design Manual %(S)s7.6"),
]''' % {"S": S})

# ══════════════════════════════════════════════════════════════════════════
# 3 · the registers
# ══════════════════════════════════════════════════════════════════════════
NEW_TABLES = '''
-- ── the registers the Manual assumes exist ─────────────────────────────────

-- Manual %(S)s4.2's annexure is "(to be added)". So the department authors it once,
-- per stage, HERE, and every project's checklist is stamped from the template at
-- stage initiation. A lesson promoted out of the LLR lands in this table, which
-- is what makes "we learned something" change what the next project is checked
-- against. That loop is the whole point of %(S)s7.6.
CREATE TABLE IF NOT EXISTS checklist_templates (
  id INTEGER PRIMARY KEY, stage INTEGER NOT NULL, seq INTEGER,
  text TEXT NOT NULL, source TEXT, llr_id INTEGER,
  added_by TEXT, added_at TEXT, active INTEGER NOT NULL DEFAULT 1
);

-- Manual %(S)s7.6 — the Lessons Learned Register. PM %(S)s8.3 defines a competing
-- process and neither document references the other; that conflict is recorded
-- on the entry rather than silently resolved.
CREATE TABLE IF NOT EXISTS llr (
  id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
  stage INTEGER, discipline TEXT, category TEXT,
  title TEXT NOT NULL, detail TEXT, impact TEXT,
  raised_by TEXT, raised_at TEXT, source TEXT,
  origin_entity TEXT, origin_id INTEGER,        -- what the lesson came out of
  status TEXT NOT NULL DEFAULT 'open',          -- open|ruled|adopted|rejected
  ruling TEXT, ruled_by TEXT, ruled_at TEXT,
  promoted_stage INTEGER, promoted_at TEXT, template_id INTEGER
);

-- The honest answer to "file upload": a link register that attaches to ANY
-- entity, versioned, with who attached it. They already have a drive; what they
-- do not have is a record of which file is the current one and what it belongs to.
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
  project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL, kind TEXT, link TEXT, revision TEXT DEFAULT 'A',
  superseded_by INTEGER, added_by TEXT, added_at TEXT
);

-- Manual %(S)s7 and %(S)s17 — the authority file. Submission, the wait, the
-- observations, the conditions attached to an approval. The clock on the
-- Authority is the longest one in the department and nobody totals it today.
CREATE TABLE IF NOT EXISTS authority (
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  authority TEXT NOT NULL, kind TEXT NOT NULL,      -- submission|inspection|noc
  ref TEXT, title TEXT, stage INTEGER,
  submitted_on TEXT, submitted_by TEXT,
  status TEXT NOT NULL DEFAULT 'submitted',         -- submitted|observations|approved|rejected
  responded_on TEXT, observations TEXT, conditions TEXT, note TEXT,
  coordination_id INTEGER
);

-- Drawing revision history, and what was actually in each transmittal. A
-- transmittal with a COUNT on it is a number; a transmittal with the sheet list
-- and the revision of each sheet is the contractual fact %(S)s5 is talking about.
CREATE TABLE IF NOT EXISTS drawing_revs (
  id INTEGER PRIMARY KEY, drawing_id INTEGER NOT NULL REFERENCES drawings(id),
  revision TEXT NOT NULL, status TEXT, link TEXT, note TEXT,
  at TEXT, by_whom TEXT
);
CREATE TABLE IF NOT EXISTS transmittal_drawings (
  transmittal_id INTEGER NOT NULL REFERENCES transmittals(id),
  drawing_id INTEGER NOT NULL REFERENCES drawings(id),
  revision TEXT,
  PRIMARY KEY (transmittal_id, drawing_id)
);

CREATE INDEX IF NOT EXISTS ix_doc ON documents(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_llr_pr ON llr(project_id, status);
CREATE INDEX IF NOT EXISTS ix_auth ON authority(project_id, status);
CREATE INDEX IF NOT EXISTS ix_tpl ON checklist_templates(stage, active);
''' % {"S": S}

sub('''CREATE INDEX IF NOT EXISTS ix_note ON notes(entity, entity_id);''',
    NEW_TABLES + '''
CREATE INDEX IF NOT EXISTS ix_note ON notes(entity, entity_id);''')

# drawings gains a station and a supersede pointer
sub('''  number TEXT NOT NULL, title TEXT NOT NULL, discipline TEXT,
  revision TEXT NOT NULL DEFAULT 'A', status TEXT NOT NULL DEFAULT 'draft',
  link TEXT, created_at TEXT, created_by TEXT
);''',
    '''  number TEXT NOT NULL, title TEXT NOT NULL, discipline TEXT,
  revision TEXT NOT NULL DEFAULT 'A', status TEXT NOT NULL DEFAULT 'draft',
  link TEXT, stage INTEGER, superseded_by INTEGER,
  created_at TEXT, created_by TEXT
);''')

# products gains provenance
sub('''  variable INTEGER DEFAULT 0, gate INTEGER DEFAULT 0,
  tat_booklet TEXT, tat_manual TEXT
);''',
    '''  variable INTEGER DEFAULT 0, gate INTEGER DEFAULT 0,
  tat_booklet TEXT, tat_manual TEXT, source TEXT
);''')

sub('''        c.execute("INSERT INTO products(team,workflow,stage,seq,step,tat_days,lane,"
                  "is_external,maker,checker,rework,variable,gate,tat_booklet,tat_manual)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (r["team"], r["workflow"], r["stage"], r["seq"], r["step"],
                   r["tat_days"], r["lane"], int(r["is_external"]), int(r["maker"]),
                   int(r["checker"]), int(r["rework"]), int(r["variable"]),
                   int(r["gate"]), r["tat_booklet"], r["tat_manual"]))''',
    '''        c.execute("INSERT INTO products(team,workflow,stage,seq,step,tat_days,lane,"
                  "is_external,maker,checker,rework,variable,gate,tat_booklet,"
                  "tat_manual,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (r["team"], r["workflow"], r["stage"], r["seq"], r["step"],
                   r["tat_days"], r["lane"], int(r["is_external"]), int(r["maker"]),
                   int(r["checker"]), int(r["rework"]), int(r["variable"]),
                   int(r["gate"]), r["tat_booklet"], r["tat_manual"], r["source"]))''')

open(PATH, "w", encoding="utf-8").write(src)
print("store.py part 1 patched")
