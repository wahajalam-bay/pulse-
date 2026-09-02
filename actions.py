#!/usr/bin/env python3
"""ZD PULSE — the write layer. Everything a person CREATES or DECIDES.

WHY THIS IS A SEPARATE MODULE
  The first cut of this system had five write verbs and was, fairly, called a
  reporting layer. This module is the difference between a dashboard and a
  workstation: it is where work is raised, assigned, decided, signed off and
  handed over. Reads live in server.py; every mutation lives here so the audit
  surface is one file.

THE RULE EVERY HANDLER FOLLOWS
  1. authorise    — tier and lane, not just "is logged in"
  2. gate         — check preconditions; a refusal is logged, never silent
  3. mutate       — one transaction
  4. ledger       — who, what authority, what changed
  Nothing mutates without steps 1 and 4.
"""
import json, datetime, re
import store, catalog


class Refused(Exception):
    """A gate said no. Carries the payload the client shows the user."""
    def __init__(self, msg, **extra):
        super().__init__(msg)
        self.payload = dict(extra, error=msg, blocked=True)


def _req(d, *keys):
    missing = [k for k in keys if not str(d.get(k, "")).strip()]
    if missing:
        raise Refused("Missing required field: " + ", ".join(missing))


def _tier(who):
    return who.get("tier", 3)


def _pname(c, pid):
    r = c.execute("SELECT name FROM projects WHERE id=?", (pid,)).fetchone()
    return r["name"] if r else None


def _next_ref(c, prefix, code):
    n = c.execute("SELECT COUNT(*) FROM cases WHERE type=?", (prefix,)).fetchone()[0]
    return f"{prefix}-{code or 'ZD'}-{100 + n + 1}"


# ══════════════════════════════════════════════════════════════════════════
# PROJECTS & INTAKE   — Manual §3
# ══════════════════════════════════════════════════════════════════════════
INTAKE_FIELDS = [
    ("regulatory", "Regulatory data (bylaws, ground coverage)", "Acquisition / Legal"),
    ("land_area",  "Land area & plot size",                     "Acquisition / Legal"),
    ("height",     "Height of building",                        "Acquisition / Feasibility"),
    ("basements",  "Number of basements",                       "Feasibility / Geotech"),
    ("inventory",  "Inventory type",                            "Sales / Feasibility"),
    ("seismic",    "Earthquake zone identification",            "Design (Structural)"),
    ("mep",        "MEP design / layouts",                      "Design (MEP)"),
]


def project_create(c, who, d):
    """Create a project and open its intake. Manual §3.1's table, field for field."""
    if _tier(who) > 1:
        raise Refused("Only the department head or a senior manager can add a project.")
    _req(d, "name")
    name = d["name"].strip()
    if c.execute("SELECT 1 FROM projects WHERE name=?", (name,)).fetchone():
        raise Refused(f"A project called “{name}” already exists.")
    code = (d.get("code") or "".join(w[0] for w in name.split()[:3])).upper()[:5]
    c.execute("INSERT INTO projects(name,code,kind,city,status,created_at)"
              " VALUES(?,?,?,?,'Active',?)",
              (name, code, d.get("kind") or "Residential", d.get("city") or "Lahore",
               store.now()))
    pid = c.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone()["id"]
    for stage, _n, _p, _dd in catalog.STAGES:
        c.execute("INSERT OR IGNORE INTO project_stages(project_id,stage) VALUES(?,?)",
                  (pid, stage))
    c.execute("INSERT INTO intake(project_id,updated_at,updated_by) VALUES(?,?,?)",
              (pid, store.now(), who["name"]))
    store.log(c, who["name"], _tier(who), "project", pid, "create",
              f"Opened project {name} ({code}) — 13 stations, intake started", project=name)
    return {"ok": True, "id": pid}


def intake_save(c, who, d):
    """Fill the intake. Stage 3 cannot be initiated until it is complete — that is
    the gate that makes 'who is holding up the start' a field with a name on it."""
    pid = int(d.get("project_id") or 0)
    if not _pname(c, pid):
        raise Refused("No such project.")
    cur = c.execute("SELECT * FROM intake WHERE project_id=?", (pid,)).fetchone()
    if not cur:
        c.execute("INSERT INTO intake(project_id) VALUES(?)", (pid,))
    sets, args = [], []
    for k, _lbl, _src in INTAKE_FIELDS:
        if k in d:
            sets.append(f"{k}=?"); args.append(str(d[k]).strip())
    if not sets:
        raise Refused("Nothing to save.")
    args += [store.now(), who["name"], pid]
    c.execute(f"UPDATE intake SET {','.join(sets)},updated_at=?,updated_by=? "
              "WHERE project_id=?", args)
    row = c.execute("SELECT * FROM intake WHERE project_id=?", (pid,)).fetchone()
    filled = sum(1 for k, _l, _s in INTAKE_FIELDS if (row[k] or "").strip())
    store.log(c, who["name"], _tier(who), "intake", pid, "save",
              f"Intake {filled}/{len(INTAKE_FIELDS)} fields complete",
              project=_pname(c, pid))
    return {"ok": True, "filled": filled, "of": len(INTAKE_FIELDS)}


# ══════════════════════════════════════════════════════════════════════════
# STAGES  — initiating a stage is what generates the work
# ══════════════════════════════════════════════════════════════════════════
def stage_initiate(c, who, d):
    """Generate this stage's tasks for this project, straight from the catalog.

    THE GATE: stage 3 needs a complete intake (§3.4 — the initial gate), and no
    stage may open while the previous one is unsigned. Refusals are logged; a
    caller may override with a stated reason, which is also logged. Soft gates,
    because a hard block just moves the work back to paper.
    """
    pid, stage = int(d.get("project_id") or 0), int(d.get("stage") or 0)
    pname = _pname(c, pid)
    if not pname:
        raise Refused("No such project.")
    if _tier(who) > 2:
        raise Refused("Only a lead or above can initiate a stage.")
    st = c.execute("SELECT * FROM project_stages WHERE project_id=? AND stage=?",
                   (pid, stage)).fetchone()
    if st and st["status"] not in ("not_started",):
        raise Refused(f"Stage {stage} is already {st['status']}.")

    reason = (d.get("override_reason") or "").strip()

    if stage == 3:
        row = c.execute("SELECT * FROM intake WHERE project_id=?", (pid,)).fetchone()
        filled = sum(1 for k, _l, _s in INTAKE_FIELDS
                     if row and (row[k] or "").strip()) if row else 0
        if filled < len(INTAKE_FIELDS) and not reason:
            store.log(c, who["name"], _tier(who), "stage", stage, "initiate",
                      f"BLOCKED — {pname} stage 3 with intake {filled}/"
                      f"{len(INTAKE_FIELDS)} complete", project=pname, blocked=1)
            missing = [lbl for k, lbl, src in INTAKE_FIELDS
                       if not (row and (row[k] or "").strip())]
            raise Refused("Intake is incomplete — Manual §3.4 makes this the initial gate.",
                          missing=missing, gate="intake", overridable=True)

    prev = c.execute("SELECT * FROM project_stages WHERE project_id=? AND stage=?",
                     (pid, stage - 1)).fetchone()
    if stage > 3 and prev and prev["status"] not in ("done",) and not reason:
        store.log(c, who["name"], _tier(who), "stage", stage, "initiate",
                  f"BLOCKED — {pname} stage {stage} before stage {stage-1} closed",
                  project=pname, blocked=1)
        raise Refused(f"Stage {stage-1} has not been signed off.",
                      gate="sequence", overridable=True)

    steps = c.execute("SELECT * FROM products WHERE stage=? ORDER BY team,seq",
                      (stage,)).fetchall()
    if not steps:
        raise Refused(f"The catalog has no steps for stage {stage}.")

    start = store.today()
    cursor, made = start, 0
    for p in steps:
        psd = cursor
        ped = store._add_working_days(psd, p["tat_days"] or 2)
        c.execute(
            "INSERT INTO tasks(project_id,product_id,team,workflow,stage,seq,title,"
            "lane,is_external,baseline_days,planned_sd,planned_ed,status,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'queued',?,?)",
            (pid, p["id"], p["team"], p["workflow"], stage, p["seq"], p["step"],
             p["lane"], p["is_external"], p["tat_days"],
             psd.isoformat(), ped.isoformat(), store.now(), store.now()))
        cursor = ped; made += 1

    c.execute("UPDATE project_stages SET status='running',planned_start=?,planned_end=?,"
              "actual_start=? WHERE project_id=? AND stage=?",
              (start.isoformat(), cursor.isoformat(), start.isoformat(), pid, stage))

    # The mandatory checklist for this stage — Manual §4.1 — stamped from the
    # §4.2 template, so it arrives with content instead of as an empty page a
    # manager is asked to sign. Anything a lesson learned promoted into the
    # template comes with it.
    c.execute("INSERT INTO checklists(project_id,stage,created_at) VALUES(?,?,?)",
              (pid, stage, store.now()))
    clid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    tpl = c.execute("SELECT * FROM checklist_templates WHERE stage=? AND active=1 "
                    "ORDER BY seq", (stage,)).fetchall()
    for i, t in enumerate(tpl):
        c.execute("INSERT INTO checklist_items(checklist_id,seq,text,source) "
                  "VALUES(?,?,?,?)", (clid, i + 1, t["text"], t["source"]))

    store.log(c, who["name"], _tier(who), "stage", stage,
              "initiate_override" if reason else "initiate",
              f"Initiated stage {stage} on {pname} — {made} tasks from catalog, "
              f"{len(tpl)} checks from the §4.2 template"
              + (f" · OVERRIDE: {reason}" if reason else ""), project=pname)
    return {"ok": True, "tasks": made}


