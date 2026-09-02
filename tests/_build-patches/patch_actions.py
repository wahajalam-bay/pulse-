"""Patch actions.py: connect the flows, add the eleven missing write verbs."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\actions.py"
src = open(PATH, encoding="utf-8").read()

S = "\u00a7"
D = "\u2014"


def sub(old, new):
    global src
    assert old in src, "anchor missing: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1 · initiating a stage stamps the §4.2 template onto the checklist
# ══════════════════════════════════════════════════════════════════════════
sub('''    # the mandatory checklist for this stage — Manual %(S)s4.1
    c.execute("INSERT INTO checklists(project_id,stage,created_at) VALUES(?,?,?)",
              (pid, stage, store.now()))
''' % {"S": S},
    '''    # The mandatory checklist for this stage — Manual %(S)s4.1 — stamped from the
    # %(S)s4.2 template, so it arrives with content instead of as an empty page a
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
''' % {"S": S})

sub('''              f"Initiated stage {stage} on {pname} %(D)s {made} tasks from catalog"''' % {"D": D},
    '''              f"Initiated stage {stage} on {pname} %(D)s {made} tasks from catalog, "
              f"{len(tpl)} checks from the %(S)s4.2 template"''' % {"D": D, "S": S})

# ══════════════════════════════════════════════════════════════════════════
# 2 · case_create goes through the shared route instantiator
# ══════════════════════════════════════════════════════════════════════════
sub('''    route = store.ROUTES[typ]
    ref = _next_ref(c, typ, pr["code"])
    c.execute("INSERT INTO cases(ref,type,project_id,title,value_pkr,position,status,"
              "raised_by,raised_at,note) VALUES(?,?,?,?,?,0,'open',?,?,?)",
              (ref, typ, pid, d["title"].strip(), val, who["name"],
               store.today().isoformat(), (d.get("note") or "").strip()))
    cid = c.execute("SELECT id FROM cases WHERE ref=?", (ref,)).fetchone()["id"]
    for idx, (label, owner, sla) in enumerate(route["lanes"]):
        c.execute("INSERT INTO case_lanes(case_id,idx,label,owner_lane,sla_days,"
                  "is_stub,entered_at) VALUES(?,?,?,?,?,?,?)",
                  (cid, idx, label, owner, sla, int(store.is_stub(owner)),
                   store.now() if idx == 0 else None))
''',
    '''    cid, ref = store.open_case(c, typ, pid, pr["code"], d["title"].strip(), val,
                               who["name"], store.today().isoformat(),
                               (d.get("note") or "").strip())
''')

# ══════════════════════════════════════════════════════════════════════════
# 3 · a site visit that finds non-compliance RAISES the NCR
# ══════════════════════════════════════════════════════════════════════════
sub('''    store.log(c, who["name"], _tier(who), "visit", vid, "create",
              f"Site visit %(D)s {d['findings'].strip()[:70]}"
              + (" %(M)s NON-COMPLIANCE RAISED" if nc else ""), project=pname)
    return {"ok": True, "id": vid, "non_compliance": bool(nc)}''' % {"D": D, "M": "·"},
    '''    # Manual %(S)s16: non-compliance is not a checkbox. It raises an NCR on a route
    # with a clock, opens the QA/QC re-inspection ask, and shows up in the
    # approvals inbox as work waiting on a named lane.
    ref = None
    if nc:
        code = c.execute("SELECT code FROM projects WHERE id=?", (pid,)).fetchone()["code"]
        cid, ref = store.open_case(
            c, "NCR", pid, code,
            (d.get("title") or d["findings"].strip().split(".")[0])[:90],
            None, who["name"], d.get("visited_on") or store.today().isoformat(),
            d["findings"].strip(), position=1, origin=f"site visit #{vid}")
        c.execute("INSERT INTO coordination(project_id,stage,from_team,to_lane,ask,"
                  "sla_days,opened_at) VALUES(?,?,?,?,?,?,?)",
                  (pid, 13, "Architecture", "QA/QC",
                   f"{ref} %(D)s joint re-inspection after rectification", 5,
                   store.today().isoformat()))
        store.log(c, who["name"], _tier(who), "case", cid, "create",
                  f"{ref} raised automatically from site visit #{vid}", project=pname)
    store.log(c, who["name"], _tier(who), "visit", vid, "create",
              f"Site visit %(D)s {d['findings'].strip()[:70]}"
              + (f" %(D)s NON-COMPLIANCE, {ref} raised" if nc else ""), project=pname)
    return {"ok": True, "id": vid, "non_compliance": bool(nc), "ref": ref}''' % {"D": D, "S": S})

# ══════════════════════════════════════════════════════════════════════════
# 4 · a transmittal carries the sheet list, and issuing changes the register
# ══════════════════════════════════════════════════════════════════════════
sub('''    n = c.execute("SELECT COUNT(*) FROM transmittals").fetchone()[0]
    ref = f"TR-{pr['code']}-{200 + n + 1}"
    cnt = c.execute("SELECT COUNT(*) FROM drawings WHERE project_id=?", (pid,)).fetchone()[0]
    c.execute("INSERT INTO transmittals(ref,project_id,phase,issued_to,drawing_count,"
              "note,issued_at,issued_by) VALUES(?,?,?,?,?,?,?,?)",
              (ref, pid, d["phase"], d["issued_to"].strip(),
               int(d.get("drawing_count") or cnt), (d.get("note") or "").strip(),
               store.now(), who["name"]))
    tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]''',
    '''    # Which sheets, at which revision. A transmittal with only a count on it is a
    # number; %(S)s5 makes the sheet list the contractual fact.
    ids = d.get("drawing_ids") or []
    if isinstance(ids, str):
        ids = [x for x in ids.replace(" ", "").split(",") if x.isdigit()]
    sheets = [dict(r) for r in c.execute(
        "SELECT * FROM drawings WHERE project_id=?", (pid,))]
    if ids:
        keep = {int(x) for x in ids}
        sheets = [s for s in sheets if s["id"] in keep]
    if not sheets and not reason:
        raise Refused("Nothing to issue %(D)s no drawing on this project is selected.",
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
                       f"Issued for construction on {ref}", store.now(), who["name"]))''' % {"S": S, "D": D})

sub('''    store.log(c, who["name"], _tier(who), "transmittal", tid,
              "issue_override" if reason else "issue",
              f"{ref} %(D)s {d['phase']} issued to {d['issued_to'].strip()}"
              + (f" %(M)s OVERRIDE: {reason}" if reason else ""), project=pr["name"])
    return {"ok": True, "ref": ref}''' % {"D": D, "M": "·"},
    '''    store.log(c, who["name"], _tier(who), "transmittal", tid,
              "issue_override" if reason else "issue",
              f"{ref} %(D)s {d['phase']}, {len(sheets)} sheets to "
              f"{d['issued_to'].strip()}"
              + (f" %(M)s OVERRIDE: {reason}" if reason else ""), project=pr["name"])
    return {"ok": True, "ref": ref, "id": tid, "sheets": len(sheets)}''' % {"D": D, "M": "·"})

# ══════════════════════════════════════════════════════════════════════════
# 5 · the new write verbs
# ══════════════════════════════════════════════════════════════════════════
NEW = '''

# ══════════════════════════════════════════════════════════════════════════
# DRAWING REVISIONS  — Manual %(S)s5
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
        raise Refused("A revision needs a reason %(D)s that is what the register is for.")
    c.execute("UPDATE drawings SET revision=?,status=?,link=? WHERE id=?",
              (nxt, status, link, did))
    c.execute("INSERT INTO drawing_revs(drawing_id,revision,status,link,note,at,by_whom)"
              " VALUES(?,?,?,?,?,?,?)",
              (did, nxt, status, link, note, store.now(), who["name"]))
    store.log(c, who["name"], _tier(who), "drawing", did, "revise",
              f"{dw['number']} Rev {cur} %(RA)s {nxt} %(D)s {note[:70]}",
              project=_pname(c, dw["project_id"]))
    return {"ok": True, "revision": nxt}


# ══════════════════════════════════════════════════════════════════════════
# THE AUTHORITY FILE  — Manual %(S)s7 and %(S)s17
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
               f"{ref} %(D)s {d['title'].strip()}", sla, day))
    coid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("UPDATE authority SET coordination_id=? WHERE id=?", (coid, aid))
    store.log(c, who["name"], _tier(who), "authority", aid, "submit",
              f"{ref} %(D)s {d['kind']} to {d['authority'].strip()}: "
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
        raise Refused("Record what the authority actually said %(D)s an unrecorded "
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
              f"{a['ref']} %(RA)s {status}" + (f" %(D)s {(obs or cond)[:70]}" if (obs or cond) else ""),
              project=_pname(c, a["project_id"]))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# LESSONS LEARNED  — Manual %(S)s7.6.  The loop that changes the next project.
# ══════════════════════════════════════════════════════════════════════════
def llr_create(c, who, d):
    _req(d, "title", "detail")
    pid = int(d["project_id"]) if str(d.get("project_id") or "").isdigit() else None
    stage = int(d["stage"]) if str(d.get("stage") or "").isdigit() else None
    c.execute("INSERT INTO llr(project_id,stage,discipline,category,title,detail,"
              "impact,raised_by,raised_at,source,origin_entity,origin_id,status)"
              " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'open')",
              (pid, stage, d.get("discipline") or None, d.get("category") or "General",
               d["title"].strip(), d["detail"].strip(), (d.get("impact") or "").strip(),
               who["name"], store.today().isoformat(), "Design Manual %(S)s7.6",
               d.get("origin_entity") or None,
               int(d["origin_id"]) if str(d.get("origin_id") or "").isdigit() else None))
    lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    store.log(c, who["name"], _tier(who), "llr", lid, "create",
              f"Lesson raised %(D)s {d['title'].strip()[:70]}",
              project=_pname(c, pid) if pid else None)
    return {"ok": True, "id": lid}


def llr_rule(c, who, d):
    """Rule on a lesson. %(S)s7.6 names Head ZD; PM %(S)s8.3 defines a competing process
    and neither document references the other. Recorded, not silently resolved."""
    lid = int(d.get("id") or 0)
    l = c.execute("SELECT * FROM llr WHERE id=?", (lid,)).fetchone()
    if not l:
        raise Refused("No such lesson.")
    if _tier(who) > 1:
        raise Refused("Only a senior manager or the department head can rule on a "
                      "lesson %(D)s the ruling changes what every future project is "
                      "checked against.")
    ruling = (d.get("ruling") or "").strip()
    if not ruling:
        raise Refused("A ruling with no text is not a ruling.")
    status = (d.get("status") or "ruled").lower()
    c.execute("UPDATE llr SET status=?,ruling=?,ruled_by=?,ruled_at=? WHERE id=?",
              (status, ruling, who["name"], store.now(), lid))
    store.log(c, who["name"], _tier(who), "llr", lid, status,
              f"{l['title'][:60]} %(RA)s {status}: {ruling[:70]}",
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
                  f"BLOCKED %(D)s {l['title'][:50]} promoted before it was ruled on",
                  blocked=1)
        raise Refused("This lesson has not been ruled on yet.",
                      detail="%(S)s7.6 puts the ruling before adoption. Rule on it first, "
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
              f"Stage {stage} checklist template %(RA)s {d['text'].strip()[:60]}")
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
              f"Retired from stage {t['stage']}: {t['text'][:50]} %(D)s {reason[:60]}")
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
        blocks.append("no as-built transmittal has been issued (%(S)s18)")
    if ncr:
        blocks.append(f"{ncr} NCRs are still open (%(S)s16)")
    if blocks and not reason:
        store.log(c, who["name"], _tier(who), "project", pid, "close",
                  f"BLOCKED %(D)s closeout of {pr['name']}: " + "; ".join(blocks),
                  project=pr["name"], blocked=1)
        raise Refused("This project cannot be closed out yet.",
                      missing=blocks, gate="closeout", overridable=True)
    c.execute("UPDATE projects SET status='Closed' WHERE id=?", (pid,))
    store.log(c, who["name"], _tier(who), "project", pid,
              "close_override" if reason else "close",
              f"Closed out {pr['name']}" + (f" %(D)s OVERRIDE: {reason}" if reason else ""),
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
              (store.now(), ca["ref"] + "%%"))
    store.log(c, who["name"], _tier(who), "case", cid, "withdraw",
              f"{ca['ref']} withdrawn %(D)s {reason[:70]}",
              project=_pname(c, ca["project_id"]))
    return {"ok": True}
''' % {"S": S, "D": D, "RA": "\u2192"}

sub('''# ══════════════════════════════════════════════════════════════════════════
DISPATCH = {''', NEW + '''

# ══════════════════════════════════════════════════════════════════════════
DISPATCH = {''')

sub('''    "/api/note/add":             note_add,
}''',
    '''    "/api/note/add":             note_add,
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
}''')

open(PATH, "w", encoding="utf-8").write(src)
print("actions.py patched")
