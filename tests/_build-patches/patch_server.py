"""Patch server.py: search, the universal entity endpoint, notifications, registers."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\server.py"
src = open(PATH, encoding="utf-8").read()

S = "\u00a7"


def sub(old, new):
    global src
    assert old in src, "anchor missing: " + old[:70]
    src = src.replace(old, new, 1)


# ── route table in the module docstring ──
sub('''  GET  <MOUNT>/api/health
''',
    '''  GET  <MOUNT>/api/search?q=     one box over every register
  GET  <MOUNT>/api/entity/<k>/<id> the record, its context and its history
  GET  <MOUNT>/api/notifications what is waiting on the signed-in person
  GET  <MOUNT>/api/llr           lessons learned register
  GET  <MOUNT>/api/authority     the authority file
  GET  <MOUNT>/api/site          visits, NCRs and inspections
  GET  <MOUNT>/api/template      the §4.2 stage checklist template
  GET  <MOUNT>/api/health
''')

# ══════════════════════════════════════════════════════════════════════════
# 1 · GET dispatch — the new endpoints
# ══════════════════════════════════════════════════════════════════════════
sub('''            if p == "/api/catalog":''',
    '''            if p == "/api/search":
                return self._json(200, self._search(c))

            m = re.match(r"^/api/entity/([a-z_]+)/(\\d+)$", p)
            if m:
                return self._json(200, self._entity(c, m.group(1), int(m.group(2)), who))

            if p == "/api/notifications":
                return self._json(200, self._notify(c, who))

            if p == "/api/llr":
                rows = [dict(r) for r in c.execute(
                    "SELECT l.*, p.name pname, p.code pcode FROM llr l "
                    "LEFT JOIN projects p ON p.id=l.project_id "
                    "ORDER BY (l.status='open') DESC, l.raised_at DESC")]
                tpl = [dict(r) for r in c.execute(
                    "SELECT * FROM checklist_templates WHERE active=1 ORDER BY stage,seq")]
                agg = {}
                for r in rows:
                    agg[r["status"]] = agg.get(r["status"], 0) + 1
                return self._json(200, {
                    "rows": rows, "template": tpl, "summary": agg,
                    "from_lessons": sum(1 for t in tpl if t["llr_id"]),
                    "stages": {s: n for s, n, _p, _d in catalog.STAGES}})

            if p == "/api/template":
                return self._json(200, {"rows": [dict(r) for r in c.execute(
                    "SELECT * FROM checklist_templates ORDER BY stage,seq")],
                    "stages": {s: n for s, n, _p, _d in catalog.STAGES}})

            if p == "/api/authority":
                return self._json(200, {"rows": [
                    dict(r, age=age_days(r["submitted_on"]))
                    for r in c.execute(
                        "SELECT a.*, p.name pname, p.code pcode FROM authority a "
                        "LEFT JOIN projects p ON p.id=a.project_id "
                        "ORDER BY a.submitted_on DESC")]})

            if p == "/api/site":
                return self._json(200, self._site(c))

            if p == "/api/documents":
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                sql = ("SELECT d.*, p.name pname FROM documents d "
                       "LEFT JOIN projects p ON p.id=d.project_id WHERE 1=1")
                args = []
                if q.get("entity"):
                    sql += " AND d.entity=?"; args.append(q["entity"][0])
                if q.get("id"):
                    sql += " AND d.entity_id=?"; args.append(int(q["id"][0]))
                if q.get("project"):
                    sql += " AND d.project_id=?"; args.append(int(q["project"][0]))
                sql += " ORDER BY d.id DESC LIMIT 300"
                return self._json(200, {"rows": [dict(x) for x in c.execute(sql, args)]})

            if p == "/api/catalog":''')

# drawings endpoint gains revisions and sheet lists
sub('''                dw = [dict(x) for x in c.execute(
                    "SELECT * FROM drawings WHERE project_id=? ORDER BY number", (pid,))]
                tr = [dict(x) for x in c.execute(
                    "SELECT * FROM transmittals WHERE project_id=? ORDER BY issued_at DESC",
                    (pid,))]
                return self._json(200, {"drawings": dw, "transmittals": tr})''',
    '''                dw = [dict(x) for x in c.execute(
                    "SELECT * FROM drawings WHERE project_id=? ORDER BY discipline,number",
                    (pid,))]
                revs = {}
                for r in c.execute(
                        "SELECT r.* FROM drawing_revs r JOIN drawings d ON d.id=r.drawing_id"
                        " WHERE d.project_id=? ORDER BY r.id", (pid,)):
                    revs.setdefault(r["drawing_id"], []).append(dict(r))
                for x in dw:
                    x["revs"] = revs.get(x["id"], [])
                tr = [dict(x) for x in c.execute(
                    "SELECT * FROM transmittals WHERE project_id=? ORDER BY issued_at DESC",
                    (pid,))]
                sheets = {}
                for r in c.execute(
                        "SELECT td.transmittal_id tid, d.number, d.title, td.revision, "
                        "d.id did FROM transmittal_drawings td "
                        "JOIN drawings d ON d.id=td.drawing_id "
                        "JOIN transmittals t ON t.id=td.transmittal_id "
                        "WHERE t.project_id=? ORDER BY d.number", (pid,)):
                    sheets.setdefault(r["tid"], []).append(dict(r))
                for x in tr:
                    x["sheets"] = sheets.get(x["id"], [])
                return self._json(200, {"drawings": dw, "transmittals": tr})''')

# catalog endpoint gains per-workflow provenance
sub('''                return self._json(200, {
                    "rows": [dict(r) for r in rows],
                    "stats": catalog.stats(),''',
    '''                return self._json(200, {
                    "rows": [dict(r) for r in rows],
                    "workflows": catalog.workflows(),
                    "booklet": catalog.BOOKLET,
                    "stats": catalog.stats(),''')

# ══════════════════════════════════════════════════════════════════════════
# 2 · the payload builders
# ══════════════════════════════════════════════════════════════════════════
BUILDERS = '''
    # ── one box over every register ──
    def _search(self, c):
        """Search was on the "not built" list. It is the difference between a
        system you navigate and a system you ask. One query, every register."""
        from urllib.parse import urlparse, parse_qs
        q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0].strip()
        if len(q) < 2:
            return {"q": q, "groups": []}
        like = "%%" + q.replace("%%", "") + "%%"
        G = []

        def group(kind, label, sql, args, row):
            hits = [row(r) for r in c.execute(sql, args)]
            if hits:
                G.append({"kind": kind, "label": label, "rows": hits})

        group("project", "Projects",
              "SELECT * FROM projects WHERE name LIKE ? OR code LIKE ? OR city LIKE ? "
              "ORDER BY is_bau,name LIMIT 8", (like, like, like),
              lambda r: {"id": r["id"], "title": r["name"],
                         "sub": f"{r['code']} %(M)s {r['kind']} %(M)s {r['city']} %(M)s {r['status']}"})
        group("case", "Cases",
              "SELECT ca.*, p.name pname FROM cases ca LEFT JOIN projects p "
              "ON p.id=ca.project_id WHERE ca.ref LIKE ? OR ca.title LIKE ? "
              "ORDER BY ca.status, ca.raised_at DESC LIMIT 10", (like, like),
              lambda r: {"id": r["id"], "title": f"{r['ref']} %(M)s {r['title']}",
                         "sub": f"{r['pname'] or ''} %(M)s {r['status']}"})
        group("task", "Steps and tasks",
              "SELECT t.*, p.name pname FROM tasks t LEFT JOIN projects p "
              "ON p.id=t.project_id WHERE t.title LIKE ? OR t.workflow LIKE ? "
              "ORDER BY t.status!='running', t.planned_ed LIMIT 12", (like, like),
              lambda r: {"id": r["id"], "title": r["title"],
                         "sub": f"{r['pname'] or ''} %(M)s stage {r['stage']} %(M)s "
                                f"{r['team']} %(M)s {r['status']}"})
        group("drawing", "Drawings",
              "SELECT d.*, p.name pname FROM drawings d LEFT JOIN projects p "
              "ON p.id=d.project_id WHERE d.number LIKE ? OR d.title LIKE ? "
              "ORDER BY d.number LIMIT 10", (like, like),
              lambda r: {"id": r["id"], "title": f"{r['number']} %(M)s {r['title']}",
                         "sub": f"{r['pname'] or ''} %(M)s Rev {r['revision']} %(M)s {r['status']}"})
        group("transmittal", "Transmittals",
              "SELECT t.*, p.name pname FROM transmittals t LEFT JOIN projects p "
              "ON p.id=t.project_id WHERE t.ref LIKE ? OR t.phase LIKE ? "
              "OR t.issued_to LIKE ? ORDER BY t.issued_at DESC LIMIT 8",
              (like, like, like),
              lambda r: {"id": r["id"], "title": f"{r['ref']} %(M)s {r['phase']}",
                         "sub": f"{r['pname'] or ''} %(M)s to {r['issued_to']}"})
        group("person", "People",
              "SELECT * FROM people WHERE name LIKE ? OR designation LIKE ? "
              "OR team LIKE ? ORDER BY tier,name LIMIT 10", (like, like, like),
              lambda r: {"id": r["id"], "title": r["name"],
                         "sub": f"{r['designation']} %(M)s {r['team']}"})
        group("llr", "Lessons learned",
              "SELECT * FROM llr WHERE title LIKE ? OR detail LIKE ? OR category LIKE ? "
              "ORDER BY raised_at DESC LIMIT 8", (like, like, like),
              lambda r: {"id": r["id"], "title": r["title"],
                         "sub": f"{r['category'] or ''} %(M)s {r['status']}"})
        group("coordination", "Open asks",
              "SELECT co.*, p.name pname FROM coordination co LEFT JOIN projects p "
              "ON p.id=co.project_id WHERE co.closed_at IS NULL AND (co.ask LIKE ? "
              "OR co.to_lane LIKE ?) ORDER BY co.opened_at LIMIT 8", (like, like),
              lambda r: {"id": r["id"], "title": r["ask"],
                         "sub": f"{r['pname'] or ''} %(M)s waiting on {r['to_lane']}"})
        group("authority", "Authority file",
              "SELECT a.*, p.name pname FROM authority a LEFT JOIN projects p "
              "ON p.id=a.project_id WHERE a.ref LIKE ? OR a.title LIKE ? "
              "OR a.authority LIKE ? ORDER BY a.submitted_on DESC LIMIT 8",
              (like, like, like),
              lambda r: {"id": r["id"], "title": f"{r['ref']} %(M)s {r['title']}",
                         "sub": f"{r['pname'] or ''} %(M)s {r['authority']} %(M)s {r['status']}"})
        group("visit", "Site visits",
              "SELECT v.*, p.name pname FROM site_visits v LEFT JOIN projects p "
              "ON p.id=v.project_id WHERE v.findings LIKE ? "
              "ORDER BY v.visited_on DESC LIMIT 6", (like,),
              lambda r: {"id": r["id"], "title": (r["findings"] or "")[:80],
                         "sub": f"{r['pname'] or ''} %(M)s {r['visited_on']}"})
        group("product", "Catalog steps",
              "SELECT * FROM products WHERE step LIKE ? OR workflow LIKE ? "
              "ORDER BY stage,seq LIMIT 12", (like, like),
              lambda r: {"id": r["id"], "title": r["step"],
                         "sub": f"{r['workflow']} %(M)s stage {r['stage']} %(M)s {r['team']}"})
        return {"q": q, "groups": G,
                "total": sum(len(g["rows"]) for g in G)}

    # ── the record, its context, and everything that happened to it ──
    def _entity(self, c, kind, eid, who):
        """One endpoint behind every click. Whatever you opened, you get the row,
        the project it belongs to, its notes, its attached documents and its slice
        of the ledger — so nothing in this system is a dead end."""
        one = lambda sql, *a: c.execute(sql, a).fetchone()
        many = lambda sql, *a: [dict(r) for r in c.execute(sql, a)]
        rec, extra, pid, title, sub = None, {}, None, "", ""

        if kind == "project":
            rec = one("SELECT * FROM projects WHERE id=?", eid)
            if rec:
                pid = eid
                title, sub = rec["name"], f"{rec['code']} · {rec['kind']} · {rec['city']}"
                extra = {
                    "stages": many("SELECT * FROM project_stages WHERE project_id=? "
                                   "ORDER BY stage", eid),
                    "intake": dict(one("SELECT * FROM intake WHERE project_id=?", eid) or {}),
                    "counts": {
                        "tasks": one("SELECT COUNT(*) n FROM tasks WHERE project_id=?", eid)["n"],
                        "open_cases": one("SELECT COUNT(*) n FROM cases WHERE project_id=? "
                                          "AND status='open'", eid)["n"],
                        "drawings": one("SELECT COUNT(*) n FROM drawings WHERE project_id=?", eid)["n"],
                        "transmittals": one("SELECT COUNT(*) n FROM transmittals WHERE project_id=?", eid)["n"],
                        "visits": one("SELECT COUNT(*) n FROM site_visits WHERE project_id=?", eid)["n"],
                        "asks": one("SELECT COUNT(*) n FROM coordination WHERE project_id=? "
                                    "AND closed_at IS NULL", eid)["n"],
                        "lessons": one("SELECT COUNT(*) n FROM llr WHERE project_id=?", eid)["n"],
                    },
                    "stage_names": {s: n for s, n, _p, _d in catalog.STAGES},
                }

        elif kind == "task":
            rec = one("SELECT * FROM tasks WHERE id=?", eid)
            if rec:
                pid = rec["project_id"]
                title = rec["title"]
                sub = f"{rec['workflow'] or ''} · stage {rec['stage']} · {rec['team']}"
                prod = one("SELECT * FROM products WHERE id=?", rec["product_id"]) \\
                    if rec["product_id"] else None
                extra = {
                    "view": task_view(rec),
                    "product": dict(prod) if prod else None,
                    "person": dict(one("SELECT * FROM people WHERE id=?",
                                       rec["person_id"]) or {}) if rec["person_id"] else None,
                    "siblings": many("SELECT * FROM tasks WHERE project_id=? AND stage=? "
                                     "AND team=? ORDER BY seq LIMIT 40",
                                     rec["project_id"], rec["stage"], rec["team"]),
                    "asks": many("SELECT * FROM coordination WHERE task_id=?", eid),
                }

        elif kind == "case":
            rec = one("SELECT ca.*, p.name pname, p.code pcode FROM cases ca "
                      "LEFT JOIN projects p ON p.id=ca.project_id WHERE ca.id=?", eid)
            if rec:
                pid = rec["project_id"]
                title = f"{rec['ref']} · {rec['title']}"
                route = store.ROUTES.get(rec["type"], {})
                sub = f"{route.get('label', rec['type'])} · {rec['status']}"
                lanes = many("SELECT * FROM case_lanes WHERE case_id=? ORDER BY idx", eid)
                for l in lanes:
                    l["age"] = age_days(l["entered_at"]) if l["entered_at"] and not l["left_at"] else None
                extra = {"lanes": lanes, "route": route.get("label"),
                         "source": route.get("source"), "position": rec["position"],
                         "asks": many("SELECT * FROM coordination WHERE ask LIKE ?",
                                      rec["ref"] + "%%")}

        elif kind == "drawing":
            rec = one("SELECT * FROM drawings WHERE id=?", eid)
            if rec:
                pid = rec["project_id"]
                title = f"{rec['number']} · {rec['title']}"
                sub = f"{rec['discipline']} · Rev {rec['revision']} · {rec['status']}"
                extra = {
                    "revs": many("SELECT * FROM drawing_revs WHERE drawing_id=? "
                                 "ORDER BY id", eid),
                    "transmittals": many(
                        "SELECT t.*, td.revision issued_rev FROM transmittals t "
                        "JOIN transmittal_drawings td ON td.transmittal_id=t.id "
                        "WHERE td.drawing_id=? ORDER BY t.issued_at DESC", eid),
                }

        elif kind == "transmittal":
            rec = one("SELECT * FROM transmittals WHERE id=?", eid)
            if rec:
                pid = rec["project_id"]
                title = f"{rec['ref']} · {rec['phase']}"
                sub = f"Issued to {rec['issued_to']}"
                extra = {"sheets": many(
                    "SELECT d.*, td.revision issued_rev FROM transmittal_drawings td "
                    "JOIN drawings d ON d.id=td.drawing_id WHERE td.transmittal_id=? "
                    "ORDER BY d.number", eid)}

        elif kind == "person":
            rec = one("SELECT * FROM people WHERE id=?", eid)
            if rec:
                title, sub = rec["name"], f"{rec['designation']} · {rec['team']}"
                ts = many("SELECT t.*, p.name pname FROM tasks t LEFT JOIN projects p "
                          "ON p.id=t.project_id WHERE t.person_id=? "
                          "ORDER BY t.status='done', t.planned_ed LIMIT 60", eid)
                done = [t for t in ts if t["status"] == "done" and t["baseline_days"]]
                extra = {"tasks": ts, "kpi": {
                    "open": sum(1 for t in ts if t["status"] != "done"),
                    "done": len(done),
                    "on_time": sum(1 for t in done
                                   if (t["own_days"] or 0) <= t["baseline_days"]),
                    "revisions": sum(t["revision"] or 0 for t in ts)}}

        elif kind == "coordination":
            rec = one("SELECT co.*, p.name pname FROM coordination co "
                      "LEFT JOIN projects p ON p.id=co.project_id WHERE co.id=?", eid)
            if rec:
                pid = rec["project_id"]
                title, sub = rec["ask"], f"{rec['from_team']} → {rec['to_lane']}"
                extra = {"age": age_days(rec["opened_at"]),
                         "external": store.is_stub(rec["to_lane"])}

        elif kind == "obligation":
            rec = one("SELECT o.*, p.name pname FROM obligations o "
                      "LEFT JOIN projects p ON p.id=o.project_id WHERE o.id=?", eid)
            if rec:
                pid = rec["project_id"]
                title, sub = rec["label"], f"Due {rec['due_on']} · {rec['source'] or ''}"
                extra = {"history": many(
                    "SELECT * FROM obligations WHERE kind=? AND "
                    "(project_id=? OR (project_id IS NULL AND ? IS NULL)) "
                    "ORDER BY due_on DESC LIMIT 14",
                    rec["kind"], rec["project_id"], rec["project_id"])}

        elif kind == "visit":
            rec = one("SELECT v.*, p.name pname FROM site_visits v "
                      "LEFT JOIN projects p ON p.id=v.project_id WHERE v.id=?", eid)
            if rec:
                pid = rec["project_id"]
                title = f"Site visit · {rec['visited_on']}"
                sub = f"{rec['by_whom']} · {rec['photos'] or 0} photos"
                extra = {"ncr": many(
                    "SELECT * FROM cases WHERE project_id=? AND type='NCR' "
                    "AND raised_at<=? ORDER BY id DESC LIMIT 5",
                    rec["project_id"], rec["visited_on"]) if rec["non_compliance"] else []}

        elif kind == "llr":
            rec = one("SELECT l.*, p.name pname FROM llr l LEFT JOIN projects p "
                      "ON p.id=l.project_id WHERE l.id=?", eid)
            if rec:
                pid = rec["project_id"]
                title, sub = rec["title"], f"{rec['category'] or ''} · {rec['status']}"
                extra = {"template": dict(one(
                    "SELECT * FROM checklist_templates WHERE id=?",
                    rec["template_id"]) or {}) if rec["template_id"] else None,
                    "stage_names": {s: n for s, n, _p, _d in catalog.STAGES}}

        elif kind == "authority":
            rec = one("SELECT a.*, p.name pname FROM authority a LEFT JOIN projects p "
                      "ON p.id=a.project_id WHERE a.id=?", eid)
            if rec:
                pid = rec["project_id"]
                title = f"{rec['ref']} · {rec['title']}"
                sub = f"{rec['authority']} · {rec['kind']} · {rec['status']}"
                extra = {"age": age_days(rec["submitted_on"]),
                         "ask": dict(one("SELECT * FROM coordination WHERE id=?",
                                         rec["coordination_id"]) or {})
                         if rec["coordination_id"] else None}

        elif kind == "product":
            rec = one("SELECT * FROM products WHERE id=?", eid)
            if rec:
                title = rec["step"]
                sub = f"{rec['workflow']} · stage {rec['stage']} · {rec['team']}"
                extra = {"instances": many(
                    "SELECT t.*, p.name pname FROM tasks t LEFT JOIN projects p "
                    "ON p.id=t.project_id WHERE t.product_id=? ORDER BY p.name", eid)}

        if not rec:
            return {"error": "not found", "kind": kind, "id": eid}

        rec = dict(rec)
        project = dict(one("SELECT * FROM projects WHERE id=?", pid) or {}) if pid else None
        notes = many("SELECT * FROM notes WHERE entity=? AND entity_id=? "
                     "ORDER BY id DESC LIMIT 40", kind, eid)
        docs = many("SELECT * FROM documents WHERE entity=? AND entity_id=? "
                    "ORDER BY id DESC", kind, eid)
        ledger = many("SELECT * FROM changes WHERE entity=? AND entity_id=? "
                      "ORDER BY id DESC LIMIT 40", kind, eid)
        if kind == "project" and project:
            ledger = many("SELECT * FROM changes WHERE project=? ORDER BY id DESC LIMIT 60",
                          project["name"])
        return {"kind": kind, "id": eid, "record": rec, "title": title, "sub": sub,
                "project": project, "extra": extra, "notes": notes,
                "documents": docs, "ledger": ledger}

    # ── site & compliance ──
    def _site(self, c):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        args, where = [], ""
        if q.get("project"):
            where = " AND v.project_id=?"; args = [int(q["project"][0])]
        visits = [dict(r) for r in c.execute(
            "SELECT v.*, p.name pname, p.code pcode FROM site_visits v "
            "LEFT JOIN projects p ON p.id=v.project_id WHERE 1=1" + where +
            " ORDER BY v.visited_on DESC LIMIT 120", args)]
        ncr = [dict(r, age=age_days(r["raised_at"])) for r in c.execute(
            "SELECT ca.*, p.name pname, p.code pcode FROM cases ca "
            "LEFT JOIN projects p ON p.id=ca.project_id WHERE ca.type='NCR' "
            "ORDER BY ca.status, ca.raised_at DESC")]
        auth = [dict(r, age=age_days(r["submitted_on"])) for r in c.execute(
            "SELECT a.*, p.name pname FROM authority a LEFT JOIN projects p "
            "ON p.id=a.project_id ORDER BY a.submitted_on DESC")]
        return {"visits": visits, "ncr": ncr, "authority": auth,
                "kpi": {
                    "visits": len(visits),
                    "non_compliance": sum(1 for v in visits if v["non_compliance"]),
                    "ncr_open": sum(1 for x in ncr if x["status"] == "open"),
                    "authority_open": sum(1 for a in auth
                                          if a["status"] in ("submitted", "observations")),
                    "authority_days": sum(a["age"] for a in auth
                                          if a["status"] in ("submitted", "observations")),
                }}

    # ── what is actually waiting on the person reading the screen ──
    def _notify(self, c, who):
        """Computed, never stored. A notification table drifts out of date the
        moment something is actioned elsewhere; this is derived from the same
        rows the rest of the system reads, so it cannot lie."""
        me = c.execute("SELECT * FROM people WHERE lower(email)=?",
                       (who["email"].lower(),)).fetchone()
        mid = me["id"] if me else -1
        team = me["team"] if me else None
        t = store.today().isoformat()
        out = []

        for r in c.execute("SELECT t.*, p.name pname FROM tasks t LEFT JOIN projects p "
                           "ON p.id=t.project_id WHERE t.person_id=? AND t.status!='done' "
                           "AND t.planned_ed<? ORDER BY t.planned_ed LIMIT 12", (mid, t)):
            out.append({"level": "bad", "kind": "task", "id": r["id"], "tab": "queue",
                        "text": f"Overdue since {r['planned_ed']} — {r['title']}",
                        "sub": r["pname"] or ""})
        for r in c.execute("""SELECT ca.*, p.name pname, l.label lane, l.entered_at,
                              l.sla_days FROM cases ca
                              JOIN case_lanes l ON l.case_id=ca.id AND l.idx=ca.position
                              LEFT JOIN projects p ON p.id=ca.project_id
                              WHERE ca.status='open' AND l.is_stub=0
                              ORDER BY l.entered_at LIMIT 12"""):
            age = age_days(r["entered_at"])
            over = r["sla_days"] and age > r["sla_days"]
            out.append({"level": "bad" if over else "warn", "kind": "case",
                        "id": r["id"], "tab": "cases",
                        "text": f"{r['ref']} waiting on us at “{r['lane']}”"
                                + (f" — {age}d, past the {r['sla_days']}d SLA" if over
                                   else f" — {age}d"),
                        "sub": r["pname"] or ""})
        for r in c.execute("SELECT o.*, p.name pname FROM obligations o "
                           "LEFT JOIN projects p ON p.id=o.project_id "
                           "WHERE o.done_at IS NULL AND o.due_on<? "
                           "ORDER BY o.due_on LIMIT 10", (t,)):
            out.append({"level": "bad", "kind": "obligation", "id": r["id"],
                        "tab": "oblig",
                        "text": f"{r['label']} missed — due {r['due_on']}",
                        "sub": r["pname"] or "Department"})
        for r in c.execute("SELECT co.*, p.name pname FROM coordination co "
                           "LEFT JOIN projects p ON p.id=co.project_id "
                           "WHERE co.closed_at IS NULL AND co.sla_days IS NOT NULL "
                           "AND julianday('now')-julianday(co.opened_at) > co.sla_days*1.4 "
                           "ORDER BY co.opened_at LIMIT 10"):
            out.append({"level": "warn", "kind": "coordination", "id": r["id"],
                        "tab": "coord",
                        "text": f"{r['to_lane']} is {age_days(r['opened_at'])}d on “"
                                f"{(r['ask'] or '')[:60]}” (SLA {r['sla_days']}d)",
                        "sub": r["pname"] or ""})
        if team:
            n = c.execute("SELECT COUNT(*) FROM tasks WHERE team=? AND person_id IS NULL "
                          "AND is_external=0 AND status!='done'", (team,)).fetchone()[0]
            if n:
                out.append({"level": "info", "kind": "tab", "id": 0, "tab": "queue",
                            "text": f"{n} {team} steps have nobody's name on them",
                            "sub": "Unassigned work"})
        if who.get("tier", 3) <= 1:
            for r in c.execute("SELECT * FROM llr WHERE status='ruled' "
                               "AND promoted_stage IS NULL ORDER BY ruled_at LIMIT 6"):
                out.append({"level": "info", "kind": "llr", "id": r["id"], "tab": "llr",
                            "text": f"Ruled but not adopted — “{r['title'][:60]}”",
                            "sub": "§7.6 promotion pending"})
            nb = c.execute("SELECT COUNT(*) FROM changes WHERE blocked=1 "
                           "AND date(at) >= date('now','-7 day')").fetchone()[0]
            if nb:
                out.append({"level": "warn", "kind": "tab", "id": 0, "tab": "ledger",
                            "text": f"{nb} blocked attempts in the last 7 days",
                            "sub": "Gate refusals and external-lane blocks"})
        return {"rows": out, "count": len(out),
                "bad": sum(1 for x in out if x["level"] == "bad")}
''' % {"M": "\u00b7"}

sub('''    # ── payloads ──
    def _bootstrap(self, c, who):''', BUILDERS + '''
    # ── payloads ──
    def _bootstrap(self, c, who):''')

# ══════════════════════════════════════════════════════════════════════════
# 3 · bootstrap and project payload gain the new registers
# ══════════════════════════════════════════════════════════════════════════
sub('''            "routes": {k: {"label": v["label"], "source": v["source"],
                           "lanes": [{"label": a, "owner": b, "sla": cc,
                                      "stub": store.is_stub(b)}
                                     for a, b, cc in v["lanes"]]}
                       for k, v in store.ROUTES.items()},''',
    '''            "routes": {k: {"label": v["label"], "source": v["source"],
                           "stage": v.get("stage"),
                           "value_routed": bool(v.get("value_routed")),
                           "lanes": [{"label": a, "owner": b, "sla": cc,
                                      "stub": store.is_stub(b)}
                                     for a, b, cc in v["lanes"]]}
                       for k, v in store.ROUTES.items()},''')

sub('''                "own_days": own_total, "wait_days": wait_total,''',
    '''                "drawings": q("SELECT COUNT(*) FROM drawings"),
                "sheets_issued": q("SELECT COUNT(*) FROM transmittal_drawings"),
                "visits": q("SELECT COUNT(*) FROM site_visits"),
                "ncr_open": q("SELECT COUNT(*) FROM cases WHERE type='NCR' "
                              "AND status='open'"),
                "authority_open": q("SELECT COUNT(*) FROM authority WHERE status IN "
                                    "('submitted','observations')"),
                "authority_days": q("SELECT COALESCE(SUM(julianday('now')-"
                                    "julianday(submitted_on)),0) FROM authority "
                                    "WHERE status IN ('submitted','observations')"),
                "lessons_open": q("SELECT COUNT(*) FROM llr WHERE status='open'"),
                "lessons_adopted": q("SELECT COUNT(*) FROM llr WHERE status='adopted'"),
                "template_items": q("SELECT COUNT(*) FROM checklist_templates "
                                    "WHERE active=1"),
                "blocked": q("SELECT COUNT(*) FROM changes WHERE blocked=1"),
                "own_days": own_total, "wait_days": wait_total,''')

sub('''        return {"project": dict(p), "stages": stages, "tasks": tasks,
                "cases": cases, "coordination": coord, "obligations": ob,
                "by_team": by_team,
                "stage_names": {s: n for s, n, _p, _d in catalog.STAGES}}''',
    '''        visits = [dict(r) for r in c.execute(
            "SELECT * FROM site_visits WHERE project_id=? ORDER BY visited_on DESC "
            "LIMIT 12", (pid,))]
        dwg = [dict(r) for r in c.execute(
            "SELECT * FROM drawings WHERE project_id=? ORDER BY number", (pid,))]
        trs = [dict(r) for r in c.execute(
            "SELECT * FROM transmittals WHERE project_id=? ORDER BY issued_at DESC",
            (pid,))]
        auth = [dict(r, age=age_days(r["submitted_on"])) for r in c.execute(
            "SELECT * FROM authority WHERE project_id=? ORDER BY submitted_on DESC",
            (pid,))]
        lessons = [dict(r) for r in c.execute(
            "SELECT * FROM llr WHERE project_id=? ORDER BY raised_at DESC", (pid,))]
        chk = {r["stage"]: dict(r) for r in c.execute(
            "SELECT * FROM checklists WHERE project_id=?", (pid,))}
        for st in stages:
            cl = chk.get(st["stage"])
            st["checklist"] = cl
            if cl:
                st["checks"] = c.execute(
                    "SELECT COUNT(*) n, SUM(done) d FROM checklist_items "
                    "WHERE checklist_id=?", (cl["id"],)).fetchone()["n"]
                st["checks_done"] = c.execute(
                    "SELECT COALESCE(SUM(done),0) d FROM checklist_items "
                    "WHERE checklist_id=?", (cl["id"],)).fetchone()["d"]
        return {"project": dict(p), "stages": stages, "tasks": tasks,
                "cases": cases, "coordination": coord, "obligations": ob,
                "visits": visits, "drawings": dwg, "transmittals": trs,
                "authority": auth, "lessons": lessons,
                "by_team": by_team,
                "stage_names": {s: n for s, n, _p, _d in catalog.STAGES}}''')

# startup banner
sub('''    print(f"  catalog  {s['workflows']} workflows · {s['steps']} steps · "
          f"{s['tat_conflicts']} TAT conflicts · {s['unknown_tat']} steps with no duration")''',
    '''    print(f"  catalog  {s['workflows']} workflows ({s['from_booklet']} booklet + "
          f"{s['from_manual']} manual) · {s['steps']} steps · {s['stations']} stations")
    print(f"           {s['tat_conflicts']} TAT conflicts · "
          f"{s['unknown_tat']} steps with no duration · "
          f"{len(store.ROUTES)} case routes · {len(actions.DISPATCH) + 5} write actions")''')

open(PATH, "w", encoding="utf-8").write(src)
print("server.py patched")
