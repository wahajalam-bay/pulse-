"""Backlog #12/#13 (today), #16 (learning summary), #21/#22 (exec bifurcation),
   #27 (workflow catalogue), #28/#29 (time categories), #32/#33 (delivery), §36."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\server.py"
src = open(PATH, encoding="utf-8").read()
S = "\u00a7"
D = "\u2014"


def sub(old, new):
    global src
    assert old in src, "anchor: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1 · task_view exposes priority, hold, external wait, due date
# ══════════════════════════════════════════════════════════════════════════
sub('''def task_view(r):
    """Everything derived, on read. See store.py note 3."""
    base = r["baseline_days"]
    own, wait = r["own_days"] or 0, r["wait_days"] or 0
    elapsed = own + wait
    var = None if base is None else own - base   # SLA is judged on OWN time only
    late = bool(base is not None and own > base)
    return {''',
'''def task_view(r, cfg=None):
    """Everything derived, on read.

    Backlog #27-#31. The review asked the matrix to separate expected, actual,
    waiting, hold and in-progress, and to split waiting into ours vs theirs. So
    this returns all five, and the ONE ambiguous rule — does waiting count
    inside in-progress — is read from `cfg`, never decided here. `cfg` comes from
    the settings table, which ships UNCONFIRMED because §36 D is still open.
    """
    cfg = cfg or {}
    base = r["baseline_days"]
    own = r["own_days"] or 0
    wait = r["wait_days"] or 0
    wait_ext = r["wait_ext_days"] or 0
    hold = r["hold_days"] or 0
    wait_int = max(wait - wait_ext, 0)
    elapsed = own + wait + hold
    # §36 D / §27: the open question, as a switch rather than an assumption
    in_progress = own + (wait if cfg.get("wait_counts_as_inprogress") else 0)
    var = None if base is None else in_progress - base
    late = bool(base is not None and in_progress > base)
    return {
        "priority": r["priority"], "due_on": r["due_on"],
        "wait_internal": wait_int, "wait_external": wait_ext, "hold": hold,
        "in_progress": in_progress, "expected": base,
        "hold_reason": r["hold_reason"],
        "origin_entity": r["origin_entity"], "origin_id": r["origin_id"],''')

sub('''        "variance": var, "late": late, "revision": r["revision"],
        "status": r["status"], "planned_sd": r["planned_sd"], "planned_ed": r["planned_ed"],
        "actual_sd": r["actual_sd"], "actual_ed": r["actual_ed"],
        "person_id": r["person_id"],
    }''',
'''        "variance": var, "late": late, "revision": r["revision"],
        "status": r["status"], "planned_sd": r["planned_sd"], "planned_ed": r["planned_ed"],
        "actual_sd": r["actual_sd"], "actual_ed": r["actual_ed"],
        "person_id": r["person_id"],
    }


def timecfg(c):
    """The time-model settings, read once per request."""
    return {
        "wait_counts_as_inprogress": store.setting_bool(
            c, "time.wait_counts_as_inprogress", False),
        "own_time_means": store.setting(c, "time.own_time_means", "active_execution"),
        "exclusions": store.delivery_exclusions(c),
    }


def days_since(iso):
    if not iso:
        return None
    try:
        return (datetime.datetime.now()
                - datetime.datetime.fromisoformat(iso)).total_seconds() / 86400.0
    except ValueError:
        return None''')

# every task_view caller gets the config
for old, new in [
    ('mine = [task_view(r) for r in c.execute(', 'cfg = timecfg(c)\n                mine = [task_view(r, cfg) for r in c.execute('),
]:
    sub(old, new)
src = src.replace('unass = [task_view(r) for r in c.execute(',
                  'unass = [task_view(r, cfg) for r in c.execute(')
src = src.replace('tasks = [task_view(r) for r in c.execute(',
                  'tasks = [task_view(r, timecfg(c)) for r in c.execute(')
src = src.replace('return {"rows": [task_view(r) for r in c.execute(sql, args)]}',
                  'cfg = timecfg(c)\n        return {"rows": [task_view(r, cfg) for r in c.execute(sql, args)]}')
src = src.replace('"view": task_view(rec),', '"view": task_view(rec, timecfg(c)),')
src = src.replace('return self._json(200, {"ok": True, "task": task_view(row)})',
                  'return self._json(200, {"ok": True, "task": task_view(row, timecfg(c))})')

# ══════════════════════════════════════════════════════════════════════════
# 2 · new GET endpoints
# ══════════════════════════════════════════════════════════════════════════
sub('''            if p == "/api/search":''',
'''            if p == "/api/today":
                return self._json(200, self._today(c, who))

            if p == "/api/settings":
                rows = [dict(r) for r in c.execute(
                    "SELECT * FROM settings ORDER BY section, key")]
                sec = {}
                for r in rows:
                    sec.setdefault(r["section"], []).append(r)
                return self._json(200, {
                    "sections": sec, "rows": rows,
                    "unconfirmed": sum(1 for r in rows if not r["confirmed"]),
                    "total": len(rows)})

            if p == "/api/findings":
                return self._json(200, self._findings(c))

            if p == "/api/learning":
                return self._json(200, self._learning(c))

            if p == "/api/delivery":
                return self._json(200, self._delivery(c))

            if p == "/api/departments":
                return self._json(200, {"rows": [dict(r) for r in c.execute(
                    "SELECT * FROM departments WHERE active=1 ORDER BY kind,name")],
                    "kinds": ["design", "internal", "governance", "external"]})

            if p == "/api/search":''')

# ══════════════════════════════════════════════════════════════════════════
# 3 · the payload builders
# ══════════════════════════════════════════════════════════════════════════
B = '''
    # ── "What should I do today?"  Backlog #13, asked for by name ──
    def _today(self, c, who):
        """The review asked for this in those words: not a list of pending
        things, but "what requires action today". So every row here carries the
        reason it is on the list and what the action IS, sorted by priority
        first and lateness second — because a Critical two days late outranks a
        Low three weeks late, and the old queue could not express that at all.
        """
        me = c.execute("SELECT * FROM people WHERE lower(email)=?",
                       (who["email"].lower(),)).fetchone()
        mid = me["id"] if me else -1
        team = me["team"] if me else (who.get("team") or "Architecture")
        t = store.today().isoformat()
        cfg = timecfg(c)
        prios = store.priorities(c)
        rank = {p: i for i, p in enumerate(prios)}
        rows = []

        def add(bucket, kind, eid, title, why, action, priority, due, age=None,
                sub=None, overdue=False):
            rows.append({"bucket": bucket, "kind": kind, "id": eid, "title": title,
                         "why": why, "action": action,
                         "priority": priority or "Medium", "due": due,
                         "age": age, "sub": sub, "overdue": overdue,
                         "rank": rank.get(priority or "Medium", 9)})

        # 1 · a cross-team request nobody has acknowledged
        for r in c.execute("""SELECT ca.*, p.name pname FROM cases ca
                              LEFT JOIN projects p ON p.id=ca.project_id
                              WHERE ca.status='open' AND ca.acknowledged_at IS NULL
                                AND ca.ack_due_at IS NOT NULL
                              ORDER BY ca.ack_due_at"""):
            late = store.ack_overdue(c, r)
            add("Acknowledge", "case", r["id"], f"{r['ref']} {r['title']}",
                ("Acknowledgement window has closed" if late
                 else "Waiting to be acknowledged"),
                "Acknowledge it, or say what is blocking it",
                r["priority"], (r["ack_due_at"] or "")[:16].replace("T", " "),
                sub=f"{r['from_team'] or ''} → {r['to_team'] or ''} · {r['pname'] or ''}",
                overdue=late)

        # 2 · a decision sitting in a ZD lane
        for r in c.execute("""SELECT ca.*, p.name pname, l.label lane, l.entered_at,
                              l.sla_days FROM cases ca
                              JOIN case_lanes l ON l.case_id=ca.id AND l.idx=ca.position
                              LEFT JOIN projects p ON p.id=ca.project_id
                              WHERE ca.status='open' AND l.is_stub=0
                              ORDER BY l.entered_at"""):
            age = age_days(r["entered_at"])
            over = bool(r["sla_days"] and age > r["sla_days"])
            add("Decide", "case", r["id"], f"{r['ref']} {r['title']}",
                (f"{age}d in “{r['lane']}”, past the {r['sla_days']}d TAT" if over
                 else f"{age}d in “{r['lane']}”"),
                "Approve, return or reject — with a reason",
                r["priority"], r["due_on"], age=age,
                sub=f"{r['pname'] or ''} · {r['type']}", overdue=over)

        # 3 · my own steps, overdue first
        for r in c.execute("""SELECT t.*, p.name pname FROM tasks t
                              LEFT JOIN projects p ON p.id=t.project_id
                              WHERE t.person_id=? AND t.status NOT IN ('done')
                              ORDER BY t.due_on""", (mid,)):
            v = task_view(r, cfg)
            over = bool(r["due_on"] and r["due_on"] < t)
            if not over and r["status"] != "queued" and not v["late"]:
                continue
            add("My work", "task", r["id"], r["title"],
                ("Hold: " + (r["hold_reason"] or "blocked") if r["status"] == "hold"
                 else f"Overdue since {r['due_on']}" if over
                 else f"{v['in_progress']}d against a {v['expected']}d TAT" if v["late"]
                 else "Not started"),
                ("Say what is blocking it" if r["status"] == "hold"
                 else "Start it" if r["status"] == "queued" else "Finish it"),
                r["priority"], r["due_on"], sub=r["pname"] or "", overdue=over)

        # 4 · a finding assigned to me or my team, still open
        for r in c.execute("""SELECT f.*, p.name pname FROM findings f
                              LEFT JOIN projects p ON p.id=f.project_id
                              WHERE f.status IN ('open','assigned','in_progress')
                                AND (f.person_id=? OR f.responsible_team=?)
                              ORDER BY f.due_on""", (mid, team)):
            over = bool(r["due_on"] and r["due_on"] < t)
            add("Site findings", "finding", r["id"], r["title"],
                (f"Non-compliance, overdue since {r['due_on']}" if over and r["non_compliance"]
                 else f"Overdue since {r['due_on']}" if over
                 else "Non-compliance open" if r["non_compliance"]
                 else "Open finding"),
                "Resolve it, or raise it to the responsible team",
                r["priority"], r["due_on"],
                sub=f"{r['pname'] or ''} · {r['category'] or ''} · {r['location'] or ''}",
                overdue=over)

        # 5 · an obligation past due
        for r in c.execute("""SELECT o.*, p.name pname FROM obligations o
                              LEFT JOIN projects p ON p.id=o.project_id
                              WHERE o.done_at IS NULL AND o.due_on < ?
                              ORDER BY o.due_on LIMIT 12""", (t,)):
            add("Compliance", "obligation", r["id"], r["label"],
                f"Missed — was due {r['due_on']}", "Complete it with evidence",
                "High", r["due_on"], sub=r["pname"] or "Department", overdue=True)

        # 6 · a lesson I have to rule on (heads and senior managers only)
        if who.get("tier", 3) <= 1:
            for r in c.execute("SELECT * FROM llr WHERE status='open' "
                               "ORDER BY raised_at LIMIT 10"):
                add("Rule on", "llr", r["id"], r["title"],
                    "Raised and waiting on a ruling",
                    "Rule on it, then adopt it into the stage checklist",
                    r["priority"], None, sub=r["category"] or "")
            n = c.execute("SELECT COUNT(*) FROM settings WHERE confirmed=0").fetchone()[0]
            if n:
                add("Define", "setting", 0,
                    f"{n} business definitions are still UNCONFIRMED",
                    "Every performance number in the system depends on these",
                    "Confirm them, or the figures cannot be defended",
                    "Critical", None, sub="Haroon's review §36")

        rows.sort(key=lambda r: (not r["overdue"], r["rank"], r["due"] or "9999"))
        buckets = {}
        for r in rows:
            buckets[r["bucket"]] = buckets.get(r["bucket"], 0) + 1
        return {"rows": rows, "buckets": buckets, "count": len(rows),
                "overdue": sum(1 for r in rows if r["overdue"]),
                "critical": sum(1 for r in rows if r["priority"] == "Critical"),
                "me": dict(me) if me else None, "priorities": prios}

    # ── findings, with the history the review asked for (#10) ──
    def _findings(self, c):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        sql = ("SELECT f.*, p.name pname, p.code pcode, v.visited_on, v.by_whom,"
               " pe.name person, ca.ref case_ref, ca.status case_status"
               " FROM findings f"
               " LEFT JOIN projects p ON p.id=f.project_id"
               " LEFT JOIN site_visits v ON v.id=f.visit_id"
               " LEFT JOIN people pe ON pe.id=f.person_id"
               " LEFT JOIN cases ca ON ca.id=f.case_id WHERE 1=1")
        args = []
        if q.get("project"):
            sql += " AND f.project_id=?"; args.append(int(q["project"][0]))
        if q.get("visit"):
            sql += " AND f.visit_id=?"; args.append(int(q["visit"][0]))
        if q.get("status"):
            sql += " AND f.status=?"; args.append(q["status"][0])
        if q.get("team"):
            sql += " AND f.responsible_team=?"; args.append(q["team"][0])
        sql += " ORDER BY f.raised_at DESC, f.seq LIMIT 400"
        rows = [dict(r) for r in c.execute(sql, args)]
        t = store.today().isoformat()
        for r in rows:
            r["overdue"] = bool(r["due_on"] and r["due_on"] < t
                                and r["status"] not in ("resolved", "closed"))
        # #10 — recurrence, by category and place
        rec = {}
        for r in c.execute("SELECT category, location, COUNT(*) n, "
                           "COUNT(DISTINCT project_id) np FROM findings "
                           "WHERE category IS NOT NULL GROUP BY category, location "
                           "HAVING n > 1 ORDER BY n DESC"):
            rec.setdefault(r["category"], []).append(dict(r))
        by_cat = {}
        for r in c.execute("SELECT category, COUNT(*) n, "
                           "SUM(non_compliance) nc, "
                           "SUM(status IN ('resolved','closed')) closed "
                           "FROM findings GROUP BY category ORDER BY n DESC"):
            by_cat[r["category"] or "Uncategorised"] = dict(r)
        by_team = {}
        for r in c.execute("SELECT responsible_team tm, COUNT(*) n, "
                           "SUM(status NOT IN ('resolved','closed')) open "
                           "FROM findings GROUP BY responsible_team"):
            by_team[r["tm"] or "unassigned"] = dict(r)
        return {"rows": rows, "recurring": rec, "by_category": by_cat,
                "by_team": by_team,
                "kpi": {"total": len(rows),
                        "open": sum(1 for r in rows
                                    if r["status"] not in ("resolved", "closed")),
                        "overdue": sum(1 for r in rows if r["overdue"]),
                        "non_compliance": sum(1 for r in rows if r["non_compliance"]),
                        "recurring": sum(1 for r in rows if r["recurrence_of"]),
                        "became_case": sum(1 for r in rows if r["case_id"])},
                "categories": actions.FINDING_CATEGORIES}

    # ── Learning Summary.  Backlog #16, asked for as a dedicated page ──
    def _learning(self, c):
        """"Turn lessons learned into institutional knowledge" — the review's
        words. Which means the page cannot just list lessons: it has to answer
        what keeps happening, whose process caused it, how much TAT it cost, and
        which improvements are actually closed."""
        rows = [dict(r) for r in c.execute(
            "SELECT l.*, p.name pname FROM llr l LEFT JOIN projects p "
            "ON p.id=l.project_id ORDER BY l.raised_at DESC")]
        agg = lambda col: {k: v for k, v in c.execute(
            f"SELECT COALESCE({col},'Unstated') k, COUNT(*) n FROM llr "
            f"GROUP BY {col} ORDER BY n DESC").fetchall()}
        recur = [dict(r) for r in c.execute(
            "SELECT category, COUNT(*) n, SUM(COALESCE(delay_days,0)) days "
            "FROM llr GROUP BY category HAVING n > 1 ORDER BY n DESC")]
        imp = {}
        for r in c.execute("SELECT improvement_status s, COUNT(*) n FROM llr "
                           "GROUP BY improvement_status"):
            imp[r["s"] or "proposed"] = r["n"]
        tpl = c.execute("SELECT COUNT(*) n FROM checklist_templates "
                        "WHERE llr_id IS NOT NULL AND active=1").fetchone()["n"]
        return {
            "rows": rows,
            "by_category": agg("category"),
            "by_discipline": agg("discipline"),
            "by_delay_kind": agg("delay_kind"),
            "by_delay_owner": agg("delay_owner"),
            "recurring": recur,
            "improvements": imp,
            "kpi": {
                "total": len(rows),
                "open": sum(1 for r in rows if r["status"] == "open"),
                "ruled": sum(1 for r in rows if r["status"] == "ruled"),
                "adopted": sum(1 for r in rows if r["status"] == "adopted"),
                "with_root_cause": sum(1 for r in rows if r["root_cause"]),
                "tat_days_lost": sum(r["delay_days"] or 0 for r in rows),
                "internal": sum(1 for r in rows if r["delay_kind"] == "internal"),
                "external": sum(1 for r in rows if r["delay_kind"] == "external"),
                "dependency": sum(1 for r in rows if r["delay_kind"] == "dependency"),
                "process": sum(1 for r in rows if r["delay_kind"] == "process"),
                "head_seen": sum(1 for r in rows if r["head_notified_at"]),
                "audit_seen": sum(1 for r in rows if r["audit_notified_at"]),
                "checks_created": tpl,
                "improvements_open": sum(
                    v for k, v in imp.items()
                    if k in ("proposed", "agreed", "in_progress")),
                "improvements_closed": imp.get("done", 0),
            },
            "settings": {
                "notify_head": store.setting_bool(c, "lessons.notify_head", True),
                "notify_audit": store.setting_bool(c, "lessons.notify_audit", True),
                "audit_from": store.setting(c, "lessons.audit_from_status", "ruled"),
            }}

    # ── Delivery cycle.  Backlog #29 / #30 / #32 / #33 ──
    def _delivery(self, c):
        """The review's sharpest point: "When a Director signs off, the timing of
        that approval can currently reflect negatively on the senior manager."
        So delivery time is decomposed and the exclusions are SETTINGS — §30
        asked for MD approval out, and §36 F says confirm the rest first. Every
        figure here says which exclusions produced it."""
        cfg = timecfg(c)
        ex = cfg["exclusions"]
        out = []
        for pr in c.execute("SELECT * FROM projects WHERE is_bau=0 ORDER BY name"):
            row = c.execute("""SELECT
                  COALESCE(SUM(own_days),0) own,
                  COALESCE(SUM(wait_days),0) wait,
                  COALESCE(SUM(wait_ext_days),0) wait_ext,
                  COALESCE(SUM(hold_days),0) hold,
                  COALESCE(SUM(baseline_days),0) expected,
                  COUNT(*) n FROM tasks WHERE project_id=?""",
                            (pr["id"],)).fetchone()
            own, wait = row["own"], row["wait"]
            wext, hold = row["wait_ext"], row["hold"]
            wint = max(wait - wext, 0)
            # approval time held by a governance lane on this project's cases
            appr = c.execute("""SELECT COALESCE(SUM(
                     julianday(COALESCE(l.left_at, 'now')) - julianday(l.entered_at)
                   ),0) d FROM case_lanes l JOIN cases ca ON ca.id=l.case_id
                   WHERE ca.project_id=? AND l.entered_at IS NOT NULL
                     AND l.owner_lane IN ('Head ZD','CEO Office','CPC','CFT')""",
                             (pr["id"],)).fetchone()["d"] or 0
            md = c.execute("""SELECT COALESCE(SUM(
                     julianday(COALESCE(l.left_at,'now')) - julianday(l.entered_at)
                   ),0) d FROM case_lanes l JOIN cases ca ON ca.id=l.case_id
                   WHERE ca.project_id=? AND l.entered_at IS NOT NULL
                     AND l.owner_lane='CEO Office'""", (pr["id"],)).fetchone()["d"] or 0
            gross = own + wait + hold
            removed = 0
            if "md_approval" in ex:
                removed += md
            if "approval" in ex:
                removed += max(appr - md, 0)
            if "wait_external" in ex:
                removed += wext
            if "hold" in ex:
                removed += hold
            out.append({
                "project": dict(pr),
                "expected": row["expected"], "steps": row["n"],
                "in_progress": own, "wait_internal": wint, "wait_external": wext,
                "hold": hold, "approval": round(appr - md, 1), "md_approval": round(md, 1),
                "gross": round(gross, 1),
                "delivery": round(max(gross - removed, 0), 1),
                "excluded": round(removed, 1),
            })
        return {"rows": out, "exclusions": ex,
                "settings": [dict(r) for r in c.execute(
                    "SELECT * FROM settings WHERE section='Delivery cycle' "
                    "ORDER BY key")],
                "note": ("MD approval is excluded by default because §30 of the "
                         "review asked for it. Everything else is a switch until "
                         "§36 F confirms the full list.")}
'''

sub('''    # ── one box over every register ──
    def _search(self, c):''', B + '''
    # ── one box over every register ──
    def _search(self, c):''')

open(PATH, "w", encoding="utf-8").write(src)
print("server.py: today, findings, learning, delivery, settings, departments")
