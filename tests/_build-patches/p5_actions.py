"""Backlog #1-#6 (collaboration, ack, escalation, priority), #7-#10 (findings),
   #17 (root cause), #27/#31 (hold), §36 (settings are editable, not code)."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\actions.py"
src = open(PATH, encoding="utf-8").read()
S = "\u00a7"
D = "\u2014"
RA = "\u2192"


def sub(old, new):
    global src
    assert old in src, "anchor: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1 · case_create learns cross-team routing, priority and TAT
# ══════════════════════════════════════════════════════════════════════════
sub('''    cid, ref = store.open_case(c, typ, pid, pr["code"], d["title"].strip(), val,
                               who["name"], store.today().isoformat(),
                               (d.get("note") or "").strip())''',
'''    # Backlog #1: a case can be raised AT another team. #5/#6: it carries a
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
        _msg(c, cid, "update", d["note"].strip(), who)''')

sub('''    store.log(c, who["name"], _tier(who), "case", cid, "create",
              f"Raised {ref} %(M)s {d['title'].strip()}"
              + (f" %(M)s {gate} approval required (PKR {val:,.0f})" if gate else ""),
              project=pr["name"])
    return {"ok": True, "ref": ref, "id": cid, "gate": gate}''' % {"D": D, "M": "\u00b7"},
'''    store.log(c, who["name"], _tier(who), "case", cid, "create",
              f"Raised {ref} %(M)s {d['title'].strip()}"
              + (f" %(M)s to {to_team}" if to_team else "")
              + (f" %(M)s {gate} approval required (PKR {val:,.0f})" if gate else ""),
              project=pr["name"])
    row = c.execute("SELECT ack_due_at FROM cases WHERE id=?", (cid,)).fetchone()
    return {"ok": True, "ref": ref, "id": cid, "gate": gate,
            "ack_due_at": row["ack_due_at"] if row else None}''' % {"D": D, "M": "\u00b7"})


# ══════════════════════════════════════════════════════════════════════════
# 2 · a decision also lands in the thread
# ══════════════════════════════════════════════════════════════════════════
sub('''    store.log(c, who["name"], _tier(who), "case", cid, outcome, summ, project=pname)
    return {"ok": True}''',
'''    _msg(c, cid, "decision", f"{outcome.upper()}" + (f" %(D)s {reason}" if reason else ""), who)
    store.log(c, who["name"], _tier(who), "case", cid, outcome, summ, project=pname)
    return {"ok": True}''' % {"D": D})


# ══════════════════════════════════════════════════════════════════════════
# 3 · the new verbs
# ══════════════════════════════════════════════════════════════════════════
NEW = '''

# ══════════════════════════════════════════════════════════════════════════
# COLLABORATION  — Haroon's review %(S)s2.1, %(S)s3, %(S)s16.  The largest gap in the
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
    # answering counts as acknowledging %(D)s nobody should have to do both
    if not ca["acknowledged_at"]:
        c.execute("UPDATE cases SET acknowledged_at=?,ack_by=? WHERE id=?",
                  (store.now(), who["name"], cid))
    store.log(c, who["name"], _tier(who), "case", cid, kind,
              f"{ca['ref']} %(D)s {d['body'].strip()[:70]}",
              project=_pname(c, ca["project_id"]), team=who.get("team"))
    return {"ok": True}


def case_ack(c, who, d):
    """Acknowledge receipt. Backlog #3.

    The window is a SETTING, not a constant, because %(S)s36 A leaves open whether
    24 hours means calendar hours, business hours or working days %(D)s and a request
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
              f"{ca['ref']} acknowledged" + (" %(D)s AFTER the window closed" if late else
                                             " inside the window"),
              project=_pname(c, ca["project_id"]), team=who.get("team"),
              blocked=1 if late else 0)
    return {"ok": True, "late": late}