def stage_signoff(c, who, d):
    """Close a stage. Manual §4.1 — the checklist must be signed first."""
    pid, stage = int(d.get("project_id") or 0), int(d.get("stage") or 0)
    pname = _pname(c, pid)
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can sign off a stage.")
    reason = (d.get("override_reason") or "").strip()
    cl = c.execute("SELECT * FROM checklists WHERE project_id=? AND stage=?",
                   (pid, stage)).fetchone()
    if cl and not cl["signed_at"] and not reason:
        store.log(c, who["name"], _tier(who), "stage", stage, "signoff",
                  f"BLOCKED — {pname} stage {stage} checklist unsigned (§4.1)",
                  project=pname, blocked=1)
        raise Refused("The stage checklist has not been signed — Manual §4.1 makes it "
                      "mandatory before any drawing issuance.",
                      gate="checklist", overridable=True)
    open_n = c.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND stage=? "
                       "AND status!='done'", (pid, stage)).fetchone()[0]
    if open_n and not reason:
        raise Refused(f"{open_n} steps are still open in this stage.",
                      gate="open_tasks", overridable=True)
    c.execute("UPDATE project_stages SET status='done',actual_end=? "
              "WHERE project_id=? AND stage=?", (store.today().isoformat(), pid, stage))
    store.log(c, who["name"], _tier(who), "stage", stage,
              "signoff_override" if reason else "signoff",
              f"Signed off stage {stage} on {pname}"
              + (f" · OVERRIDE: {reason}" if reason else ""), project=pname)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# TASKS
# ══════════════════════════════════════════════════════════════════════════
def task_create(c, who, d):
    """An ad-hoc task. Not everything the department does is in the booklet."""
    _req(d, "title", "project_id")
    pid = int(d["project_id"])
    pname = _pname(c, pid)
    if not pname:
        raise Refused("No such project.")
    team = d.get("team") or who.get("team") or "Architecture"
    base = d.get("baseline_days")
    base = int(base) if str(base or "").strip().isdigit() else None
    psd = store.today()
    ped = store._add_working_days(psd, base or 2)
    c.execute("INSERT INTO tasks(project_id,team,workflow,stage,seq,title,person_id,"
              "lane,is_external,baseline_days,planned_sd,planned_ed,status,note,"
              "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,0,?,?,?,'queued',?,?,?)",
              (pid, team, d.get("workflow") or "Ad hoc",
               int(d.get("stage") or 13), 999, d["title"].strip(),
               int(d["person_id"]) if str(d.get("person_id") or "").isdigit() else None,
               team, base, psd.isoformat(), ped.isoformat(),
               (d.get("note") or "").strip(), store.now(), store.now()))
    tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    store.log(c, who["name"], _tier(who), "task", tid, "create",
              f"Created ad-hoc task · {d['title'].strip()}", project=pname, team=team)
    return {"ok": True, "id": tid}


def task_assign(c, who, d):
    tid = int(d.get("id") or 0)
    t = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not t:
        raise Refused("No such task.")
    pidv = d.get("person_id")
    person = None
    if str(pidv or "").isdigit():
        person = c.execute("SELECT * FROM people WHERE id=?", (int(pidv),)).fetchone()
        if not person:
            raise Refused("No such person.")
        if person["team"] != t["team"]:
            raise Refused(f"{person['name']} is in {person['team']}; "
                          f"this step belongs to {t['team']}.")
    c.execute("UPDATE tasks SET person_id=?,updated_at=? WHERE id=?",
              (person["id"] if person else None, store.now(), tid))
    store.log(c, who["name"], _tier(who), "task", tid, "assign",
              f"Assigned to {person['name'] if person else 'nobody'} · {t['title']}",
              project=_pname(c, t["project_id"]), team=t["team"])
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# CASES  — raise and decide, not just advance
# ══════════════════════════════════════════════════════════════════════════
def case_create(c, who, d):
    """Raise a MAR / DCR / RFI / shop drawing / vetting engagement.

    The route is instantiated from ROUTES, so the approval chain is the manual's,
    not whatever the person raising it remembers.
    """
    _req(d, "type", "title", "project_id")
    typ = d["type"].upper()
    if typ not in store.ROUTES:
        raise Refused(f"Unknown case type {typ}.")
    pid = int(d["project_id"])
    pr = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not pr:
        raise Refused("No such project.")
    val = d.get("value_pkr")
    try:
        val = float(str(val).replace(",", "")) if str(val or "").strip() else None
    except ValueError:
        raise Refused("Value must be a number.")

    # Backlog #1: a case can be raised AT another team. #5/#6: it carries a
    # priority AND a TAT, and they are different fields.
    to_team = (d.get("to_team") or "").strip() or None
    if to_team and to_team not in catalog.departments():
        raise Refused(f"{to_team} is not a department on the register.")
    prio = (d.get("priority") or "").strip() or None
    if prio and prio not in store.priorities(c):
        raise Refused(f"{prio} is not one of the configured priority levels.")
    tat = int(d["tat_days"]) if str(d.get("tat_days") or "").strip().isdigit() else None
    cid, ref = store.open_case(c, typ, pid, pr["code"], d["title"].strip(), val,
                               who["name"], store.today().isoformat(),
                               (d.get("note") or "").strip(),
                               priority=prio, tat_days=tat,
                               from_team=(d.get("from_team") or who.get("team")
                                          or "Architecture"),
                               to_team=to_team)
    if (d.get("note") or "").strip():
        _msg(c, cid, "update", d["note"].strip(), who)

    gate = ("CEO Office" if val and val >= store.PKR_CEO else
            "CPC" if val and val >= store.PKR_CPC else None)
    store.log(c, who["name"], _tier(who), "case", cid, "create",
              f"Raised {ref} · {d['title'].strip()}"
              + (f" · to {to_team}" if to_team else "")
              + (f" · {gate} approval required (PKR {val:,.0f})" if gate else ""),
              project=pr["name"])
    row = c.execute("SELECT ack_due_at FROM cases WHERE id=?", (cid,)).fetchone()
    return {"ok": True, "ref": ref, "id": cid, "gate": gate,
            "ack_due_at": row["ack_due_at"] if row else None}


def case_decide(c, who, d):
    """Approve, reject or return a case at its current lane — with a reason.

    "Advance" was the old verb and it was wrong: a review that can only say yes is
    not a review. Reject closes the case; return sends it back one lane.
    """
    cid = int(d.get("id") or 0)
    ca = c.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
    if not ca:
        raise Refused("No such case.")
    if ca["status"] != "open":
        raise Refused(f"This case is already {ca['status']}.")
    lanes = c.execute("SELECT * FROM case_lanes WHERE case_id=? ORDER BY idx",
                      (cid,)).fetchall()
    pos = ca["position"]
    if pos >= len(lanes):
        raise Refused("Case is already at the end of its route.")
    cur = lanes[pos]
    pname = _pname(c, ca["project_id"])
    outcome = (d.get("outcome") or "approve").lower()
    reason = (d.get("reason") or "").strip()

    if cur["is_stub"] and not d.get("force"):
        age = store.working_days_between(cur["entered_at"], store.today().isoformat()) or 0
        store.log(c, who["name"], _tier(who), "case", cid, "decide",
                  f"BLOCKED — {ca['ref']} sits with {cur['owner_lane']} ({age}d), "
                  f"outside ZD PULSE", project=pname, blocked=1)
        raise Refused(f"This lane belongs to {cur['owner_lane']} — outside Arch & Design.",
                      detail="Logged as an external wait. It becomes actionable when that "
                             "department's system is connected.",
                      lane=cur["owner_lane"], waiting_days=age)

    if outcome in ("reject", "return") and not reason:
        raise Refused("A rejection or return needs a reason — an unexplained "
                      "decision cannot be judged.")

    # value gate: CPC / CEO thresholds from the Supply Chain Manual
    v = ca["value_pkr"]
    if outcome == "approve" and v and v >= store.PKR_CPC:
        need = "CEO Office" if v >= store.PKR_CEO else "CPC"
        last = lanes[-1]["idx"]
        if pos == last and not d.get("force"):
            store.log(c, who["name"], _tier(who), "case", cid, "decide",
                      f"BLOCKED — {ca['ref']} PKR {v:,.0f} needs {need} approval",
                      project=pname, blocked=1)
            raise Refused(f"PKR {v:,.0f} requires {need} approval "
                          f"(Supply Chain Manual §18).", gate="value", overridable=True)

    c.execute("UPDATE case_lanes SET left_at=?,actor=?,outcome=?,note=? WHERE id=?",
              (store.now(), who["name"], outcome, reason, cur["id"]))

    if outcome == "reject":
        c.execute("UPDATE cases SET status='rejected',closed_at=? WHERE id=?",
                  (store.now(), cid))
        summ = f"{ca['ref']} REJECTED at {cur['label']} — {reason}"
    elif outcome == "return":
        nxt = max(pos - 1, 0)
        c.execute("UPDATE case_lanes SET entered_at=?,left_at=NULL,outcome=NULL "
                  "WHERE id=?", (store.now(), lanes[nxt]["id"]))
        c.execute("UPDATE cases SET position=? WHERE id=?", (nxt, cid))
        summ = f"{ca['ref']} returned to {lanes[nxt]['label']} — {reason}"
    else:
        nxt = pos + 1
        if nxt >= len(lanes):
            c.execute("UPDATE cases SET position=?,status='approved',closed_at=? "
                      "WHERE id=?", (nxt, store.now(), cid))
            summ = f"{ca['ref']} APPROVED — route complete"
        else:
            c.execute("UPDATE case_lanes SET entered_at=? WHERE id=?",
                      (store.now(), lanes[nxt]["id"]))
            c.execute("UPDATE cases SET position=? WHERE id=?", (nxt, cid))
            summ = f"{ca['ref']} · {cur['label']} → {lanes[nxt]['label']}"
            if lanes[nxt]["is_stub"]:
                # handing to a department with no system = an open coordination ask
                c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,"
                          "ask,sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
                          (ca["project_id"], 13, "Architecture", lanes[nxt]["owner_lane"],
                           f"{ca['ref']} — {lanes[nxt]['label']}", lanes[nxt]["sla_days"],
                           store.today().isoformat()))
    _msg(c, cid, "decision", f"{outcome.upper()}" + (f" — {reason}" if reason else ""), who)
    store.log(c, who["name"], _tier(who), "case", cid, outcome, summ, project=pname)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# COORDINATION  — raise the ask, not just close it
