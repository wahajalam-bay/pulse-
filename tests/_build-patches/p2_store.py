"""Backlog §36 (definitions as settings), #5/#6 priority, #1-4 collaboration,
#7-10 findings, #15-17 lessons root cause, #27-31 the time model."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\store.py"
src = open(PATH, encoding="utf-8").read()
S = "\u00a7"
D = "\u2014"
RA = "\u2192"


def sub(old, new):
    global src
    assert old in src, "anchor: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1 · §36 — the definitions Haroon said not to hard-code
# ══════════════════════════════════════════════════════════════════════════
DEFS = '''

# ── the definitions that are NOT allowed to be constants ─────────────────────
# Haroon's review, %(S)s36: "The following points should not be hard-coded until the
# business definition is confirmed." Eight of them. So they live in the `settings`
# table, every calculation reads them, and each one ships carrying the QUESTION it
# is waiting on and `confirmed=0`. The screen says UNCONFIRMED until someone
# answers, which is the honest state — a number nobody has agreed is worse than a
# blank, because a blank does not get quoted in a board pack.
#
# (key, value, kind, section, label, question / note, options, doc_ref)
DEFINITIONS = [
 ("ack.window_value", "24", "int", "Acknowledgement",
  "Acknowledgement window",
  "How long a receiving team has to acknowledge a cross-team request.",
  "", "%(S)s3 / %(S)s36 A"),
 ("ack.window_unit", "calendar_hours", "choice", "Acknowledgement",
  "The window is measured in",
  "THE OPEN QUESTION: does 24 hours mean calendar hours, business hours, or "
  "working days? A request raised 4pm Friday is due 4pm Saturday on the first "
  "reading and Monday afternoon on the third. Nothing else in the system can be "
  "trusted until this is answered.",
  "calendar_hours|business_hours|working_days", "%(S)s36 A"),
 ("ack.business_day_start", "9", "int", "Acknowledgement",
  "Business day starts (hour)", "Only used if the window is business hours.",
  "", "%(S)s36 A"),
 ("ack.business_day_end", "18", "int", "Acknowledgement",
  "Business day ends (hour)", "Only used if the window is business hours.",
  "", "%(S)s36 A"),

 ("priority.levels", "Critical|High|Medium|Low", "list", "Priority",
  "Priority levels",
  "THE OPEN QUESTION: is this the right ladder? The review asked for configurable "
  "levels and gave this as an example, not a decision.",
  "", "%(S)s3 / %(S)s36 B"),
 ("priority.default", "Medium", "choice", "Priority",
  "Default priority for a new item", "",
  "Critical|High|Medium|Low", "%(S)s36 B"),
 ("priority.change_needs_reason", "1", "bool", "Priority",
  "Changing priority requires a stated reason",
  "The review asked for the historical record to survive a priority change. A "
  "change with no reason cannot be reviewed later.",
  "", "%(S)s3"),
 ("priority.who_can_change", "1", "int", "Priority",
  "Minimum tier that may change priority",
  "0 head %(RA)s 1 senior manager %(RA)s 2 lead %(RA)s 3 member.",
  "", "%(S)s36 B"),

 ("scope.sla_applies_to", "External commitments %(D)s dates promised outside the department",
  "text", "SLA vs TAT",
  "SLA means", "THE OPEN QUESTION (%(S)s36 C): establish exactly where SLA applies.",
  "", "%(S)s36 C"),
 ("scope.tat_applies_to", "Internal turnaround %(D)s how long a team takes on its own step",
  "text", "SLA vs TAT",
  "TAT means",
  "%(S)s21 of the review: cross-team task timelines are TAT, not SLA. The wording is "
  "now TAT everywhere it describes a turnaround.",
  "", "%(S)s36 C / %(S)s21"),

 ("time.inprogress_definition",
  "Time the responsible team was actively working on the item",
  "text", "Time model", "In Progress means",
  "%(S)s27 of the review.", "", "%(S)s36 D"),
 ("time.wait_definition",
  "Time the item was waiting on another person, team or action",
  "text", "Time model", "Wait means", "%(S)s27 of the review.", "", "%(S)s36 D"),
 ("time.hold_definition",
  "Time progress was intentionally or externally blocked",
  "text", "Time model", "Hold / Blocking means", "%(S)s27 of the review.", "",
  "%(S)s36 D"),
 ("time.wait_counts_as_inprogress", "0", "bool", "Time model",
  "Count Wait as part of In Progress",
  "THE OPEN QUESTION, raised directly in %(S)s27: it was suggested Wait may need to "
  "count inside In Progress for some reporting. Off means SLA is judged on active "
  "execution only %(D)s the current behaviour. Turning it on changes every variance "
  "figure in the system, which is why it is a switch and not an opinion.",
  "", "%(S)s36 D"),
 ("time.own_time_means", "active_execution", "choice", "Time model",
  "Own Time represents",
  "THE OPEN QUESTION (%(S)s28 / %(S)s36 E): is Own Time active execution, or does it "
  "include time the item sat with us untouched? If the second, it overlaps Hold and "
  "the two must not be summed.",
  "active_execution|all_time_held_by_us", "%(S)s36 E"),

 ("delivery.exclude_md_approval", "1", "bool", "Delivery cycle",
  "Exclude MD approval time from Delivery Time",
  "%(S)s30 of the review asked for this specifically. Default on.",
  "", "%(S)s33 / %(S)s36 F"),
 ("delivery.exclude_director_approval", "0", "bool", "Delivery cycle",
  "Exclude Director approval time from Delivery Time",
  "%(S)s29: a Director's sign-off timing currently lands on the senior manager's "
  "delivery figure. Unresolved %(D)s the review did not say to exclude it, only that "
  "the calculation must distinguish it.",
  "", "%(S)s36 F"),
 ("delivery.exclude_external", "1", "bool", "Delivery cycle",
  "Exclude external dependency time from Delivery Time",
  "Time held by the Authority, a contractor or a vendor.", "", "%(S)s36 F"),
 ("delivery.exclude_hold", "1", "bool", "Delivery cycle",
  "Exclude Hold / blocking time from Delivery Time", "", "", "%(S)s36 F"),

 ("baseline.source", "booklet", "choice", "SLA baseline",
  "Which document is the TAT baseline",
  "THE BLOCKING ONE (%(S)s22 / %(S)s26 / %(S)s36 G). Booklet Vol.1 and Guidelines Manual "
  "%(S)s4.0 disagree on six of the ten architecture stages, and the Manual disagrees "
  "with its own flowcharts on three. Ahmed rules. Until then this records the "
  "working assumption and the Workflow Catalogue rail shows every conflict. "
  "NOTE: changing this does not retrospectively re-baseline existing tasks %(D)s "
  "planned dates are stamped when a stage is initiated.",
  "booklet|manual", "%(S)s26 / %(S)s36 G"),

 ("escalation.levels", "Line Manager|Senior Manager|Department Head", "list",
  "Escalation", "Escalation ladder",
  "%(S)s16 of the review: collaboration cannot be limited to junior staff. This is "
  "who a missed acknowledgement climbs to, in order.",
  "", "%(S)s4 / %(S)s16"),
 ("escalation.on_ack_missed", "1", "bool", "Escalation",
  "Escalate automatically when the acknowledgement window is missed", "", "",
  "%(S)s4"),
 ("escalation.on_tat_breach", "1", "bool", "Escalation",
  "Escalate automatically when TAT is breached", "", "", "%(S)s4"),

 ("lessons.notify_head", "1", "bool", "Lessons learned",
  "A raised lesson is visible to the department head",
  "%(S)s11 of the review: Lesson %(RA)s Head visibility %(RA)s Audit visibility %(RA)s repository.",
  "", "%(S)s15"),
 ("lessons.notify_audit", "1", "bool", "Lessons learned",
  "A raised lesson is visible to Audit / IA",
  "Audit is a named control in all four manuals.", "", "%(S)s15"),
 ("lessons.audit_from_status", "ruled", "choice", "Lessons learned",
  "Audit sees a lesson from this status onward",
  "Whether Audit sees raw lessons or only ruled ones is a governance choice.",
  "open|ruled|adopted", "%(S)s15"),
]
''' % {"S": S, "D": D, "RA": RA}

sub("\n\nSCHEMA = \"\"\"", DEFS + "\n\nSCHEMA = \"\"\"")


# ══════════════════════════════════════════════════════════════════════════
# 2 · schema
# ══════════════════════════════════════════════════════════════════════════
# priority + collaboration on cases
sub('''CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY, ref TEXT UNIQUE,
  type TEXT NOT NULL, project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL, value_pkr REAL,
  position INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',          -- open|approved|rejected|withdrawn
  raised_by TEXT, raised_at TEXT, closed_at TEXT, note TEXT
);''',
'''CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY, ref TEXT UNIQUE,
  type TEXT NOT NULL, project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL, value_pkr REAL,
  position INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',          -- open|approved|rejected|withdrawn
  raised_by TEXT, raised_at TEXT, closed_at TEXT, note TEXT,

  -- Backlog #5/#6: priority is business importance. TAT is time. They are NOT
  -- the same field and one must never stand in for the other.
  priority TEXT NOT NULL DEFAULT 'Medium',
  tat_days INTEGER, due_on TEXT,

  -- Backlog #1/#2/#3/#4/#20: a case can be raised AT another team, has to be
  -- acknowledged, can be talked about without being closed, and escalates when
  -- the acknowledgement is missed.
  from_team TEXT, to_team TEXT, to_person_id INTEGER REFERENCES people(id),
  line_manager_id INTEGER REFERENCES people(id),
  ack_due_at TEXT, acknowledged_at TEXT, ack_by TEXT,
  escalation_level INTEGER NOT NULL DEFAULT 0,
  escalated_at TEXT, escalated_to TEXT, escalated_by TEXT, escalation_reason TEXT,

  -- Backlog #24: the hook for PM/Asana. Nothing syncs yet, but an item can be
  -- pointed at its counterpart so the link is not recreated by hand later.
  external_system TEXT, external_ref TEXT, external_url TEXT,
  origin_entity TEXT, origin_id INTEGER            -- what produced this case
);

-- Backlog #2: the back-and-forth. "The receiving team should be able to provide
-- updates without closing the case." An update is therefore a message, not a
-- status change, and the thread is part of the case timeline.
CREATE TABLE IF NOT EXISTS case_messages (
  id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id),
  kind TEXT NOT NULL DEFAULT 'update',   -- update|question|answer|ack|escalation|decision
  body TEXT NOT NULL, who TEXT, who_team TEXT, who_tier INTEGER,
  at TEXT NOT NULL, seen_by TEXT
);

-- Backlog #5: priority changes during the lifecycle and the history survives.
CREATE TABLE IF NOT EXISTS priority_log (
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
  old_priority TEXT, new_priority TEXT NOT NULL, reason TEXT,
  who TEXT, who_tier INTEGER, at TEXT NOT NULL
);

-- §36: the business definitions, editable, each carrying its own question.
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY, value TEXT, kind TEXT, section TEXT,
  label TEXT, note TEXT, options TEXT, doc_ref TEXT,
  confirmed INTEGER NOT NULL DEFAULT 0,
  confirmed_by TEXT, confirmed_at TEXT, updated_at TEXT, updated_by TEXT
);

-- Backlog #18: the organisation, so a lesson or a finding can belong to Legal.
CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1, head_person_id INTEGER REFERENCES people(id)
);

-- Backlog #7/#8/#9/#10: one visit, many findings. The review was explicit —
-- "a visit should not become one large unstructured record." Each finding is
-- independently categorised, evidenced, owned, timed and resolvable, and each
-- can become an RFI or a task without the visit itself moving.
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY,
  visit_id INTEGER REFERENCES site_visits(id),
  project_id INTEGER NOT NULL REFERENCES projects(id),
  seq INTEGER, category TEXT, title TEXT NOT NULL,
  description TEXT, location TEXT,
  responsible_team TEXT, person_id INTEGER REFERENCES people(id),
  priority TEXT NOT NULL DEFAULT 'Medium',
  tat_days INTEGER, due_on TEXT,
  status TEXT NOT NULL DEFAULT 'open',   -- open|assigned|in_progress|resolved|closed
  non_compliance INTEGER NOT NULL DEFAULT 0,
  raised_by TEXT, raised_at TEXT,
  resolution TEXT, resolved_by TEXT, resolved_at TEXT,
  case_id INTEGER REFERENCES cases(id),      -- became an RFI / NCR
  task_id INTEGER REFERENCES tasks(id),      -- became a task
  llr_id INTEGER REFERENCES llr(id),         -- became a lesson
  recurrence_of INTEGER REFERENCES findings(id)   -- #10: seen before
);

-- Backlog #27/#28/#30/#31: the time model, auditable. Columns carry the
-- rollup; this carries how it got there, so a disputed figure can be walked
-- back to the transition that produced it.
CREATE TABLE IF NOT EXISTS time_log (
  id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
  category TEXT NOT NULL,   -- in_progress|wait_internal|wait_external|hold|approval|md_approval
  days REAL, from_on TEXT, to_on TEXT,
  party TEXT, note TEXT, who TEXT, at TEXT
);''')

# priority + time categories + PM hook on tasks
sub('''  own_days INTEGER NOT NULL DEFAULT 0, wait_days INTEGER NOT NULL DEFAULT 0,
  revision INTEGER NOT NULL DEFAULT 0,          -- the "Changes Required" loop
  status TEXT NOT NULL DEFAULT 'queued',        -- queued|running|waiting|done
  note TEXT, created_at TEXT, updated_at TEXT
);''',
'''  own_days INTEGER NOT NULL DEFAULT 0, wait_days INTEGER NOT NULL DEFAULT 0,
  -- Backlog #28/#29: the matrix has to separate these. wait_days stays the
  -- total; wait_ext is the part held outside the department, so internal delay
  -- is wait_days - wait_ext_days and nobody is charged for the wrong one.
  wait_ext_days INTEGER NOT NULL DEFAULT 0,
  hold_days INTEGER NOT NULL DEFAULT 0,
  revision INTEGER NOT NULL DEFAULT 0,          -- the "Changes Required" loop
  status TEXT NOT NULL DEFAULT 'queued',        -- queued|running|waiting|hold|done
  priority TEXT NOT NULL DEFAULT 'Medium',      -- #5: not a substitute for TAT
  due_on TEXT,
  hold_reason TEXT, held_at TEXT,
  external_system TEXT, external_ref TEXT, external_url TEXT,   -- #24
  origin_entity TEXT, origin_id INTEGER,                        -- #36 linkage
  note TEXT, created_at TEXT, updated_at TEXT
);''')

sub('''  own_days INTEGER NOT NULL DEFAULT 0,          -- clock while ZD held it
  wait_days INTEGER NOT NULL DEFAULT 0,         -- clock while someone else held it
  note TEXT,
  PRIMARY KEY (project_id, stage)''',
'''  own_days INTEGER NOT NULL DEFAULT 0,          -- clock while ZD held it
  wait_days INTEGER NOT NULL DEFAULT 0,         -- clock while someone else held it
  wait_ext_days INTEGER NOT NULL DEFAULT 0,     -- #29: of which, outside ZD
  hold_days INTEGER NOT NULL DEFAULT 0,         -- #27: intentionally blocked
  expected_days INTEGER,                        -- #24: published TAT for the stage
  note TEXT,
  PRIMARY KEY (project_id, stage)''')

# coordination gains priority + TAT wording + acknowledgement
sub('''CREATE TABLE IF NOT EXISTS coordination (
  id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
  stage INTEGER, from_team TEXT NOT NULL, to_lane TEXT NOT NULL,
  ask TEXT NOT NULL, sla_days INTEGER,
  opened_at TEXT NOT NULL, closed_at TEXT, task_id INTEGER
);''',
'''CREATE TABLE IF NOT EXISTS coordination (
  id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),
  stage INTEGER, from_team TEXT NOT NULL, to_lane TEXT NOT NULL,
  ask TEXT NOT NULL,
  -- Backlog #21/#25: this column is a TURNAROUND, so it is TAT. `sla_days` is
  -- kept as the physical name only because every existing row and query uses
  -- it; everything a person reads says TAT. Renaming the column is a migration
  -- for its own change, not a silent one buried in a feature.
  sla_days INTEGER,
  priority TEXT NOT NULL DEFAULT 'Medium',
  ack_due_at TEXT, acknowledged_at TEXT, ack_by TEXT,
  escalation_level INTEGER NOT NULL DEFAULT 0, escalated_at TEXT, escalated_to TEXT,
  opened_at TEXT NOT NULL, closed_at TEXT, closed_by TEXT, outcome TEXT,
  task_id INTEGER, case_id INTEGER
);''')

# lessons: root cause / performance analysis / head + audit visibility
sub('''  status TEXT NOT NULL DEFAULT 'open',          -- open|ruled|adopted|rejected
  ruling TEXT, ruled_by TEXT, ruled_at TEXT,
  promoted_stage INTEGER, promoted_at TEXT, template_id INTEGER
);''',
'''  status TEXT NOT NULL DEFAULT 'open',          -- open|ruled|adopted|rejected
  ruling TEXT, ruled_by TEXT, ruled_at TEXT,
  promoted_stage INTEGER, promoted_at TEXT, template_id INTEGER,

  -- Backlog #17: "SLA/TAT took too long" has to be answerable. Why, where, whose,
  -- internal or external, was there a dependency, what changes. A lesson that
  -- records only the symptom cannot drive an improvement.
  root_cause TEXT,
  delay_owner TEXT,          -- which team or party caused it
  delay_kind TEXT,           -- internal | external | dependency | process | none
  delay_days INTEGER,        -- how much TAT was lost
  dependency TEXT,
  preventive_action TEXT,
  improvement_status TEXT NOT NULL DEFAULT 'proposed',  -- proposed|agreed|in_progress|done|dropped
  improvement_owner TEXT, improvement_due TEXT, improvement_closed_at TEXT,

  -- Backlog #15: Lesson -> Head visibility -> Audit visibility -> repository
  head_dept TEXT, head_notified_at TEXT, audit_notified_at TEXT,
  origin_finding_id INTEGER REFERENCES findings(id),
  priority TEXT NOT NULL DEFAULT 'Medium'
);''')

sub('''CREATE INDEX IF NOT EXISTS ix_doc ON documents(entity, entity_id);''',
'''CREATE INDEX IF NOT EXISTS ix_doc ON documents(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_find ON findings(project_id, status);
CREATE INDEX IF NOT EXISTS ix_find_visit ON findings(visit_id);
CREATE INDEX IF NOT EXISTS ix_msg ON case_messages(case_id);
CREATE INDEX IF NOT EXISTS ix_tlog ON time_log(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_plog ON priority_log(entity, entity_id);''')


# ══════════════════════════════════════════════════════════════════════════
# 3 · helpers: read a setting, priority order, acknowledgement due, delivery time
# ══════════════════════════════════════════════════════════════════════════
HELP = '''

# ── settings access ─────────────────────────────────────────────────────────
# Every calculation goes through here. If a number in this system can be
# questioned, the answer has to be "because this setting says so, and here is
# who confirmed it" — not "because it is in the code".
def setting(c, key, default=None):
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r and r["value"] is not None else default


def setting_int(c, key, default=0):
    try:
        return int(float(setting(c, key, default)))
    except (TypeError, ValueError):
        return default


def setting_bool(c, key, default=False):
    v = setting(c, key, "1" if default else "0")
    return str(v).strip() in ("1", "true", "yes", "on")


def setting_list(c, key, default=""):
    return [x.strip() for x in (setting(c, key, default) or "").split("|") if x.strip()]


def priorities(c):
    return setting_list(c, "priority.levels", "Critical|High|Medium|Low")


def priority_rank(c, p):
    ps = priorities(c)
    return ps.index(p) if p in ps else len(ps)


def unconfirmed(c):
    """The definitions still waiting on the business. Shown, not hidden."""
    return [dict(r) for r in c.execute(
        "SELECT * FROM settings WHERE confirmed=0 ORDER BY section, key")]


# ── acknowledgement due (%(S)s3, and %(S)s36 A is why this is not a constant) ────────
def ack_due(c, from_iso=None):
    """When a cross-team request must have been acknowledged by.

    The unit is a SETTING, because the review left it open and the three
    readings give three different answers for anything raised on a Friday.
    """
    start = datetime.datetime.fromisoformat(from_iso) if from_iso else datetime.datetime.now()
    n = setting_int(c, "ack.window_value", 24)
    unit = setting(c, "ack.window_unit", "calendar_hours")
    if unit == "working_days":
        return datetime.datetime.combine(
            _add_working_days(start.date(), max(n // 24, 1)), start.time())
    if unit == "business_hours":
        h0 = setting_int(c, "ack.business_day_start", 9)
        h1 = setting_int(c, "ack.business_day_end", 18)
        span = max(h1 - h0, 1)
        cur, left = start, n
        while left > 0:
            if cur.weekday() < 5 and h0 <= cur.hour < h1:
                step = min(left, h1 - cur.hour)
                cur += datetime.timedelta(hours=step)
                left -= step
            else:
                cur += datetime.timedelta(hours=1)
        return cur
    return start + datetime.timedelta(hours=n)


def ack_overdue(c, row):
    if not row or row["acknowledged_at"] or not row["ack_due_at"]:
        return False
    try:
        return datetime.datetime.fromisoformat(row["ack_due_at"]) < datetime.datetime.now()
    except ValueError:
        return False


# ── delivery time (%(S)s29 / %(S)s30 / %(S)s36 F) ────────────────────────────────────
def delivery_exclusions(c):
    """What comes OUT of delivery time. %(S)s30 asked for MD approval to be removed;
    the rest are switches because %(S)s36 F says confirm the full list first."""
    out = []
    if setting_bool(c, "delivery.exclude_md_approval", True):
        out.append("md_approval")
    if setting_bool(c, "delivery.exclude_director_approval", False):
        out.append("approval")
    if setting_bool(c, "delivery.exclude_external", True):
        out.append("wait_external")
    if setting_bool(c, "delivery.exclude_hold", True):
        out.append("hold")
    return out


def log_time(c, entity, eid, category, days, from_on=None, to_on=None,
             party=None, note=None, who=None):
    c.execute("INSERT INTO time_log(entity,entity_id,category,days,from_on,to_on,"
              "party,note,who,at) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (entity, eid, category, days, from_on, to_on, party, note, who, now()))


def log_priority(c, entity, eid, old, new, reason, who, tier):
    c.execute("INSERT INTO priority_log(entity,entity_id,old_priority,new_priority,"
              "reason,who,who_tier,at) VALUES(?,?,?,?,?,?,?,?)",
              (entity, eid, old, new, reason, who, tier, now()))
''' % {"S": S}

sub("\ndef open_case(c, typ, project_id, code, title, value=None, raised_by=\"system\",",
    HELP + "\n\ndef open_case(c, typ, project_id, code, title, value=None, raised_by=\"system\",")

# open_case learns about priority, TAT, routing and origin
sub('''def open_case(c, typ, project_id, code, title, value=None, raised_by="system",
              raised_at=None, note="", position=0, origin=None):''',
'''def open_case(c, typ, project_id, code, title, value=None, raised_by="system",
              raised_at=None, note="", position=0, origin=None,
              priority=None, tat_days=None, from_team=None, to_team=None,
              origin_entity=None, origin_id=None, ack=True):''')

sub('''    raised_at = raised_at or today().isoformat()
    c.execute("INSERT INTO cases(ref,type,project_id,title,value_pkr,position,status,"
              "raised_by,raised_at,note) VALUES(?,?,?,?,?,?,'open',?,?,?)",
              (ref, typ, project_id, title, value, position, raised_by, raised_at, note))''',
'''    raised_at = raised_at or today().isoformat()
    priority = priority or setting(c, "priority.default", "Medium")
    tat = tat_days if tat_days is not None else sum(
        (l[2] or 0) for l in route["lanes"]) or None
    due = _add_working_days(datetime.date.fromisoformat(raised_at[:10]),
                            tat).isoformat() if tat else None
    ackdue = ack_due(c, raised_at if "T" in str(raised_at) else None).isoformat(
        timespec="seconds") if ack else None
    c.execute("INSERT INTO cases(ref,type,project_id,title,value_pkr,position,status,"
              "raised_by,raised_at,note,priority,tat_days,due_on,from_team,to_team,"
              "ack_due_at,origin_entity,origin_id) "
              "VALUES(?,?,?,?,?,?,'open',?,?,?,?,?,?,?,?,?,?,?)",
              (ref, typ, project_id, title, value, position, raised_by, raised_at, note,
               priority, tat, due, from_team, to_team, ackdue,
               origin_entity, origin_id))''')

open(PATH, "w", encoding="utf-8").write(src)
print("store.py: settings, priority, collaboration, findings, time model")
