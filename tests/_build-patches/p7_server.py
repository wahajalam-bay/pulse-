"""Backlog #21/#22 (exec + workload bifurcation), #27 (catalogue), #28/#29 (matrix
   time categories), and the entity drawer for findings / threads / ack."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\server.py"
src = open(PATH, encoding="utf-8").read()
S = "\u00a7"


def sub(old, new):
    global src
    assert old in src, "anchor: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# 1 · the matrix separates the five time categories.  #24/#28/#29 of the review
# ══════════════════════════════════════════════════════════════════════════
sub('''        roll = {}
        for r in c.execute("""SELECT project_id,stage,
                COUNT(*) n, SUM(status='done') done,
                SUM(own_days) own, SUM(wait_days) wait,
                SUM(CASE WHEN baseline_days IS NOT NULL AND own_days>baseline_days
                    THEN 1 ELSE 0 END) late
                FROM tasks GROUP BY project_id,stage"""):
            roll[(r["project_id"], r["stage"])] = dict(r)''',
'''        # Backlog #24/#28/#29. The heatmap has to answer "how much time is being
        # spent waiting for OUR team vs another party" — the review's exact
        # words — so the rollup carries expected, in-progress, internal wait,
        # external wait and hold separately. One number could never say whose
        # delay it was, and the department was being charged for all of it.
        roll = {}
        for r in c.execute("""SELECT project_id,stage,
                COUNT(*) n, SUM(status='done') done,
                SUM(own_days) own, SUM(wait_days) wait,
                SUM(wait_ext_days) wait_ext, SUM(hold_days) hold,
                SUM(baseline_days) expected,
                SUM(CASE WHEN baseline_days IS NOT NULL AND own_days>baseline_days
                    THEN 1 ELSE 0 END) late
                FROM tasks GROUP BY project_id,stage"""):
            roll[(r["project_id"], r["stage"])] = dict(r)''')

sub('''                row["cells"].append({
                    "stage": s, "name": name, "phase": ph,
                    "status": cell.get("status", "not_started"),
                    "planned_end": cell.get("planned_end"),
                    "own": rr.get("own") or 0, "wait": rr.get("wait") or 0,
                    "n": rr.get("n") or 0, "done": rr.get("done") or 0,
                    "late": rr.get("late") or 0,''',
'''                own = rr.get("own") or 0
                wait = rr.get("wait") or 0
                wext = rr.get("wait_ext") or 0
                hold = rr.get("hold") or 0
                expected = rr.get("expected") or cell.get("expected_days") or 0
                elapsed = own + wait + hold
                row["cells"].append({
                    "stage": s, "name": name, "phase": ph,
                    "status": cell.get("status", "not_started"),
                    "planned_end": cell.get("planned_end"),
                    "own": own, "wait": wait,
                    # the five the review asked to see apart
                    "expected": expected, "actual": elapsed, "in_progress": own,
                    "wait_internal": max(wait - wext, 0), "wait_external": wext,
                    "hold": hold,
                    "delay": max(elapsed - expected, 0) if expected else 0,
                    # and whose delay it is, which is the point of splitting them
                    "delay_owner": ("external" if wext > max(wait - wext, 0)
                                    and wext > hold else
                                    "hold" if hold > wext and hold > (wait - wext) else
                                    "internal" if elapsed > expected and expected else
                                    None),
                    "n": rr.get("n") or 0, "done": rr.get("done") or 0,
                    "late": rr.get("late") or 0,''')

# ══════════════════════════════════════════════════════════════════════════
# 2 · /api/exec — department overview and workload bifurcation.  #21 / #22
# ══════════════════════════════════════════════════════════════════════════
sub('''            if p == "/api/today":''',
'''            if p == "/api/exec":
                return self._json(200, self._exec(c))

            if p == "/api/today":''')

EXEC = '''
    # ── Executive View.  Backlog #21 / #22 ──
    def _exec(self, c):
        """#21 asked for department-level facts; #22 for workload bifurcation
        over time, because — Haroon's observation — "Architecture & Design is
        front-heavy: the workload is particularly high during the first six
        months and then reduces." A flat headcount-vs-tasks number hides exactly
        that, and it is the number that decides whether a team is under-resourced
        or just early in a project.
        """
        cfg = timecfg(c)
        depts = []
        for team in catalog.TEAMS:
            row = c.execute("""SELECT COUNT(*) n,
                  SUM(status!='done') open,
                  SUM(status='hold') held,
                  COALESCE(SUM(baseline_days),0) expected,
                  COALESCE(SUM(own_days),0) own,
                  COALESCE(SUM(wait_days),0) wait,
                  COALESCE(SUM(wait_ext_days),0) wait_ext,
                  COALESCE(SUM(hold_days),0) hold,
                  COALESCE(SUM(revision),0) rev,
                  SUM(status='done' AND baseline_days IS NOT NULL) closed,
                  SUM(status='done' AND baseline_days IS NOT NULL
                      AND own_days<=baseline_days) ontime
                  FROM tasks WHERE team=?""", (team,)).fetchone()
            ppl = c.execute("SELECT COUNT(*) n FROM people WHERE team=? AND active=1",
                            (team,)).fetchone()["n"]
            owed = c.execute("SELECT COUNT(*) n, COALESCE(SUM("
                             "julianday('now')-julianday(opened_at)),0) d "
                             "FROM coordination WHERE from_team=? AND closed_at IS NULL",
                             (team,)).fetchone()
            asked = c.execute("SELECT COUNT(*) n FROM cases WHERE to_team=? "
                              "AND status='open'", (team,)).fetchone()["n"]
            unack = c.execute("SELECT COUNT(*) n FROM cases WHERE to_team=? "
                              "AND status='open' AND acknowledged_at IS NULL",
                              (team,)).fetchone()["n"]
            find = c.execute("SELECT COUNT(*) n, SUM(status NOT IN "
                             "('resolved','closed')) open FROM findings "
                             "WHERE responsible_team=?", (team,)).fetchone()
            less = c.execute("SELECT COUNT(*) n FROM llr WHERE discipline=?",
                             (team,)).fetchone()["n"]
            wait = row["wait"] or 0
            wext = row["wait_ext"] or 0
            depts.append({
                "team": team, "people": ppl,
                "steps": row["n"], "open": row["open"] or 0, "held": row["held"] or 0,
                "expected": row["expected"], "in_progress": row["own"],
                "wait_internal": max(wait - wext, 0), "wait_external": wext,
                "hold": row["hold"], "revisions": row["rev"],
                "closed": row["closed"] or 0,
                "on_time_pct": round((row["ontime"] or 0) / row["closed"] * 100, 1)
                               if row["closed"] else None,
                "load_per_head": round(row["open"] / ppl, 1) if ppl else None,
                "owed_asks": owed["n"], "owed_days": int(owed["d"] or 0),
                "asked_of_them": asked, "unacknowledged": unack,
                "findings": find["n"] or 0, "findings_open": find["open"] or 0,
                "lessons": less,
            })

        # #22 — where the work actually sits on the spine, per team. This is the
        # front-loading, made visible: expected days by station.
        by_station = {}
        for r in c.execute("""SELECT team, stage, COALESCE(SUM(baseline_days),0) d,
                  COUNT(*) n, SUM(status!='done') open FROM tasks
                  GROUP BY team, stage"""):
            by_station.setdefault(r["team"], {})[r["stage"]] = {
                "days": r["d"], "steps": r["n"], "open": r["open"] or 0}

        # and over calendar time, from the planned dates the catalog produced
        by_month = {}
        for r in c.execute("""SELECT team, substr(planned_sd,1,7) m,
                  COALESCE(SUM(baseline_days),0) d, COUNT(*) n FROM tasks
                  WHERE planned_sd IS NOT NULL GROUP BY team, m ORDER BY m"""):
            by_month.setdefault(r["team"], []).append(
                {"month": r["m"], "days": r["d"], "steps": r["n"]})

        # phase split: A acquisition, B design, C construction+closeout
        phase = {}
        for r in c.execute("""SELECT team, stage, COALESCE(SUM(baseline_days),0) d
                  FROM tasks GROUP BY team, stage"""):
            ph = next((p for s, _n, p, _dd in catalog.STAGES if s == r["stage"]), "B")
            phase.setdefault(r["team"], {}).setdefault(ph, 0)
            phase[r["team"]][ph] += r["d"]

        return {"departments": depts, "by_station": by_station,
                "by_month": by_month, "by_phase": phase,
                "stations": [{"stage": s, "name": n, "phase": p}
                             for s, n, p, _d in catalog.STAGES],
                "phases": catalog.PHASES,
                "unconfirmed": c.execute("SELECT COUNT(*) FROM settings "
                                         "WHERE confirmed=0").fetchone()[0]}
'''

sub('''    def _today(self, c, who):''',
    EXEC + '''    # ── "What should I do today?"  Backlog #13, asked for by name ──
    def _today(self, c, who):''')
# ══════════════════════════════════════════════════════════════════════════
# 3 · the workflow catalogue, with the attributes #27 asks for
# ══════════════════════════════════════════════════════════════════════════
sub('''                return self._json(200, {
                    "rows": [dict(r) for r in rows],
                    "workflows": catalog.workflows(),
                    "booklet": catalog.BOOKLET,
                    "stats": catalog.stats(),''',
'''                # Backlog #27 asked for a formal catalogue: for each workflow,
                # purpose, trigger, requestor, receiving team, approvals,
                # stages, TAT, priority, escalation, dependencies, completion
                # criteria, responsible roles, management visibility. Most of
                # that is derivable from the steps themselves — what a workflow
                # is TRIGGERED by is its first step, who RECEIVES it is the set
                # of external lanes it touches, its COMPLETION criterion is its
                # gate. Derived, so it cannot drift from the catalog it
                # describes.
                wfs = catalog.workflows()
                steps_by = {}
                for r in c.execute("SELECT * FROM products ORDER BY stage,seq"):
                    steps_by.setdefault((r["team"], r["workflow"]), []).append(dict(r))
                for w in wfs:
                    st = steps_by.get((w["team"], w["workflow"]), [])
                    if not st:
                        continue
                    ext = [s["lane"] for s in st if s["is_external"]]
                    w["trigger"] = st[0]["step"]
                    w["completion"] = next(
                        (s["step"] for s in reversed(st) if s["gate"]), st[-1]["step"])
                    w["receiving"] = sorted(set(ext))
                    w["checkpoints"] = sum(1 for s in st if s["checker"])
                    w["rework_at"] = [s["seq"] for s in st if s["rework"]]
                    w["gates_at"] = [s["seq"] for s in st if s["gate"]]
                    w["dependencies"] = sorted(
                        {s["lane"] for s in st
                         if s["lane"] != w["team"] and not s["is_external"]})
                    w["tat_days"] = w["sum_days"] or None
                    w["visibility"] = ("Head ZD" if any(s["gate"] for s in st)
                                       else "Sr Manager " + w["team"])
                return self._json(200, {
                    "rows": [dict(r) for r in rows],
                    "workflows": wfs,
                    "booklet": catalog.BOOKLET,
                    "baseline_source": store.setting(c, "baseline.source", "booklet"),
                    "baseline_confirmed": bool(c.execute(
                        "SELECT confirmed FROM settings WHERE key='baseline.source'"
                    ).fetchone()["confirmed"]),
                    "stats": catalog.stats(),''')

# ══════════════════════════════════════════════════════════════════════════
# 4 · bootstrap: priorities, departments, unconfirmed definitions
# ══════════════════════════════════════════════════════════════════════════
sub('''            "teams": catalog.TEAMS,''',
'''            "teams": catalog.TEAMS,
            "departments": [{"name": n, "kind": k} for n, k in catalog.DEPARTMENTS],
            "priorities": store.priorities(c),
            "priority_default": store.setting(c, "priority.default", "Medium"),
            "unconfirmed": q("SELECT COUNT(*) FROM settings WHERE confirmed=0"),
            "ack_window": (store.setting(c, "ack.window_value", "24") + " "
                           + (store.setting(c, "ack.window_unit", "calendar_hours")
                              or "").replace("_", " ")),
            "finding_categories": actions.FINDING_CATEGORIES,''')

sub('''                "lessons_open": q("SELECT COUNT(*) FROM llr WHERE status='open'"),''',
'''                "findings": q("SELECT COUNT(*) FROM findings"),
                "findings_open": q("SELECT COUNT(*) FROM findings WHERE status "
                                   "NOT IN ('resolved','closed')"),
                "findings_overdue": q("SELECT COUNT(*) FROM findings WHERE due_on "
                                      "< date('now') AND status NOT IN "
                                      "('resolved','closed')"),
                "crossteam_open": q("SELECT COUNT(*) FROM cases WHERE to_team IS NOT "
                                    "NULL AND status='open'"),
                "unacknowledged": q("SELECT COUNT(*) FROM cases WHERE status='open' "
                                    "AND ack_due_at IS NOT NULL AND acknowledged_at "
                                    "IS NULL"),
                "escalated": q("SELECT COUNT(*) FROM cases WHERE escalation_level>0"),
                "hold_days": q("SELECT COALESCE(SUM(hold_days),0) FROM tasks"),
                "wait_ext_days": q("SELECT COALESCE(SUM(wait_ext_days),0) FROM tasks"),
                "tat_days_lost": q("SELECT COALESCE(SUM(delay_days),0) FROM llr"),
                "lessons_open": q("SELECT COUNT(*) FROM llr WHERE status='open'"),''')

# ══════════════════════════════════════════════════════════════════════════
# 5 · the drawer learns findings, threads, acknowledgement and escalation
# ══════════════════════════════════════════════════════════════════════════
sub('''        elif kind == "drawing":''',
'''        elif kind == "finding":
            rec = one("SELECT f.*, p.name pname, pe.name person, v.visited_on, "
                      "v.by_whom, ca.ref case_ref, ca.status case_status "
                      "FROM findings f LEFT JOIN projects p ON p.id=f.project_id "
                      "LEFT JOIN people pe ON pe.id=f.person_id "
                      "LEFT JOIN site_visits v ON v.id=f.visit_id "
                      "LEFT JOIN cases ca ON ca.id=f.case_id WHERE f.id=?", eid)
            if rec:
                pid = rec["project_id"]
                title = rec["title"]
                sub = f"{rec['category'] or ''} · {rec['location'] or ''} · {rec['status']}"
                extra = {
                    # #10 — everything previously found in the same place
                    "history": many(
                        "SELECT f.*, v.visited_on FROM findings f "
                        "LEFT JOIN site_visits v ON v.id=f.visit_id "
                        "WHERE f.project_id=? AND f.category=? AND f.id!=? "
                        "ORDER BY f.raised_at DESC LIMIT 12",
                        rec["project_id"], rec["category"], eid),
                    "same_place": many(
                        "SELECT f.*, v.visited_on FROM findings f "
                        "LEFT JOIN site_visits v ON v.id=f.visit_id "
                        "WHERE f.project_id=? AND lower(f.location)=lower(?) "
                        "AND f.id!=? ORDER BY f.raised_at DESC LIMIT 12",
                        rec["project_id"], rec["location"] or "", eid),
                    "recurrence": dict(one("SELECT * FROM findings WHERE id=?",
                                           rec["recurrence_of"]) or {})
                                  if rec["recurrence_of"] else None,
                    "task": dict(one("SELECT * FROM tasks WHERE id=?",
                                     rec["task_id"]) or {}) if rec["task_id"] else None,
                    "lesson": dict(one("SELECT * FROM llr WHERE id=?",
                                       rec["llr_id"]) or {}) if rec["llr_id"] else None,
                    "priority_log": many("SELECT * FROM priority_log WHERE entity='finding'"
                                         " AND entity_id=? ORDER BY id DESC", eid),
                }

        elif kind == "drawing":''')

sub('''                extra = {"lanes": lanes, "route": route.get("label"),
                         "source": route.get("source"), "position": rec["position"],
                         "asks": many("SELECT * FROM coordination WHERE ask LIKE ?",
                                      rec["ref"] + "%")}''',
'''                extra = {"lanes": lanes, "route": route.get("label"),
                         "source": route.get("source"), "position": rec["position"],
                         "asks": many("SELECT * FROM coordination WHERE ask LIKE ?",
                                      rec["ref"] + "%"),
                         # #2 — the thread. A case you cannot talk about is a case
                         # whose reasoning lives in somebody's inbox.
                         "messages": many("SELECT * FROM case_messages WHERE case_id=? "
                                          "ORDER BY id", eid),
                         "ack_overdue": store.ack_overdue(c, rec),
                         "priority_log": many("SELECT * FROM priority_log "
                                              "WHERE entity='case' AND entity_id=? "
                                              "ORDER BY id DESC", eid),
                         "origin": (dict(one(
                             f"SELECT * FROM {'findings' if rec['origin_entity'] == 'finding' else 'site_visits'} WHERE id=?",
                             rec["origin_id"]) or {})
                             if rec["origin_entity"] and rec["origin_id"] else None)}''')

sub('''                extra = {"ncr": many(
                    "SELECT * FROM cases WHERE project_id=? AND type='NCR' "
                    "AND raised_at<=? ORDER BY id DESC LIMIT 5",
                    rec["project_id"], rec["visited_on"]) if rec["non_compliance"] else []}''',
'''                # the visit is now a container: its findings ARE its content
                extra = {"findings": many(
                    "SELECT f.*, pe.name person, ca.ref case_ref FROM findings f "
                    "LEFT JOIN people pe ON pe.id=f.person_id "
                    "LEFT JOIN cases ca ON ca.id=f.case_id "
                    "WHERE f.visit_id=? ORDER BY f.seq", eid),
                    "prior": many(
                    "SELECT v.*, (SELECT COUNT(*) FROM findings f WHERE f.visit_id=v.id) n"
                    " FROM site_visits v WHERE v.project_id=? AND v.id!=? "
                    "ORDER BY v.visited_on DESC LIMIT 8", rec["project_id"], eid)}''')

open(PATH, "w", encoding="utf-8").write(src)
print("server.py: exec, matrix categories, catalogue attributes, findings drawer")