# ══════════════════════════════════════════════════════════════════════════
def coord_create(c, who, d):
    _req(d, "project_id", "to_lane", "ask")
    pid = int(d["project_id"])
    pname = _pname(c, pid)
    if not pname:
        raise Refused("No such project.")
    sla = d.get("sla_days")
    sla = int(sla) if str(sla or "").strip().isdigit() else None
    team = d.get("from_team") or who.get("team") or "Architecture"
    prio = (d.get("priority") or "").strip() or store.setting(
        c, "priority.default", "Medium")
    c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,ask,"
              "sla_days,priority,ack_due_at,opened_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (pid, int(d.get("stage") or 0), team, d["to_lane"].strip(),
               d["ask"].strip(), sla, prio,
               store.ack_due(c).isoformat(timespec="seconds"),
               store.today().isoformat()))
    cid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    store.log(c, who["name"], _tier(who), "coordination", cid, "create",
              f"Asked {d['to_lane'].strip()}: {d['ask'].strip()}"
              + (f" (SLA {sla}d)" if sla else ""), project=pname, team=team)
    return {"ok": True, "id": cid}


# ══════════════════════════════════════════════════════════════════════════
# OBLIGATIONS  — Manual §9 and §15
# ══════════════════════════════════════════════════════════════════════════
def obligation_complete(c, who, d):
    oid = int(d.get("id") or 0)
    o = c.execute("SELECT * FROM obligations WHERE id=?", (oid,)).fetchone()
    if not o:
        raise Refused("No such obligation.")
    if o["done_at"]:
        raise Refused("Already completed.")
    ev = (d.get("evidence") or "").strip()
    if not ev:
        raise Refused("Record what was done — an obligation ticked with no evidence "
                      "is not evidence.")
    c.execute("UPDATE obligations SET done_at=?,done_by=?,evidence=? WHERE id=?",
              (store.now(), who["name"], ev, oid))
    store.log(c, who["name"], _tier(who), "obligation", oid, "complete",
              f"{o['label']} — {ev[:80]}",
              project=_pname(c, o["project_id"]) if o["project_id"] else None)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# SITE VISITS  — Manual §15. Feeds the Monthly Compliance Report.
# ══════════════════════════════════════════════════════════════════════════
def visit_create(c, who, d):
    """Log the visit. Manual §15, restructured by Haroon's review §4-§6.

    The visit is now a CONTAINER: a date, a person, and the findings recorded on
    it. It no longer carries the observations itself and it no longer raises the
    NCR — a finding does that, because a visit that found five problems needs
    five owners, five clocks and five outcomes, not one of each.

    `findings` may be posted inline as a list, which is how the form submits a
    multi-finding visit in one action.
    """
    _req(d, "project_id")
    pid = int(d["project_id"])
    pname = _pname(c, pid)
    if not pname:
        raise Refused("No such project.")
    rows = d.get("findings")
    if isinstance(rows, str):
        try:
            rows = json.loads(rows)
        except ValueError:
            rows = None
    rows = [r for r in (rows or []) if str(r.get("title") or "").strip()]
    if not rows and not str(d.get("summary") or d.get("findings_text") or "").strip():
        raise Refused("Record at least one finding, or a summary if the visit "
                      "found nothing.",
                      detail="A visit with no record of what was looked at cannot "
                             "close the §15 obligation — that is the whole point of "
                             "the obligation.")
    when = d.get("visited_on") or store.today().isoformat()
    c.execute("INSERT INTO site_visits(project_id,visited_on,by_whom,findings,"
              "non_compliance,photos,created_at) VALUES(?,?,?,?,?,?,?)",
              (pid, when, who["name"],
               (d.get("summary") or d.get("findings_text") or "").strip()
               or f"{len(rows)} finding{'s' if len(rows) != 1 else ''} recorded",
               1 if any(r.get("non_compliance") for r in rows) else 0,
               int(d.get("photos") or 0), store.now()))
    vid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

    made, ncrs, recur = [], [], 0
    for i, r in enumerate(rows):
        out = finding_create(c, who, dict(r, project_id=pid, visit_id=vid))
        made.append(out["id"])
        if out.get("recurrence_of"):
            recur += 1
        # §5 of the review: a finding goes to the relevant team as an RFI/NCR.
        # Non-compliance against approved IFC is an NCR by definition (§16).
        if r.get("non_compliance"):
            got = finding_raise(c, who, {"id": out["id"], "as": "NCR"})
            ncrs.append(got["ref"])

    # doing the work IS the evidence — close this month's obligation
    due = c.execute("SELECT id FROM obligations WHERE project_id=? AND kind='site_visit' "
                    "AND done_at IS NULL AND due_on <= date('now') "
                    "ORDER BY due_on DESC LIMIT 1", (pid,)).fetchone()
    if due:
        c.execute("UPDATE obligations SET done_at=?,done_by=?,evidence=? WHERE id=?",
                  (store.now(), who["name"],
                   f"Site visit #{vid} — {len(made)} findings recorded", due["id"]))

    store.log(c, who["name"], _tier(who), "visit", vid, "create",
              f"Site visit — {len(made)} finding{'s' if len(made) != 1 else ''}"
              + (f", {len(ncrs)} NCR raised ({', '.join(ncrs)})" if ncrs else "")
              + (f", {recur} seen before" if recur else ""), project=pname)
    return {"ok": True, "id": vid, "findings": made, "ncr": ncrs,
            "recurrences": recur, "non_compliance": bool(ncrs)}


# ══════════════════════════════════════════════════════════════════════════
# DRAWINGS & TRANSMITTALS  — Manual §5
# ══════════════════════════════════════════════════════════════════════════
def drawing_create(c, who, d):
    _req(d, "project_id", "number", "title")
    pid = int(d["project_id"])
    pname = _pname(c, pid)
    if not pname:
        raise Refused("No such project.")
    c.execute("INSERT INTO drawings(project_id,number,title,discipline,revision,"
              "status,link,created_at,created_by) VALUES(?,?,?,?,?,?,?,?,?)",
              (pid, d["number"].strip(), d["title"].strip(),
               d.get("discipline") or "Architecture", d.get("revision") or "A",
               d.get("status") or "draft", (d.get("link") or "").strip(),
               store.now(), who["name"]))
    did = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    store.log(c, who["name"], _tier(who), "drawing", did, "create",
              f"Registered {d['number'].strip()} Rev {d.get('revision') or 'A'} · "
              f"{d['title'].strip()}", project=pname)
    return {"ok": True, "id": did}