def case_escalate(c, who, d):
    """Climb the ladder. Backlog #4 and #20.

    %(S)s16: "Collaboration should not be limited to junior employees across
    departments." An escalation is not a sharper email %(D)s it is a recorded step
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
    to = (d.get("escalated_to") or "").strip() or \\
        f"{ladder[lvl - 1]}, {ca['to_team'] or 'receiving team'}"
    c.execute("UPDATE cases SET escalation_level=?,escalated_at=?,escalated_to=?,"
              "escalated_by=?,escalation_reason=? WHERE id=?",
              (lvl, store.now(), to, who["name"], reason, cid))
    _msg(c, cid, "escalation", f"Escalated to {to} %(D)s {reason}", who)
    store.log(c, who["name"], _tier(who), "case", cid, "escalate",
              f"{ca['ref']} escalated to {to} (level {lvl}) %(D)s {reason[:60]}",
              project=_pname(c, ca["project_id"]))
    return {"ok": True, "level": lvl, "to": to}


# ══════════════════════════════════════════════════════════════════════════
# PRIORITY  — Backlog #5 / #6.  Priority is business importance. TAT is time.
# They were the same field and the review separated them.
# ══════════════════════════════════════════════════════════════════════════
PRIORITISED = {"case": "cases", "task": "tasks", "finding": "findings",
               "coordination": "coordination", "llr": "llr"}


def priority_set(c, who, d):
    """Change priority mid-life and keep the history %(D)s the review asked for
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
        _msg(c, eid, "update", f"Priority {old} %(RA)s {new}"
             + (f" %(D)s {reason}" if reason else ""), who)
    store.log(c, who["name"], _tier(who), ent, eid, "priority",
              f"Priority {old} %(RA)s {new}" + (f" %(D)s {reason[:60]}" if reason else ""))
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
              f"Finding %(D)s {d['title'].strip()[:60]}"
              + (f" %(M)s recurrence of #{prev}" if prev else "")
              + (" %(M)s NON-COMPLIANT" if d.get("non_compliance") else ""),
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
    tat = int(d["tat_days"]) if str(d.get("tat_days") or "").strip().isdigit() \\
        else f["tat_days"]
    due = store._add_working_days(store.today(), tat).isoformat() if tat else f["due_on"]
    c.execute("UPDATE findings SET responsible_team=?,person_id=?,tat_days=?,due_on=?,"
              "status=CASE WHEN status='open' THEN 'assigned' ELSE status END WHERE id=?",
              (team, person["id"] if person else None, tat, due, fid))
    store.log(c, who["name"], _tier(who), "finding", fid, "assign",
              f"{f['title'][:50]} %(RA)s {team}"
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
                      "resolution cannot be checked on the next visit %(D)s which is "
                      "exactly how the same problem gets found four times.")
    status = (d.get("status") or "resolved").lower()
    if status not in ("resolved", "closed"):
        raise Refused("Outcome is resolved or closed.")
    if f["non_compliance"] and status == "closed" and f["case_id"]:
        ncr = c.execute("SELECT status,ref FROM cases WHERE id=?",
                        (f["case_id"],)).fetchone()
        if ncr and ncr["status"] == "open" and not (d.get("override_reason") or "").strip():
            store.log(c, who["name"], _tier(who), "finding", fid, "resolve",
                      f"BLOCKED %(D)s closing {f['title'][:40]} while {ncr['ref']} is open",
                      project=_pname(c, f["project_id"]), blocked=1)
            raise Refused(f"{ncr['ref']} is still open on the %(S)s16 route.",
                          detail="A non-compliance is closed by the NCR being closed, "
                                 "not by the finding being ticked. Close the NCR, or "
                                 "override with a reason.",
                          gate="ncr_open", overridable=True)
    c.execute("UPDATE findings SET status=?,resolution=?,resolved_by=?,resolved_at=? "
              "WHERE id=?", (status, res, who["name"], store.now(), fid))
    store.log(c, who["name"], _tier(who), "finding", fid, status,
              f"{f['title'][:50]} %(D)s {res[:60]}", project=_pname(c, f["project_id"]),
              team=f["responsible_team"])
    return {"ok": True}


def finding_raise(c, who, d):
    """#9: a finding becomes an RFI, an NCR or a task, and stays linked to the
    visit it came from. Visit %(RA)s Finding %(RA)s Relevant Team %(RA)s RFI / Action."""
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
                  f"{f['title'][:50]} %(RA)s task #{tid} on {team}",
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
        f"{f['category'] or ''} %(D)s {f['location'] or ''}. {f['description'] or ''}".strip(),
        position=1 if as_what == "NCR" else 0,
        origin=f"finding #{fid}", priority=f["priority"], tat_days=f["tat_days"],
        from_team="Architecture", to_team=f["responsible_team"],
        origin_entity="finding", origin_id=fid)
    c.execute("UPDATE findings SET case_id=? WHERE id=?", (cid, fid))
    store.log(c, who["name"], _tier(who), "finding", fid, "raise_" + as_what.lower(),
              f"{f['title'][:50]} %(RA)s {ref}", project=pr["name"],
              team=f["responsible_team"])
    return {"ok": True, "ref": ref, "case_id": cid}