def transmittal_issue(c, who, d):
    """Issue a drawing set. Manual §5 makes IFC issuance a contractual milestone
    tied to construction progress; this is the logged, auditable fact of it."""
    _req(d, "project_id", "phase", "issued_to")
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can issue drawings.")
    pid = int(d["project_id"])
    pr = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not pr:
        raise Refused("No such project.")
    reason = (d.get("override_reason") or "").strip()

    # Manual §4.1 — no issuance before the stage checklist is signed.
    stage = {"IFC Phase I": 11, "IFC Phase II": 11, "IFC Phase III": 12,
             "Tender": 10, "Authority": 7}.get(d["phase"], None)
    if stage:
        cl = c.execute("SELECT * FROM checklists WHERE project_id=? AND stage=?",
                       (pid, stage)).fetchone()
        if cl and not cl["signed_at"] and not reason:
            store.log(c, who["name"], _tier(who), "transmittal", None, "issue",
                      f"BLOCKED — {d['phase']} issuance on {pr['name']} with stage "
                      f"{stage} checklist unsigned (§4.1)", project=pr["name"], blocked=1)
            raise Refused("Manual §4.1: checklist sign-off is mandatory before any "
                          "drawing issuance.", gate="checklist", overridable=True)

    # Which sheets, at which revision. A transmittal with only a count on it is a
    # number; §5 makes the sheet list the contractual fact.
    ids = d.get("drawing_ids") or []
    if isinstance(ids, str):
        ids = [x for x in ids.replace(" ", "").split(",") if x.isdigit()]
    sheets = [dict(r) for r in c.execute(
        "SELECT * FROM drawings WHERE project_id=?", (pid,))]
    if ids:
        keep = {int(x) for x in ids}
        sheets = [s for s in sheets if s["id"] in keep]
    if not sheets and not reason:
        raise Refused("Nothing to issue — no drawing on this project is selected.",
                      detail="Register the sheets first, or override to record an "
                             "issuance made outside the register.",
                      gate="empty_transmittal", overridable=True)

    n = c.execute("SELECT COUNT(*) FROM transmittals").fetchone()[0]
    ref = f"TR-{pr['code']}-{200 + n + 1}"
    c.execute("INSERT INTO transmittals(ref,project_id,phase,issued_to,drawing_count,"
              "note,issued_at,issued_by) VALUES(?,?,?,?,?,?,?,?)",
              (ref, pid, d["phase"], d["issued_to"].strip(),
               len(sheets), (d.get("note") or "").strip(),
               store.now(), who["name"]))
    tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    ifc = d["phase"].startswith("IFC")
    for s in sheets:
        c.execute("INSERT OR IGNORE INTO transmittal_drawings(transmittal_id,"
                  "drawing_id,revision) VALUES(?,?,?)", (tid, s["id"], s["revision"]))
        if ifc and s["status"] != "IFC":
            c.execute("UPDATE drawings SET status='IFC' WHERE id=?", (s["id"],))
            c.execute("INSERT INTO drawing_revs(drawing_id,revision,status,link,note,"
                      "at,by_whom) VALUES(?,?,?,?,?,?,?)",
                      (s["id"], s["revision"], "IFC", s["link"],
                       f"Issued for construction on {ref}", store.now(), who["name"]))
    # issuing to another department opens the clock on them
    for lane in [x.strip() for x in d["issued_to"].split(",") if x.strip()]:
        if store.is_stub(lane):
            c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,"
                      "ask,sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
                      (pid, stage or 13, "Architecture", lane,
                       f"{ref} — acknowledge {d['phase']}", 3,
                       store.today().isoformat()))
    store.log(c, who["name"], _tier(who), "transmittal", tid,
              "issue_override" if reason else "issue",
              f"{ref} — {d['phase']}, {len(sheets)} sheets to "
              f"{d['issued_to'].strip()}"
              + (f" · OVERRIDE: {reason}" if reason else ""), project=pr["name"])
    return {"ok": True, "ref": ref, "id": tid, "sheets": len(sheets)}


# ══════════════════════════════════════════════════════════════════════════
# CHECKLISTS  — Manual §4.1 / §4.2
# ══════════════════════════════════════════════════════════════════════════
def checklist_add(c, who, d):
    """§4.2's annexure is "(to be added)". So the department authors it in-system,
    and the LLR loop (§7.6) can feed items in later."""
    _req(d, "checklist_id", "text")
    cid = int(d["checklist_id"])
    cl = c.execute("SELECT * FROM checklists WHERE id=?", (cid,)).fetchone()
    if not cl:
        raise Refused("No such checklist.")
    if cl["signed_at"]:
        raise Refused("This checklist is already signed.")
    n = c.execute("SELECT COALESCE(MAX(seq),0) FROM checklist_items WHERE checklist_id=?",
                  (cid,)).fetchone()[0]
    c.execute("INSERT INTO checklist_items(checklist_id,seq,text,source) VALUES(?,?,?,?)",
              (cid, n + 1, d["text"].strip(), d.get("source") or "Authored in-system"))
    store.log(c, who["name"], _tier(who), "checklist", cid, "add_item",
              f"Added check: {d['text'].strip()[:70]}",
              project=_pname(c, cl["project_id"]))
    return {"ok": True}


def checklist_tick(c, who, d):
    iid = int(d.get("id") or 0)
    it = c.execute("SELECT * FROM checklist_items WHERE id=?", (iid,)).fetchone()
    if not it:
        raise Refused("No such item.")
    done = 0 if it["done"] else 1
    c.execute("UPDATE checklist_items SET done=?,done_by=?,done_at=?,note=? WHERE id=?",
              (done, who["name"] if done else None,
               store.now() if done else None, (d.get("note") or "").strip(), iid))
    return {"ok": True, "done": bool(done)}


def checklist_sign(c, who, d):
    cid = int(d.get("id") or 0)
    cl = c.execute("SELECT * FROM checklists WHERE id=?", (cid,)).fetchone()
    if not cl:
        raise Refused("No such checklist.")
    if _tier(who) > 2:
        raise Refused("Only a lead or above can sign off a checklist.")
    items = c.execute("SELECT * FROM checklist_items WHERE checklist_id=?", (cid,)).fetchall()
    if not items:
        raise Refused("This checklist has no items yet — §4.2's annexure has not been "
                      "authored. Add the checks first.")
    undone = [i for i in items if not i["done"]]
    reason = (d.get("override_reason") or "").strip()
    if undone and not reason:
        store.log(c, who["name"], _tier(who), "checklist", cid, "sign",
                  f"BLOCKED — {len(undone)} of {len(items)} checks not ticked",
                  project=_pname(c, cl["project_id"]), blocked=1)
        raise Refused(f"{len(undone)} of {len(items)} checks are not ticked.",
                      gate="checklist_items", overridable=True)
    c.execute("UPDATE checklists SET signed_at=?,signed_by=? WHERE id=?",
              (store.now(), who["name"], cid))
    store.log(c, who["name"], _tier(who), "checklist", cid,
              "sign_override" if reason else "sign",
              f"Signed stage {cl['stage']} checklist ({len(items)} checks)"
              + (f" · OVERRIDE: {reason}" if reason else ""),
              project=_pname(c, cl["project_id"]))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# NOTES  — the thing that currently lives in WhatsApp
# ══════════════════════════════════════════════════════════════════════════
def note_add(c, who, d):
    _req(d, "entity", "entity_id", "body")
    c.execute("INSERT INTO notes(entity,entity_id,body,who,at) VALUES(?,?,?,?,?)",
              (d["entity"], int(d["entity_id"]), d["body"].strip(),
               who["name"], store.now()))
    store.log(c, who["name"], _tier(who), d["entity"], int(d["entity_id"]), "note",
              d["body"].strip()[:90])
    return {"ok": True}




# ══════════════════════════════════════════════════════════════════════════
# DRAWING REVISIONS  — Manual §5
# ══════════════════════════════════════════════════════════════════════════
def drawing_revise(c, who, d):
    """Bump a sheet. The register keeps every revision, because "which drawing is
    the contractor actually building from" is the question a drawing register
    exists to answer, and a single mutable row cannot answer it."""
    did = int(d.get("id") or 0)
    dw = c.execute("SELECT * FROM drawings WHERE id=?", (did,)).fetchone()
    if not dw:
        raise Refused("No such drawing.")
    cur = (dw["revision"] or "A").strip().upper()
    nxt = (d.get("revision") or "").strip().upper() or (
        chr(ord(cur[-1]) + 1) if cur[-1] < "Z" else cur + "1")
    if nxt == cur:
        raise Refused(f"Revision {cur} is already the current one.")
    status = d.get("status") or ("for review" if dw["status"] == "IFC" else dw["status"])
    link = (d.get("link") or dw["link"] or "").strip()
    note = (d.get("note") or "").strip()
    if not note:
        raise Refused("A revision needs a reason — that is what the register is for.")
    c.execute("UPDATE drawings SET revision=?,status=?,link=? WHERE id=?",
              (nxt, status, link, did))
    c.execute("INSERT INTO drawing_revs(drawing_id,revision,status,link,note,at,by_whom)"
              " VALUES(?,?,?,?,?,?,?)",
              (did, nxt, status, link, note, store.now(), who["name"]))
    store.log(c, who["name"], _tier(who), "drawing", did, "revise",
              f"{dw['number']} Rev {cur} → {nxt} — {note[:70]}",
              project=_pname(c, dw["project_id"]))
    return {"ok": True, "revision": nxt}


# ══════════════════════════════════════════════════════════════════════════
# THE AUTHORITY FILE  — Manual §7 and §17
# ══════════════════════════════════════════════════════════════════════════
def authority_submit(c, who, d):
    """Log a submission or an inspection. The clock on the Authority is the
    longest single wait in the department; opening it here is what makes it
    countable at all."""
    _req(d, "project_id", "authority", "kind", "title")
    pid = int(d["project_id"])
    pr = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not pr:
        raise Refused("No such project.")
    n = c.execute("SELECT COUNT(*) FROM authority").fetchone()[0]
    ref = f"AUT-{pr['code']}-{300 + n + 1}"
    day = d.get("submitted_on") or store.today().isoformat()
    stage = int(d.get("stage") or (7 if d["kind"] == "submission" else 13))
    c.execute("INSERT INTO authority(project_id,authority,kind,ref,title,stage,"
              "submitted_on,submitted_by,status,note) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (pid, d["authority"].strip(), d["kind"], ref, d["title"].strip(),
               stage, day, who["name"], "submitted", (d.get("note") or "").strip()))
    aid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    sla = int(d.get("sla_days") or 21)
    c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,ask,"
              "sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
              (pid, stage, "Architecture", "Authority",
               f"{ref} — {d['title'].strip()}", sla, day))
    coid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("UPDATE authority SET coordination_id=? WHERE id=?", (coid, aid))
    store.log(c, who["name"], _tier(who), "authority", aid, "submit",
              f"{ref} — {d['kind']} to {d['authority'].strip()}: "
              f"{d['title'].strip()}", project=pr["name"])
    return {"ok": True, "id": aid, "ref": ref}


def authority_respond(c, who, d):
    """Record what came back. An approval with conditions is not an approval
    until the conditions are written down."""
    aid = int(d.get("id") or 0)
    a = c.execute("SELECT * FROM authority WHERE id=?", (aid,)).fetchone()
    if not a:
        raise Refused("No such authority record.")
    status = (d.get("status") or "").strip().lower()
    if status not in ("observations", "approved", "rejected"):
        raise Refused("Outcome must be observations, approved or rejected.")
    obs = (d.get("observations") or "").strip()
    cond = (d.get("conditions") or "").strip()
    if status in ("observations", "rejected") and not obs:
        raise Refused("Record what the authority actually said — an unrecorded "
                      "observation cannot be answered or counted.")
    c.execute("UPDATE authority SET status=?,responded_on=?,observations=?,"
              "conditions=? WHERE id=?",
              (status, d.get("responded_on") or store.today().isoformat(),
               obs, cond, aid))
    if a["coordination_id"]:
        c.execute("UPDATE coordination SET closed_at=? WHERE id=? AND closed_at IS NULL",
                  (store.now(), a["coordination_id"]))
    # observations are work: they come back as a task on the design team
    if status == "observations":
        psd = store.today()
        c.execute("INSERT INTO tasks(project_id,team,workflow,stage,seq,title,lane,"
                  "is_external,baseline_days,planned_sd,planned_ed,status,note,"
                  "created_at,updated_at) VALUES(?,?,?,?,?,?,?,0,?,?,?,'queued',?,?,?)",
                  (a["project_id"], "Architecture", "Regulatory Inspection Support",
                   a["stage"] or 7, 900,
                   f"Answer {a['ref']} authority observations", "Architecture",
                   5, psd.isoformat(), store._add_working_days(psd, 5).isoformat(),
                   obs[:400], store.now(), store.now()))
    store.log(c, who["name"], _tier(who), "authority", aid, status,
              f"{a['ref']} → {status}" + (f" — {(obs or cond)[:70]}" if (obs or cond) else ""),
              project=_pname(c, a["project_id"]))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# LESSONS LEARNED  — Manual §7.6.  The loop that changes the next project.
# ══════════════════════════════════════════════════════════════════════════
def llr_create(c, who, d):
    _req(d, "title", "detail")
    pid = int(d["project_id"]) if str(d.get("project_id") or "").isdigit() else None
    stage = int(d["stage"]) if str(d.get("stage") or "").isdigit() else None
    # #15 — the head sees it the moment it is raised; Audit from the status the
    # governance setting names. Both are settings because who sees what is a
    # governance decision, not a coding one.
    head = store.now() if store.setting_bool(c, "lessons.notify_head", True) else None
    audit = store.now() if (store.setting_bool(c, "lessons.notify_audit", True)
                            and store.setting(c, "lessons.audit_from_status",
                                              "ruled") == "open") else None
    prio = (d.get("priority") or "").strip() or store.setting(
        c, "priority.default", "Medium")
    c.execute("INSERT INTO llr(project_id,stage,discipline,category,title,detail,"
              "impact,raised_by,raised_at,source,origin_entity,origin_id,status,"
              "root_cause,delay_kind,delay_owner,delay_days,dependency,"
              "preventive_action,head_dept,head_notified_at,audit_notified_at,priority)"
              " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'open',?,?,?,?,?,?,?,?,?,?)",
              (pid, stage, d.get("discipline") or None, d.get("category") or "General",
               d["title"].strip(), d["detail"].strip(), (d.get("impact") or "").strip(),
               who["name"], store.today().isoformat(), "Design Manual §7.6",
               d.get("origin_entity") or None,
               int(d["origin_id"]) if str(d.get("origin_id") or "").isdigit() else None,
               (d.get("root_cause") or "").strip() or None,
               (d.get("delay_kind") or "").strip() or None,
               (d.get("delay_owner") or "").strip() or None,
               int(d["delay_days"]) if str(d.get("delay_days") or "").strip().isdigit()
               else None,
               (d.get("dependency") or "").strip() or None,
               (d.get("preventive_action") or "").strip() or None,
               d.get("discipline") or "Architecture", head, audit, prio))
    lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    store.log(c, who["name"], _tier(who), "llr", lid, "create",
              f"Lesson raised — {d['title'].strip()[:70]}",
              project=_pname(c, pid) if pid else None)
    return {"ok": True, "id": lid}


def llr_rule(c, who, d):
    """Rule on a lesson. §7.6 names Head ZD; PM §8.3 defines a competing process
    and neither document references the other. Recorded, not silently resolved."""
    lid = int(d.get("id") or 0)
    l = c.execute("SELECT * FROM llr WHERE id=?", (lid,)).fetchone()
    if not l:
        raise Refused("No such lesson.")
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can rule on a "
                      "lesson — the ruling changes what every future project is "
                      "checked against.")
    ruling = (d.get("ruling") or "").strip()
    if not ruling:
        raise Refused("A ruling with no text is not a ruling.")
    status = (d.get("status") or "ruled").lower()
    c.execute("UPDATE llr SET status=?,ruling=?,ruled_by=?,ruled_at=? WHERE id=?",
              (status, ruling, who["name"], store.now(), lid))
    if (status == "ruled" and not l["audit_notified_at"]
            and store.setting_bool(c, "lessons.notify_audit", True)
            and store.setting(c, "lessons.audit_from_status", "ruled") in
            ("open", "ruled")):
        c.execute("UPDATE llr SET audit_notified_at=? WHERE id=?", (store.now(), lid))
    store.log(c, who["name"], _tier(who), "llr", lid, status,
              f"{l['title'][:60]} → {status}: {ruling[:70]}",
              project=_pname(c, l["project_id"]) if l["project_id"] else None)
    return {"ok": True}


def llr_promote(c, who, d):
    """THE LOOP. A ruled lesson becomes a permanent item on the stage checklist
    template, and lands immediately on every checklist for that stage that is not
    yet signed. That is the difference between a lessons register and a lessons
    log: this one changes what the next project is stopped for."""
    lid = int(d.get("id") or 0)
    l = c.execute("SELECT * FROM llr WHERE id=?", (lid,)).fetchone()
    if not l:
        raise Refused("No such lesson.")
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can change the "
                      "stage checklist template.")
    stage = int(d.get("stage") or l["stage"] or 0)
    text = (d.get("text") or "").strip()
    if not stage:
        raise Refused("Which stage should check for this?")
    if not text:
        raise Refused("Write the check as it should appear on the checklist.")
    if not l["ruling"] and not (d.get("override_reason") or "").strip():
        store.log(c, who["name"], _tier(who), "llr", lid, "promote",
                  f"BLOCKED — {l['title'][:50]} promoted before it was ruled on",
                  blocked=1)
        raise Refused("This lesson has not been ruled on yet.",
                      detail="§7.6 puts the ruling before adoption. Rule on it first, "
                             "or override with a reason.", overridable=True)
    n = c.execute("SELECT COALESCE(MAX(seq),0) FROM checklist_templates WHERE stage=?",
                  (stage,)).fetchone()[0]
    c.execute("INSERT INTO checklist_templates(stage,seq,text,source,llr_id,added_by,"
              "added_at) VALUES(?,?,?,?,?,?,?)",
              (stage, n + 1, text, f"Lessons learned LLR-{lid}", lid,
               who["name"], store.now()))
    tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("UPDATE llr SET status='adopted',promoted_stage=?,promoted_at=?,"
              "template_id=? WHERE id=?", (stage, store.now(), tid, lid))
    # live projects get it too, as long as the checklist is still open
    live = c.execute("SELECT * FROM checklists WHERE stage=? AND signed_at IS NULL",
                     (stage,)).fetchall()
    for cl in live:
        m = c.execute("SELECT COALESCE(MAX(seq),0) FROM checklist_items "
                      "WHERE checklist_id=?", (cl["id"],)).fetchone()[0]
        c.execute("INSERT INTO checklist_items(checklist_id,seq,text,source) "
                  "VALUES(?,?,?,?)", (cl["id"], m + 1, text, f"Lessons learned LLR-{lid}"))
    store.log(c, who["name"], _tier(who), "llr", lid, "promote",
              f"Adopted into the stage {stage} checklist template "
              f"({len(live)} open checklists updated): {text[:60]}")
    return {"ok": True, "stage": stage, "checklists_updated": len(live)}


# ══════════════════════════════════════════════════════════════════════════
# DOCUMENTS  — the link register. We do not store files; we record which file
# is current, what it belongs to, and who attached it.
# ══════════════════════════════════════════════════════════════════════════
def document_add(c, who, d):
    _req(d, "entity", "entity_id", "title", "link")
    pid = int(d["project_id"]) if str(d.get("project_id") or "").isdigit() else None
    c.execute("INSERT INTO documents(entity,entity_id,project_id,title,kind,link,"
              "revision,added_by,added_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (d["entity"], int(d["entity_id"]), pid, d["title"].strip(),
               d.get("kind") or "Reference", d["link"].strip(),
               d.get("revision") or "A", who["name"], store.now()))
    did = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    store.log(c, who["name"], _tier(who), d["entity"], int(d["entity_id"]), "document",
              f"Attached {d['title'].strip()[:60]}",
              project=_pname(c, pid) if pid else None)
    return {"ok": True, "id": did}


# ══════════════════════════════════════════════════════════════════════════
# CHECKLIST TEMPLATE  — the §4.2 annexure, editable in-system
# ══════════════════════════════════════════════════════════════════════════
def template_add(c, who, d):
    _req(d, "stage", "text")
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can change the "
                      "stage checklist template.")
    stage = int(d["stage"])
    n = c.execute("SELECT COALESCE(MAX(seq),0) FROM checklist_templates WHERE stage=?",
                  (stage,)).fetchone()[0]
    c.execute("INSERT INTO checklist_templates(stage,seq,text,source,added_by,added_at)"
              " VALUES(?,?,?,?,?,?)",
              (stage, n + 1, d["text"].strip(), d.get("source") or "Authored in-system",
               who["name"], store.now()))
    store.log(c, who["name"], _tier(who), "template", stage, "add",
              f"Stage {stage} checklist template → {d['text'].strip()[:60]}")
    return {"ok": True}