def finding_to_lesson(c, who, d):
    """A finding that keeps coming back is a lesson, not a defect. #10 %(RA)s %(S)s7.6."""
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
              f"On hold %(D)s {reason[:70]}", project=_pname(c, t["project_id"]),
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
              f"Resumed after {days}d on hold %(D)s {(t['hold_reason'] or '')[:50]}",
              project=_pname(c, t["project_id"]), team=t["team"])
    return {"ok": True, "hold_days": days}


# ══════════════════════════════════════════════════════════════════════════
# SETTINGS  — %(S)s36.  "Should not be hard-coded until the business definition is
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
              f"{row['label']}: {old} %(RA)s {val}"
              + (" %(D)s CONFIRMED" if confirm and not row["confirmed"] else "")
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
              f"{l['title'][:50]} %(D)s improvement {st}"
              + (f": {d['note'].strip()[:50]}" if d.get("note") else ""),
              project=_pname(c, l["project_id"]) if l["project_id"] else None)
    return {"ok": True}
''' % {"S": S, "D": D, "RA": RA, "M": "\u00b7"}

sub('''# ══════════════════════════════════════════════════════════════════════════
DISPATCH = {''', NEW + '''

# ══════════════════════════════════════════════════════════════════════════
DISPATCH = {''')


# ══════════════════════════════════════════════════════════════════════════
# 4 · llr_create learns the root-cause fields
# ══════════════════════════════════════════════════════════════════════════
sub('''    c.execute("INSERT INTO llr(project_id,stage,discipline,category,title,detail,"
              "impact,raised_by,raised_at,source,origin_entity,origin_id,status)"
              " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'open')",
              (pid, stage, d.get("discipline") or None, d.get("category") or "General",
               d["title"].strip(), d["detail"].strip(), (d.get("impact") or "").strip(),
               who["name"], store.today().isoformat(), "Design Manual %(SS)s7.6",
               d.get("origin_entity") or None,
               int(d["origin_id"]) if str(d.get("origin_id") or "").isdigit() else None))''' % {"SS": S},
'''    # #15 — the head sees it the moment it is raised; Audit from the status the
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
               who["name"], store.today().isoformat(), "Design Manual %(SS)s7.6",
               d.get("origin_entity") or None,
               int(d["origin_id"]) if str(d.get("origin_id") or "").isdigit() else None,
               (d.get("root_cause") or "").strip() or None,
               (d.get("delay_kind") or "").strip() or None,
               (d.get("delay_owner") or "").strip() or None,
               int(d["delay_days"]) if str(d.get("delay_days") or "").strip().isdigit()
               else None,
               (d.get("dependency") or "").strip() or None,
               (d.get("preventive_action") or "").strip() or None,
               d.get("discipline") or "Architecture", head, audit, prio))''' % {"SS": S})

# ruling can also open Audit's view
sub('''    c.execute("UPDATE llr SET status=?,ruling=?,ruled_by=?,ruled_at=? WHERE id=?",
              (status, ruling, who["name"], store.now(), lid))''',
'''    c.execute("UPDATE llr SET status=?,ruling=?,ruled_by=?,ruled_at=? WHERE id=?",
              (status, ruling, who["name"], store.now(), lid))
    if (status == "ruled" and not l["audit_notified_at"]
            and store.setting_bool(c, "lessons.notify_audit", True)
            and store.setting(c, "lessons.audit_from_status", "ruled") in
            ("open", "ruled")):
        c.execute("UPDATE llr SET audit_notified_at=? WHERE id=?", (store.now(), lid))''')

# ══════════════════════════════════════════════════════════════════════════
# 5 · coord_create gains priority + acknowledgement
# ══════════════════════════════════════════════════════════════════════════
sub('''    c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,ask,"
              "sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
              (pid, int(d.get("stage") or 0), team, d["to_lane"].strip(),
               d["ask"].strip(), sla, store.today().isoformat()))''',
'''    prio = (d.get("priority") or "").strip() or store.setting(
        c, "priority.default", "Medium")
    c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,ask,"
              "sla_days,priority,ack_due_at,opened_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (pid, int(d.get("stage") or 0), team, d["to_lane"].strip(),
               d["ask"].strip(), sla, prio,
               store.ack_due(c).isoformat(timespec="seconds"),
               store.today().isoformat()))''')

# ══════════════════════════════════════════════════════════════════════════
# 6 · dispatch
# ══════════════════════════════════════════════════════════════════════════
sub('''    "/api/case/withdraw":        case_withdraw,
}''',
'''    "/api/case/withdraw":        case_withdraw,
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
}''')

open(PATH, "w", encoding="utf-8").write(src)
print("actions.py patched")