def template_retire(c, who, d):
    tid = int(d.get("id") or 0)
    t = c.execute("SELECT * FROM checklist_templates WHERE id=?", (tid,)).fetchone()
    if not t:
        raise Refused("No such template item.")
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can retire a check.")
    reason = (d.get("reason") or "").strip()
    if not reason:
        raise Refused("Retiring a check needs a reason. It stays in the ledger.")
    c.execute("UPDATE checklist_templates SET active=0 WHERE id=?", (tid,))
    store.log(c, who["name"], _tier(who), "template", t["stage"], "retire",
              f"Retired from stage {t['stage']}: {t['text'][:50]} — {reason[:60]}")
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# CLOSEOUT  — Manual §18. The lifecycle gets an end.
# ══════════════════════════════════════════════════════════════════════════
def project_close(c, who, d):
    pid = int(d.get("project_id") or 0)
    pr = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not pr:
        raise Refused("No such project.")
    if _tier(who) > 0:
        raise Refused("Only the department head can close a project out.")
    reason = (d.get("override_reason") or "").strip()
    open_st = c.execute("SELECT COUNT(*) FROM project_stages WHERE project_id=? "
                        "AND status!='done'", (pid,)).fetchone()[0]
    asbuilt = c.execute("SELECT COUNT(*) FROM transmittals WHERE project_id=? "
                        "AND phase='As-built'", (pid,)).fetchone()[0]
    ncr = c.execute("""SELECT COUNT(*) FROM cases WHERE project_id=? AND type='NCR'
                       AND status='open'""", (pid,)).fetchone()[0]
    blocks = []
    if open_st:
        blocks.append(f"{open_st} of 14 stations are not signed off")
    if not asbuilt:
        blocks.append("no as-built transmittal has been issued (§18)")
    if ncr:
        blocks.append(f"{ncr} NCRs are still open (§16)")
    if blocks and not reason:
        store.log(c, who["name"], _tier(who), "project", pid, "close",
                  f"BLOCKED — closeout of {pr['name']}: " + "; ".join(blocks),
                  project=pr["name"], blocked=1)
        raise Refused("This project cannot be closed out yet.",
                      missing=blocks, gate="closeout", overridable=True)
    c.execute("UPDATE projects SET status='Closed' WHERE id=?", (pid,))
    store.log(c, who["name"], _tier(who), "project", pid,
              "close_override" if reason else "close",
              f"Closed out {pr['name']}" + (f" — OVERRIDE: {reason}" if reason else ""),
              project=pr["name"])
    return {"ok": True}


def case_withdraw(c, who, d):
    cid = int(d.get("id") or 0)
    ca = c.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
    if not ca:
        raise Refused("No such case.")
    if ca["status"] != "open":
        raise Refused(f"This case is already {ca['status']}.")
    reason = (d.get("reason") or "").strip()
    if not reason:
        raise Refused("Withdrawing a case needs a reason.")
    c.execute("UPDATE cases SET status='withdrawn',closed_at=? WHERE id=?",
              (store.now(), cid))
    c.execute("UPDATE coordination SET closed_at=? WHERE ask LIKE ? AND closed_at IS NULL",
              (store.now(), ca["ref"] + "%"))
    store.log(c, who["name"], _tier(who), "case", cid, "withdraw",
              f"{ca['ref']} withdrawn — {reason[:70]}",
              project=_pname(c, ca["project_id"]))
    return {"ok": True}




# ══════════════════════════════════════════════════════════════════════════
# COLLABORATION  — Haroon's review §2.1, §3, §16.  The largest gap in the
# system: a case could be decided but not TALKED ABOUT, so every clarification
# left ZD for email and came back as a decision with no visible reasoning.
# ══════════════════════════════════════════════════════════════════════════
def _msg(c, case_id, kind, body, who, at=None):
    c.execute("INSERT INTO case_messages(case_id,kind,body,who,who_team,who_tier,at)"
              " VALUES(?,?,?,?,?,?,?)",
              (case_id, kind, body, who["name"], who.get("team"),
               who.get("tier", 3), at or store.now()))


def case_message(c, who, d):
    """An update that does NOT close the case.

    The review asked for this specifically: "The receiving team should be able to
    provide updates without closing the case." Before this the only way to say
    anything was to decide, so a team with a partial answer either sat silent or
    closed something that was not finished.
    """
    _req(d, "id", "body")
    cid = int(d["id"])
    ca = c.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
    if not ca:
        raise Refused("No such case.")
    kind = (d.get("kind") or "update").lower()
    if kind not in ("update", "question", "answer"):
        raise Refused("A message is an update, a question or an answer.")
    _msg(c, cid, kind, d["body"].strip(), who)
    # answering counts as acknowledging — nobody should have to do both
    if not ca["acknowledged_at"]:
        c.execute("UPDATE cases SET acknowledged_at=?,ack_by=? WHERE id=?",
                  (store.now(), who["name"], cid))
    store.log(c, who["name"], _tier(who), "case", cid, kind,
              f"{ca['ref']} — {d['body'].strip()[:70]}",
              project=_pname(c, ca["project_id"]), team=who.get("team"))
    return {"ok": True}


def case_ack(c, who, d):
    """Acknowledge receipt. Backlog #3.

    The window is a SETTING, not a constant, because §36 A leaves open whether
    24 hours means calendar hours, business hours or working days — and a request
    raised at 4pm Friday is due Saturday afternoon on one reading and Monday
    afternoon on another.
    """
    cid = int(d.get("id") or 0)
    ca = c.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
    if not ca:
        raise Refused("No such case.")
    if ca["acknowledged_at"]:
        raise Refused(f"{ca['ref']} was already acknowledged by {ca['ack_by']}.")
    late = store.ack_overdue(c, ca)
    c.execute("UPDATE cases SET acknowledged_at=?,ack_by=? WHERE id=?",
              (store.now(), who["name"], cid))
    _msg(c, cid, "ack", (d.get("body") or "Acknowledged.").strip(), who)
    store.log(c, who["name"], _tier(who), "case", cid, "acknowledge",
              f"{ca['ref']} acknowledged" + (" — AFTER the window closed" if late else
                                             " inside the window"),
              project=_pname(c, ca["project_id"]), team=who.get("team"),
              blocked=1 if late else 0)
    return {"ok": True, "late": late}


def case_escalate(c, who, d):
    """Climb the ladder. Backlog #4 and #20.

    §16: "Collaboration should not be limited to junior employees across
    departments." An escalation is not a sharper email — it is a recorded step
    with a named senior person and a reason, so "how often did we have to
    escalate to get an answer" becomes a number a head can act on.
    """
    cid = int(d.get("id") or 0)
    ca = c.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
    if not ca:
        raise Refused("No such case.")
    reason = (d.get("reason") or "").strip()
    if not reason:
        raise Refused("An escalation needs a reason. It is going to a senior "
                      "person's queue and they will ask why.")
    ladder = store.setting_list(c, "escalation.levels",
                                "Line Manager|Senior Manager|Department Head")
    lvl = min((ca["escalation_level"] or 0) + 1, len(ladder))
    to = (d.get("escalated_to") or "").strip() or \
        f"{ladder[lvl - 1]}, {ca['to_team'] or 'receiving team'}"
    c.execute("UPDATE cases SET escalation_level=?,escalated_at=?,escalated_to=?,"
              "escalated_by=?,escalation_reason=? WHERE id=?",
              (lvl, store.now(), to, who["name"], reason, cid))
    _msg(c, cid, "escalation", f"Escalated to {to} — {reason}", who)
    store.log(c, who["name"], _tier(who), "case", cid, "escalate",
              f"{ca['ref']} escalated to {to} (level {lvl}) — {reason[:60]}",
              project=_pname(c, ca["project_id"]))
    return {"ok": True, "level": lvl, "to": to}


# ══════════════════════════════════════════════════════════════════════════
# PRIORITY  — Backlog #5 / #6.  Priority is business importance. TAT is time.
# They were the same field and the review separated them.
# ══════════════════════════════════════════════════════════════════════════
PRIORITISED = {"case": "cases", "task": "tasks", "finding": "findings",
               "coordination": "coordination", "llr": "llr"}


def priority_set(c, who, d):
    """Change priority mid-life and keep the history — the review asked for
    "visibility of how priority changes affect the case/task", which is only
    answerable if the old value and the reason survive."""
    _req(d, "entity", "id", "priority")
    ent, eid = d["entity"], int(d["id"])
    tbl = PRIORITISED.get(ent)
    if not tbl:
        raise Refused(f"{ent} does not carry a priority.")
    new = d["priority"].strip()
    if new not in store.priorities(c):
        raise Refused(f"{new} is not one of the configured levels "
                      f"({', '.join(store.priorities(c))}).")
    if _tier(who) > store.setting_int(c, "priority.who_can_change", 1):
        raise Refused("Your tier cannot change priority. Who may is a setting, "
                      "because the review left the rules for changing priority open.")
    row = c.execute(f"SELECT * FROM {tbl} WHERE id=?", (eid,)).fetchone()
    if not row:
        raise Refused("No such record.")
    old = row["priority"]
    if old == new:
        raise Refused(f"Already {new}.")
    reason = (d.get("reason") or "").strip()
    if store.setting_bool(c, "priority.change_needs_reason", True) and not reason:
        raise Refused("State why the priority is changing. It goes in the history, "
                      "so that a Critical raised on a Friday can be explained later.")
    c.execute(f"UPDATE {tbl} SET priority=? WHERE id=?", (new, eid))
    store.log_priority(c, ent, eid, old, new, reason, who["name"], _tier(who))
    if ent == "case":
        _msg(c, eid, "update", f"Priority {old} → {new}"
             + (f" — {reason}" if reason else ""), who)
    store.log(c, who["name"], _tier(who), ent, eid, "priority",
              f"Priority {old} → {new}" + (f" — {reason[:60]}" if reason else ""))
    return {"ok": True, "priority": new}


# ══════════════════════════════════════════════════════════════════════════
# FINDINGS  — Backlog #7 / #8 / #9 / #10 / #23
# "A visit should not become one large unstructured record."
# ══════════════════════════════════════════════════════════════════════════
FINDING_CATEGORIES = ["Structural", "Architectural finish", "MEP coordination",
                      "Waterproofing", "Safety", "Dimensional", "Material",
                      "Documentation", "Workmanship", "Authority compliance"]


def _recurrence(c, pid, category, location, exclude_id=None):
    """#10: has this been seen on this project before? Same category, same
    place. This is what turns "another marble complaint" into "the fourth
    marble complaint in the same lobby", which is a different conversation."""
    if not category or not location:
        return None
    r = c.execute("SELECT id FROM findings WHERE project_id=? AND category=? "
                  "AND lower(location)=lower(?) AND id!=? ORDER BY id LIMIT 1",
                  (pid, category, location, exclude_id or -1)).fetchone()
    return r["id"] if r else None


def finding_create(c, who, d):
    _req(d, "project_id", "title")
    pid = int(d["project_id"])
    pname = _pname(c, pid)
    if not pname:
        raise Refused("No such project.")
    vid = int(d["visit_id"]) if str(d.get("visit_id") or "").isdigit() else None
    team = (d.get("responsible_team") or "").strip() or None
    if team and team not in catalog.departments():
        raise Refused(f"{team} is not a department on the register.")
    prio = (d.get("priority") or "").strip() or store.setting(
        c, "priority.default", "Medium")
    if prio not in store.priorities(c):
        raise Refused(f"{prio} is not a configured priority level.")
    tat = int(d["tat_days"]) if str(d.get("tat_days") or "").strip().isdigit() else None
    due = store._add_working_days(store.today(), tat).isoformat() if tat else None
    seq = c.execute("SELECT COALESCE(MAX(seq),0)+1 n FROM findings WHERE visit_id=?",
                    (vid,)).fetchone()["n"] if vid else 1
    loc = (d.get("location") or "").strip()
    cat = (d.get("category") or "").strip()
    prev = _recurrence(c, pid, cat, loc)
    c.execute("INSERT INTO findings(visit_id,project_id,seq,category,title,description,"
              "location,responsible_team,person_id,priority,tat_days,due_on,status,"
              "non_compliance,raised_by,raised_at,recurrence_of) "
              "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (vid, pid, seq, cat, d["title"].strip(),
               (d.get("description") or "").strip(), loc, team,
               int(d["person_id"]) if str(d.get("person_id") or "").isdigit() else None,
               prio, tat, due,
               "assigned" if team else "open",
               1 if d.get("non_compliance") else 0,
               who["name"], store.today().isoformat(), prev))
    fid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    store.log(c, who["name"], _tier(who), "finding", fid, "create",
              f"Finding — {d['title'].strip()[:60]}"
              + (f" · recurrence of #{prev}" if prev else "")
              + (" · NON-COMPLIANT" if d.get("non_compliance") else ""),
              project=pname, team=team)
    return {"ok": True, "id": fid, "recurrence_of": prev}


def finding_assign(c, who, d):
    """#9: "individual findings should be assignable to the relevant PM/team"."""
    fid = int(d.get("id") or 0)
    f = c.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
    if not f:
        raise Refused("No such finding.")
    team = (d.get("responsible_team") or "").strip() or f["responsible_team"]
    if not team:
        raise Refused("Which team owns this?")
    if team not in catalog.departments():
        raise Refused(f"{team} is not a department on the register.")
    person = None
    if str(d.get("person_id") or "").isdigit():
        person = c.execute("SELECT * FROM people WHERE id=?",
                           (int(d["person_id"]),)).fetchone()
        if person and person["team"] != team and catalog.dept_kind(team) == "design":
            raise Refused(f"{person['name']} is in {person['team']}, not {team}.")
    tat = int(d["tat_days"]) if str(d.get("tat_days") or "").strip().isdigit() \
        else f["tat_days"]
    due = store._add_working_days(store.today(), tat).isoformat() if tat else f["due_on"]
    c.execute("UPDATE findings SET responsible_team=?,person_id=?,tat_days=?,due_on=?,"
              "status=CASE WHEN status='open' THEN 'assigned' ELSE status END WHERE id=?",
              (team, person["id"] if person else None, tat, due, fid))
    store.log(c, who["name"], _tier(who), "finding", fid, "assign",
              f"{f['title'][:50]} → {team}"
              + (f" ({person['name']})" if person else "")
              + (f", TAT {tat}d" if tat else ""),
              project=_pname(c, f["project_id"]), team=team)
    return {"ok": True}


def finding_resolve(c, who, d):
    fid = int(d.get("id") or 0)
    f = c.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
    if not f:
        raise Refused("No such finding.")
    res = (d.get("resolution") or "").strip()
    if not res:
        raise Refused("Record what was actually done. A finding closed with no "
                      "resolution cannot be checked on the next visit — which is "
                      "exactly how the same problem gets found four times.")
    status = (d.get("status") or "resolved").lower()
    if status not in ("resolved", "closed"):
        raise Refused("Outcome is resolved or closed.")
    if f["non_compliance"] and status == "closed" and f["case_id"]:
        ncr = c.execute("SELECT status,ref FROM cases WHERE id=?",
                        (f["case_id"],)).fetchone()
        if ncr and ncr["status"] == "open" and not (d.get("override_reason") or "").strip():
            store.log(c, who["name"], _tier(who), "finding", fid, "resolve",
                      f"BLOCKED — closing {f['title'][:40]} while {ncr['ref']} is open",
                      project=_pname(c, f["project_id"]), blocked=1)
            raise Refused(f"{ncr['ref']} is still open on the §16 route.",
                          detail="A non-compliance is closed by the NCR being closed, "
                                 "not by the finding being ticked. Close the NCR, or "
                                 "override with a reason.",
                          gate="ncr_open", overridable=True)
    c.execute("UPDATE findings SET status=?,resolution=?,resolved_by=?,resolved_at=? "
              "WHERE id=?", (status, res, who["name"], store.now(), fid))
    store.log(c, who["name"], _tier(who), "finding", fid, status,
              f"{f['title'][:50]} — {res[:60]}", project=_pname(c, f["project_id"]),
              team=f["responsible_team"])
    return {"ok": True}


def finding_raise(c, who, d):
    """#9: a finding becomes an RFI, an NCR or a task, and stays linked to the
    visit it came from. Visit → Finding → Relevant Team → RFI / Action."""
    fid = int(d.get("id") or 0)
    f = c.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
    if not f:
        raise Refused("No such finding.")
    as_what = (d.get("as") or "NCR").upper()
    pr = c.execute("SELECT * FROM projects WHERE id=?", (f["project_id"],)).fetchone()

    if as_what == "TASK":
        if f["task_id"]:
            raise Refused("A task has already been created from this finding.")
        team = f["responsible_team"] or "Architecture"
        base = f["tat_days"] or 5
        psd = store.today()
        c.execute("INSERT INTO tasks(project_id,team,workflow,stage,seq,title,person_id,"
                  "lane,is_external,baseline_days,planned_sd,planned_ed,status,priority,"
                  "due_on,note,origin_entity,origin_id,created_at,updated_at) "
                  "VALUES(?,?,?,?,?,?,?,?,0,?,?,?,'queued',?,?,?,'finding',?,?,?)",
                  (f["project_id"], team, "QA/QC Site Coordination", 13, 950,
                   f["title"], f["person_id"], team, base, psd.isoformat(),
                   store._add_working_days(psd, base).isoformat(), f["priority"],
                   f["due_on"], f["description"], fid, store.now(), store.now()))
        tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("UPDATE findings SET task_id=?,status='in_progress' WHERE id=?",
                  (tid, fid))
        store.log(c, who["name"], _tier(who), "finding", fid, "raise_task",
                  f"{f['title'][:50]} → task #{tid} on {team}",
                  project=pr["name"], team=team)
        return {"ok": True, "task_id": tid}

    if as_what not in store.ROUTES:
        raise Refused(f"Unknown route {as_what}.")
    if f["case_id"]:
        ex = c.execute("SELECT ref FROM cases WHERE id=?", (f["case_id"],)).fetchone()
        raise Refused(f"This finding already raised {ex['ref'] if ex else 'a case'}.")
    cid, ref = store.open_case(
        c, as_what, f["project_id"], pr["code"], f["title"], None, who["name"],
        store.today().isoformat(),
        f"{f['category'] or ''} — {f['location'] or ''}. {f['description'] or ''}".strip(),
        position=1 if as_what == "NCR" else 0,
        origin=f"finding #{fid}", priority=f["priority"], tat_days=f["tat_days"],
        from_team="Architecture", to_team=f["responsible_team"],
        origin_entity="finding", origin_id=fid)
    c.execute("UPDATE findings SET case_id=? WHERE id=?", (cid, fid))
    # §16: an NCR is closed by a joint re-inspection, so raising one starts the
    # clock on QA/QC there and then. Without this the route exists but the wait on
    # the re-inspection is invisible — which is the thing the ledger is for.
    if as_what == "NCR":
        c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,ask,"
                  "sla_days,priority,ack_due_at,opened_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (f["project_id"], 13, "Architecture", "QA/QC",
                   f"{ref} — joint re-inspection after rectification",
                   f["tat_days"] or 5, f["priority"],
                   store.ack_due(c).isoformat(timespec="seconds"),
                   store.today().isoformat()))
    store.log(c, who["name"], _tier(who), "finding", fid, "raise_" + as_what.lower(),
              f"{f['title'][:50]} → {ref}", project=pr["name"],
              team=f["responsible_team"])
    return {"ok": True, "ref": ref, "case_id": cid}


def finding_to_lesson(c, who, d):
    """A finding that keeps coming back is a lesson, not a defect. #10 → §7.6."""
    fid = int(d.get("id") or 0)
    f = c.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
    if not f:
        raise Refused("No such finding.")
    if f["llr_id"]:
        raise Refused("A lesson has already been raised from this finding.")
    out = llr_create(c, who, {
        "project_id": f["project_id"], "title": d.get("title") or f["title"],
        "detail": d.get("detail") or (f["description"] or f["title"]),
        "impact": d.get("impact") or "",
        "stage": 13, "discipline": f["responsible_team"],
        "category": f["category"] or "General",
        "origin_entity": "finding", "origin_id": fid,
        "root_cause": d.get("root_cause") or "",
        "delay_kind": d.get("delay_kind") or "",
        "delay_owner": d.get("delay_owner") or f["responsible_team"] or "",
        "preventive_action": d.get("preventive_action") or "",
    })
    c.execute("UPDATE findings SET llr_id=? WHERE id=?", (out["id"], fid))
    c.execute("UPDATE llr SET origin_finding_id=? WHERE id=?", (fid, out["id"]))
    return out


# ══════════════════════════════════════════════════════════════════════════
# HOLD  — Backlog #27 / #31.  "Hold / Blocking Time: progress is intentionally
# or externally blocked."  Without this verb, blocked time was silently charged
# to the team as if they were working.
# ══════════════════════════════════════════════════════════════════════════
def task_hold(c, who, d):
    tid = int(d.get("id") or 0)
    t = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not t:
        raise Refused("No such task.")
    if t["status"] == "done":
        raise Refused("This step is finished.")
    if t["status"] == "hold":
        raise Refused("Already on hold.")
    reason = (d.get("reason") or "").strip()
    if not reason:
        raise Refused("Say what is blocking it. Hold time is excluded from the "
                      "team's own time, so an unexplained hold is an unexplained "
                      "gap in the SLA.")
    c.execute("UPDATE tasks SET status='hold',hold_reason=?,held_at=?,updated_at=? "
              "WHERE id=?", (reason, store.now(), store.now(), tid))
    store.log(c, who["name"], _tier(who), "task", tid, "hold",
              f"On hold — {reason[:70]}", project=_pname(c, t["project_id"]),
              team=t["team"])
    return {"ok": True}


def task_resume(c, who, d):
    tid = int(d.get("id") or 0)
    t = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not t:
        raise Refused("No such task.")
    if t["status"] != "hold":
        raise Refused("This step is not on hold.")
    days = store.working_days_between(
        (t["held_at"] or store.now())[:10], store.today().isoformat()) or 0
    c.execute("UPDATE tasks SET status=?,hold_days=hold_days+?,hold_reason=NULL,"
              "held_at=NULL,updated_at=? WHERE id=?",
              ("waiting" if t["is_external"] else "running", days, store.now(), tid))
    store.log_time(c, "task", tid, "hold", days, (t["held_at"] or "")[:10],
                   store.today().isoformat(), note=t["hold_reason"], who=who["name"])
    store.log(c, who["name"], _tier(who), "task", tid, "resume",
              f"Resumed after {days}d on hold — {(t['hold_reason'] or '')[:50]}",
              project=_pname(c, t["project_id"]), team=t["team"])
    return {"ok": True, "hold_days": days}


# ══════════════════════════════════════════════════════════════════════════
# SETTINGS  — §36.  "Should not be hard-coded until the business definition is
# confirmed."  So the definition is a row, and confirming it is an action with
# a name against it.
# ══════════════════════════════════════════════════════════════════════════
def setting_save(c, who, d):
    _req(d, "key")
    key = d["key"].strip()
    row = c.execute("SELECT * FROM settings WHERE key=?", (key,)).fetchone()
    if not row:
        raise Refused("No such setting.")
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can change a "
                      "business definition. Every calculation in the system reads "
                      "these.")
    val = str(d.get("value", "")).strip()
    if row["options"]:
        allowed = [x for x in row["options"].split("|") if x]
        if row["kind"] == "choice" and val not in allowed:
            raise Refused(f"{val} is not one of: {', '.join(allowed)}")
    if row["kind"] == "int" and not val.lstrip("-").isdigit():
        raise Refused("That setting takes a number.")
    old = row["value"]
    confirm = 1 if d.get("confirm") else row["confirmed"]
    c.execute("UPDATE settings SET value=?,confirmed=?,confirmed_by=?,confirmed_at=?,"
              "updated_at=?,updated_by=? WHERE key=?",
              (val, confirm,
               who["name"] if confirm and not row["confirmed"] else row["confirmed_by"],
               store.now() if confirm and not row["confirmed"] else row["confirmed_at"],
               store.now(), who["name"], key))
    store.log(c, who["name"], _tier(who), "setting", None,
              "confirm" if confirm and not row["confirmed"] else "save",
              f"{row['label']}: {old} → {val}"
              + (" — CONFIRMED" if confirm and not row["confirmed"] else "")
              + f" ({row['doc_ref']})")
    return {"ok": True, "confirmed": bool(confirm)}


# ══════════════════════════════════════════════════════════════════════════
# LESSONS  — Backlog #17 improvement tracking
# ══════════════════════════════════════════════════════════════════════════
def llr_improve(c, who, d):
    """Move the improvement, not the lesson. A lesson can be adopted into a
    checklist and still have an open action behind it; the review asked to see
    "open improvement actions" and "closed improvements" separately."""
    lid = int(d.get("id") or 0)
    l = c.execute("SELECT * FROM llr WHERE id=?", (lid,)).fetchone()
    if not l:
        raise Refused("No such lesson.")
    st = (d.get("improvement_status") or "").strip().lower()
    if st not in ("proposed", "agreed", "in_progress", "done", "dropped"):
        raise Refused("Status is proposed, agreed, in_progress, done or dropped.")
    if st == "dropped" and not (d.get("note") or "").strip():
        raise Refused("Dropping an improvement needs a reason.")
    c.execute("UPDATE llr SET improvement_status=?,improvement_owner=?,"
              "improvement_due=?,improvement_closed_at=?,preventive_action=? WHERE id=?",
              (st, (d.get("improvement_owner") or l["improvement_owner"] or "").strip()
               or None, (d.get("improvement_due") or l["improvement_due"] or "") or None,
               store.now() if st in ("done", "dropped") else None,
               (d.get("preventive_action") or l["preventive_action"] or "").strip()
               or None, lid))
    store.log(c, who["name"], _tier(who), "llr", lid, "improvement",
              f"{l['title'][:50]} — improvement {st}"
              + (f": {d['note'].strip()[:50]}" if d.get("note") else ""),
              project=_pname(c, l["project_id"]) if l["project_id"] else None)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
DISPATCH = {
    "/api/project/create":       project_create,
    "/api/intake/save":          intake_save,
    "/api/stage/initiate":       stage_initiate,
    "/api/stage/signoff":        stage_signoff,
    "/api/task/create":          task_create,
    "/api/task/assign":          task_assign,
    "/api/case/create":          case_create,
    "/api/case/decide":          case_decide,
    "/api/coordination/create":  coord_create,
    "/api/obligation/complete":  obligation_complete,
    "/api/visit/create":         visit_create,
    "/api/drawing/create":       drawing_create,
    "/api/transmittal/issue":    transmittal_issue,
    "/api/checklist/add":        checklist_add,
    "/api/checklist/tick":       checklist_tick,
    "/api/checklist/sign":       checklist_sign,
    "/api/note/add":             note_add,
    "/api/drawing/revise":       drawing_revise,
    "/api/authority/submit":     authority_submit,
    "/api/authority/respond":    authority_respond,
    "/api/llr/create":           llr_create,
    "/api/llr/rule":             llr_rule,
    "/api/llr/promote":          llr_promote,
    "/api/document/add":         document_add,
    "/api/template/add":         template_add,
    "/api/template/retire":      template_retire,
    "/api/project/close":        project_close,
    "/api/case/withdraw":        case_withdraw,
    "/api/case/message":         case_message,
    "/api/case/ack":             case_ack,
    "/api/case/escalate":        case_escalate,
    "/api/priority/set":         priority_set,
    "/api/finding/create":       finding_create,
    "/api/finding/assign":       finding_assign,
    "/api/finding/resolve":      finding_resolve,
    "/api/finding/raise":        finding_raise,
    "/api/finding/lesson":       finding_to_lesson,
    "/api/task/hold":            task_hold,
    "/api/task/resume":          task_resume,
    "/api/setting/save":         setting_save,
    "/api/llr/improve":          llr_improve,
}
