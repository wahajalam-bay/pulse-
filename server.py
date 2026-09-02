#!/usr/bin/env python3
"""ZD PULSE — the service.

Stdlib only, same shape as Bayut Studios PULSE: static files plus a small JSON API,
one SQLite store, sessions as HMAC-signed tokens rather than a server-side table.

  GET  <MOUNT>/...              static
  POST <MOUNT>/api/login        sign in
  GET  <MOUNT>/api/me           who am I
  GET  <MOUNT>/api/bootstrap    everything the client needs in one payload
  GET  <MOUNT>/api/matrix       the stage matrix — project x stage
  GET  <MOUNT>/api/project/<id> one project in depth
  GET  <MOUNT>/api/team/<name>  one team's performance
  GET  <MOUNT>/api/tasks        filtered task list
  POST <MOUNT>/api/task/start   |/finish |/revise
  GET  <MOUNT>/api/cases        the approvals inbox
  POST <MOUNT>/api/case/advance move a case along its route
  GET  <MOUNT>/api/coordination the cross-team ledger
  POST <MOUNT>/api/coordination/close
  GET  <MOUNT>/api/obligations  recurring commitments and misses
  GET  <MOUNT>/api/ledger       every action, filterable
  GET  <MOUNT>/api/catalog      the booklet as data, incl. TAT conflicts
  GET  <MOUNT>/api/search?q=     one box over every register
  GET  <MOUNT>/api/entity/<k>/<id> the record, its context and its history
  GET  <MOUNT>/api/notifications what is waiting on the signed-in person
  GET  <MOUNT>/api/llr           lessons learned register
  GET  <MOUNT>/api/authority     the authority file
  GET  <MOUNT>/api/site          visits, NCRs and inspections
  GET  <MOUNT>/api/template      the §4.2 stage checklist template
  GET  <MOUNT>/api/health

Run:  PORT=4010 MOUNT=/zd python server.py
"""
import http.server, json, os, sys, datetime, hmac, hashlib, base64, secrets, re

import store, catalog, actions

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 4010))
HOST = os.environ.get("HOST", "127.0.0.1")
MOUNT = os.environ.get("MOUNT", "/zd").rstrip("/")
USERFILE = os.path.join(HERE, "data", "users.json")
SECFILE = os.path.join(HERE, "data", ".session-secret")
PBKDF_ROUNDS = 200_000
SESSION_DAYS = 7
MAXBODY = 1024 * 1024
ALLOW_DOMAINS = [d.strip().lower() for d in os.environ.get(
    "ALLOW_DOMAINS", "zameen.com,bayut.sa,dubizzlelabs.com").split(",") if d.strip()]

PRIVATE = {"server.py", "store.py", "catalog.py", "actions.py",
           "migrate_v3.py", "backfill_v3.py", "data", "logs", "__pycache__",
           "PROJECT-MEMORY.md", "backup-pre-v2", "backup-pre-v3",
           "HAROON-REGISTER-1SEP.docx", "HAROON-REGISTER-1SEP.txt",
           # the review register under either name, the backlog, and the test
           # suite: source and meeting minutes, none of it for the browser
           "ARCH AND DESIGN (1).docx", "BACKLOG.md", "tests"}


# ── auth ─────────────────────────────────────────────────────────────────────
def _secret():
    try:
        with open(SECFILE, "rb") as f:
            s = f.read().strip()
            if s:
                return s
    except OSError:
        pass
    s = base64.urlsafe_b64encode(secrets.token_bytes(32))
    os.makedirs(os.path.dirname(SECFILE), exist_ok=True)
    with open(SECFILE, "wb") as f:
        f.write(s)
    return s


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), PBKDF_ROUNDS)
    return salt, dk.hex()


def verify_pw(pw, salt, want):
    return hmac.compare_digest(hash_pw(pw, salt)[1], want)


def load_users():
    try:
        with open(USERFILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(u):
    with open(USERFILE, "w", encoding="utf-8") as f:
        json.dump(u, f, indent=2)


def seed_users():
    """Accounts mirror the real org so the demo is recognisable.

    Everyone shares one password for the review session — this is a local
    walkthrough build, not a deployment. Rotate before this ever leaves a laptop.
    """
    if load_users():
        return
    demo_pw = "ZDesign!2026"
    who = [
        ("haroon@zameen.com", "Haroon Noon", "Head of Architecture & Design", "head", 0),
        ("ahmed@zameen.com", "Ahmed Khan", "Sr. Manager Architecture", "manager", 1),
        ("yahya@zameen.com", "Yahya Ali Khan", "Sr. Manager MEP", "manager", 1),
        ("rashid@zameen.com", "Hafiz Rashid Khalid", "Sr. Manager Structure", "manager", 1),
        ("ali@zameen.com", "Ali Aslam", "Creative Lead", "manager", 1),
        ("umer@zameen.com", "Umer Farooq", "Architect", "lead", 2),
        ("ashhad@bayut.sa", "Muhammad Ashhad", "BSE — Systems", "head", 0),
    ]
    users = {}
    for email, name, desig, role, tier in who:
        salt, h = hash_pw(demo_pw)
        users[email] = {"name": name, "designation": desig, "role": role, "tier": tier,
                        "salt": salt, "hash": h, "created": store.now(), "lastLogin": ""}
    save_users(users)


def make_token(email):
    exp = int(datetime.datetime.now().timestamp()) + SESSION_DAYS * 86400
    body = f"{email}|{exp}".encode()
    sig = hmac.new(_secret(), body, hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(body).decode() + "." + sig


def read_token(tok):
    try:
        b64, sig = tok.split(".", 1)
        body = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
        if not hmac.compare_digest(
                hmac.new(_secret(), body, hashlib.sha256).hexdigest()[:32], sig):
            return None
        email, exp = body.decode().rsplit("|", 1)
        if int(exp) < datetime.datetime.now().timestamp():
            return None
        return email
    except Exception:
        return None


def public_user(email, u):
    return {"email": email, "name": u.get("name", ""), "role": u.get("role", "member"),
            "designation": u.get("designation", ""), "tier": u.get("tier", 3)}


# ── derivation ───────────────────────────────────────────────────────────────
def task_view(r, cfg=None):
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
        "origin_entity": r["origin_entity"], "origin_id": r["origin_id"],
        "id": r["id"], "project_id": r["project_id"], "team": r["team"],
        "workflow": r["workflow"], "stage": r["stage"], "seq": r["seq"],
        "title": r["title"], "lane": r["lane"], "external": bool(r["is_external"]),
        "baseline": base, "own": own, "wait": wait, "elapsed": elapsed,
        "variance": var, "late": late, "revision": r["revision"],
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
        return None


def age_days(iso):
    if not iso:
        return 0
    return store.working_days_between(iso[:10], store.today().isoformat()) or 0


class H(http.server.SimpleHTTPRequestHandler):
    server_version = "ZDPULSE/1.0"

    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, fmt, *a):
        pass

    # ── plumbing ──
    def _json(self, code, obj):
        b = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAXBODY:
                return None
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return None

    def _who(self):
        h = self.headers.get("Authorization") or ""
        tok = h[7:].strip() if h.lower().startswith("bearer ") else ""
        email = read_token(tok) if tok else None
        if not email:
            return None
        u = load_users().get(email)
        return dict(u, email=email) if u else None

    def _strip(self):
        if MOUNT and (self.path == MOUNT or self.path.startswith(MOUNT + "/")):
            self.path = self.path[len(MOUNT):] or "/"
            return True
        return not MOUNT

    def translate_path(self, path):
        p = super().translate_path(path)
        rel = os.path.relpath(p, HERE).replace("\\", "/")
        if rel.split("/")[0] in PRIVATE:
            return os.path.join(HERE, "__forbidden__")
        return p

    # ── routes ──
    def do_GET(self):
        if not self._strip():
            self.send_error(404); return
        p = self.path.split("?")[0]

        if p == "/api/health":
            return self._json(200, {"ok": True, "mount": MOUNT,
                                    "catalog": catalog.stats()})
        if p.startswith("/api/"):
            return self._api_get(p)
        if p == "/":
            self.path = "/index.html"
        return super().do_GET()

    def _api_get(self, p):
        who = self._who()
        if not who:
            return self._json(401, {"error": "Sign in to use ZD PULSE."})
        c = store.conn()
        try:
            return self._route_get(c, p, who)
        except Exception as x:
            # A read that blows up must reach the client as an error it can show,
            # not as a dropped connection the browser reports as "failed to fetch".
            import traceback
            traceback.print_exc()
            return self._json(500, {"error": f"{type(x).__name__}: {x}"})
        finally:
            c.close()

    def _route_get(self, c, p, who):
        if True:
            if p == "/api/me":
                return self._json(200, {"ok": True, "user": public_user(who["email"], who)})

            if p == "/api/bootstrap":
                return self._json(200, self._bootstrap(c, who))

            if p == "/api/matrix":
                return self._json(200, self._matrix(c))

            m = re.match(r"^/api/project/(\d+)$", p)
            if m:
                return self._json(200, self._project(c, int(m.group(1))))

            m = re.match(r"^/api/team/(.+)$", p)
            if m:
                from urllib.parse import unquote
                return self._json(200, self._team(c, unquote(m.group(1))))

            if p == "/api/tasks":
                return self._json(200, self._tasks(c))

            if p == "/api/cases":
                return self._json(200, self._cases(c))

            if p == "/api/coordination":
                return self._json(200, self._coord(c))

            if p == "/api/obligations":
                return self._json(200, self._oblig(c))

            if p == "/api/ledger":
                rows = c.execute("SELECT * FROM changes ORDER BY id DESC LIMIT 300").fetchall()
                return self._json(200, {"rows": [dict(r) for r in rows]})

            m = re.match(r"^/api/intake/(\d+)$", p)
            if m:
                pid = int(m.group(1))
                r = c.execute("SELECT * FROM intake WHERE project_id=?", (pid,)).fetchone()
                return self._json(200, {
                    "fields": [{"key": k, "label": l, "source": src,
                                "value": (r[k] if r else "") or ""}
                               for k, l, src in actions.INTAKE_FIELDS],
                    "updated_at": r["updated_at"] if r else None,
                    "updated_by": r["updated_by"] if r else None})

            m = re.match(r"^/api/checklist/(\d+)/(\d+)$", p)
            if m:
                pid, stage = int(m.group(1)), int(m.group(2))
                cl = c.execute("SELECT * FROM checklists WHERE project_id=? AND stage=?",
                               (pid, stage)).fetchone()
                if not cl:
                    # Stamped from the §4.2 template, exactly as stage/initiate does it.
                    # A checklist that appears empty because of HOW it was opened would
                    # be a different gate depending on the route in — so it is one path.
                    c.execute("INSERT INTO checklists(project_id,stage,created_at) "
                              "VALUES(?,?,?)", (pid, stage, store.now()))
                    clid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                    for i, t in enumerate(c.execute(
                            "SELECT * FROM checklist_templates WHERE stage=? AND active=1 "
                            "ORDER BY seq", (stage,)).fetchall()):
                        c.execute("INSERT INTO checklist_items(checklist_id,seq,text,source)"
                                  " VALUES(?,?,?,?)", (clid, i + 1, t["text"], t["source"]))
                    c.commit()
                    cl = c.execute("SELECT * FROM checklists WHERE project_id=? AND stage=?",
                                   (pid, stage)).fetchone()
                items = [dict(x) for x in c.execute(
                    "SELECT * FROM checklist_items WHERE checklist_id=? ORDER BY seq",
                    (cl["id"],))]
                return self._json(200, {"checklist": dict(cl), "items": items})

            if p == "/api/drawings":
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                pid = int(q.get("project", [0])[0])
                dw = [dict(x) for x in c.execute(
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
                return self._json(200, {"drawings": dw, "transmittals": tr})

            if p == "/api/visits":
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                sql = ("SELECT v.*, p.name pname FROM site_visits v "
                       "LEFT JOIN projects p ON p.id=v.project_id")
                args = []
                if q.get("project"):
                    sql += " WHERE v.project_id=?"; args.append(int(q["project"][0]))
                sql += " ORDER BY v.visited_on DESC LIMIT 100"
                return self._json(200, {"rows": [dict(x) for x in c.execute(sql, args)]})

            m = re.match(r"^/api/notes/([a-z]+)/(\d+)$", p)
            if m:
                rows = c.execute("SELECT * FROM notes WHERE entity=? AND entity_id=? "
                                 "ORDER BY id DESC LIMIT 50", (m.group(1), int(m.group(2))))
                return self._json(200, {"rows": [dict(x) for x in rows]})

            if p == "/api/myqueue":
                me = c.execute("SELECT * FROM people WHERE lower(email)=?",
                               (who["email"].lower(),)).fetchone()
                pid = me["id"] if me else -1
                cfg = timecfg(c)
                mine = [task_view(r, cfg) for r in c.execute(
                    "SELECT * FROM tasks WHERE person_id=? AND status!='done' "
                    "ORDER BY planned_ed LIMIT 60", (pid,))]
                team = me["team"] if me else None
                unass = [task_view(r, cfg) for r in c.execute(
                    "SELECT * FROM tasks WHERE person_id IS NULL AND team=? "
                    "AND is_external=0 AND status!='done' ORDER BY planned_ed LIMIT 40",
                    (team,))] if team else []
                cases = [dict(x) for x in c.execute(
                    """SELECT ca.*, p.name pname FROM cases ca
                       JOIN case_lanes l ON l.case_id=ca.id AND l.idx=ca.position
                       LEFT JOIN projects p ON p.id=ca.project_id
                       WHERE ca.status='open' AND l.is_stub=0 ORDER BY l.entered_at""")]
                ob = [dict(x) for x in c.execute(
                    "SELECT o.*, p.name pname FROM obligations o "
                    "LEFT JOIN projects p ON p.id=o.project_id "
                    "WHERE o.done_at IS NULL ORDER BY o.due_on LIMIT 30")]
                return self._json(200, {"me": dict(me) if me else None, "tasks": mine,
                                        "unassigned": unass, "cases": cases,
                                        "obligations": ob})

            if p == "/api/exec":
                return self._json(200, self._exec(c))

            if p == "/api/today":
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

            if p == "/api/search":
                return self._json(200, self._search(c))

            m = re.match(r"^/api/entity/([a-z_]+)/(\d+)$", p)
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

            if p == "/api/catalog":
                rows = c.execute("SELECT * FROM products ORDER BY team,stage,workflow,seq")
                # Backlog #27 asked for a formal catalogue: for each workflow,
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
                    "stats": catalog.stats(),
                    "conflicts": catalog.conflicts(),
                    "stages": [{"stage": s, "name": n, "phase": ph, "detail": d}
                               for s, n, ph, d in catalog.STAGES],
                    "phases": catalog.PHASES,
                })

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

    # ── one box over every register ──
    def _search(self, c):
        """Search was on the "not built" list. It is the difference between a
        system you navigate and a system you ask. One query, every register."""
        from urllib.parse import urlparse, parse_qs
        q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0].strip()
        if len(q) < 2:
            return {"q": q, "groups": []}
        like = "%" + q.replace("%", "") + "%"
        G = []

        def group(kind, label, sql, args, row):
            hits = [row(r) for r in c.execute(sql, args)]
            if hits:
                G.append({"kind": kind, "label": label, "rows": hits})

        group("project", "Projects",
              "SELECT * FROM projects WHERE name LIKE ? OR code LIKE ? OR city LIKE ? "
              "ORDER BY is_bau,name LIMIT 8", (like, like, like),
              lambda r: {"id": r["id"], "title": r["name"],
                         "sub": f"{r['code']} · {r['kind']} · {r['city']} · {r['status']}"})
        group("case", "Cases",
              "SELECT ca.*, p.name pname FROM cases ca LEFT JOIN projects p "
              "ON p.id=ca.project_id WHERE ca.ref LIKE ? OR ca.title LIKE ? "
              "ORDER BY ca.status, ca.raised_at DESC LIMIT 10", (like, like),
              lambda r: {"id": r["id"], "title": f"{r['ref']} · {r['title']}",
                         "sub": f"{r['pname'] or ''} · {r['status']}"})
        group("task", "Steps and tasks",
              "SELECT t.*, p.name pname FROM tasks t LEFT JOIN projects p "
              "ON p.id=t.project_id WHERE t.title LIKE ? OR t.workflow LIKE ? "
              "ORDER BY t.status!='running', t.planned_ed LIMIT 12", (like, like),
              lambda r: {"id": r["id"], "title": r["title"],
                         "sub": f"{r['pname'] or ''} · stage {r['stage']} · "
                                f"{r['team']} · {r['status']}"})
        group("drawing", "Drawings",
              "SELECT d.*, p.name pname FROM drawings d LEFT JOIN projects p "
              "ON p.id=d.project_id WHERE d.number LIKE ? OR d.title LIKE ? "
              "ORDER BY d.number LIMIT 10", (like, like),
              lambda r: {"id": r["id"], "title": f"{r['number']} · {r['title']}",
                         "sub": f"{r['pname'] or ''} · Rev {r['revision']} · {r['status']}"})
        group("transmittal", "Transmittals",
              "SELECT t.*, p.name pname FROM transmittals t LEFT JOIN projects p "
              "ON p.id=t.project_id WHERE t.ref LIKE ? OR t.phase LIKE ? "
              "OR t.issued_to LIKE ? ORDER BY t.issued_at DESC LIMIT 8",
              (like, like, like),
              lambda r: {"id": r["id"], "title": f"{r['ref']} · {r['phase']}",
                         "sub": f"{r['pname'] or ''} · to {r['issued_to']}"})
        group("person", "People",
              "SELECT * FROM people WHERE name LIKE ? OR designation LIKE ? "
              "OR team LIKE ? ORDER BY tier,name LIMIT 10", (like, like, like),
              lambda r: {"id": r["id"], "title": r["name"],
                         "sub": f"{r['designation']} · {r['team']}"})
        group("llr", "Lessons learned",
              "SELECT * FROM llr WHERE title LIKE ? OR detail LIKE ? OR category LIKE ? "
              "ORDER BY raised_at DESC LIMIT 8", (like, like, like),
              lambda r: {"id": r["id"], "title": r["title"],
                         "sub": f"{r['category'] or ''} · {r['status']}"})
        group("coordination", "Open asks",
              "SELECT co.*, p.name pname FROM coordination co LEFT JOIN projects p "
              "ON p.id=co.project_id WHERE co.closed_at IS NULL AND (co.ask LIKE ? "
              "OR co.to_lane LIKE ?) ORDER BY co.opened_at LIMIT 8", (like, like),
              lambda r: {"id": r["id"], "title": r["ask"],
                         "sub": f"{r['pname'] or ''} · waiting on {r['to_lane']}"})
        group("authority", "Authority file",
              "SELECT a.*, p.name pname FROM authority a LEFT JOIN projects p "
              "ON p.id=a.project_id WHERE a.ref LIKE ? OR a.title LIKE ? "
              "OR a.authority LIKE ? ORDER BY a.submitted_on DESC LIMIT 8",
              (like, like, like),
              lambda r: {"id": r["id"], "title": f"{r['ref']} · {r['title']}",
                         "sub": f"{r['pname'] or ''} · {r['authority']} · {r['status']}"})
        group("visit", "Site visits",
              "SELECT v.*, p.name pname FROM site_visits v LEFT JOIN projects p "
              "ON p.id=v.project_id WHERE v.findings LIKE ? "
              "ORDER BY v.visited_on DESC LIMIT 6", (like,),
              lambda r: {"id": r["id"], "title": (r["findings"] or "")[:80],
                         "sub": f"{r['pname'] or ''} · {r['visited_on']}"})
        group("product", "Catalog steps",
              "SELECT * FROM products WHERE step LIKE ? OR workflow LIKE ? "
              "ORDER BY stage,seq LIMIT 12", (like, like),
              lambda r: {"id": r["id"], "title": r["step"],
                         "sub": f"{r['workflow']} · stage {r['stage']} · {r['team']}"})
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
                st = many("SELECT * FROM project_stages WHERE project_id=? "
                          "ORDER BY stage", eid)
                cls = {r["stage"]: dict(r) for r in c.execute(
                    "SELECT * FROM checklists WHERE project_id=?", (eid,))}
                for s in st:
                    cl = cls.get(s["stage"])
                    s["checklist"] = cl
                    if cl:
                        row = one("SELECT COUNT(*) n, COALESCE(SUM(done),0) d "
                                  "FROM checklist_items WHERE checklist_id=?", cl["id"])
                        s["checks"], s["checks_done"] = row["n"], row["d"]
                extra = {
                    "stages": st,
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
                prod = one("SELECT * FROM products WHERE id=?", rec["product_id"]) \
                    if rec["product_id"] else None
                extra = {
                    "view": task_view(rec, timecfg(c)),
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
                             if rec["origin_entity"] and rec["origin_id"] else None)}

        elif kind == "finding":
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
                # the visit is now a container: its findings ARE its content
                extra = {"findings": many(
                    "SELECT f.*, pe.name person, ca.ref case_ref FROM findings f "
                    "LEFT JOIN people pe ON pe.id=f.person_id "
                    "LEFT JOIN cases ca ON ca.id=f.case_id "
                    "WHERE f.visit_id=? ORDER BY f.seq", eid),
                    "prior": many(
                    "SELECT v.*, (SELECT COUNT(*) FROM findings f WHERE f.visit_id=v.id) n"
                    " FROM site_visits v WHERE v.project_id=? AND v.id!=? "
                    "ORDER BY v.visited_on DESC LIMIT 8", rec["project_id"], eid)}

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

    # ── payloads ──
    def _bootstrap(self, c, who):
        q = lambda s, *a: c.execute(s, a).fetchone()[0]
        projects = [dict(r) for r in c.execute(
            "SELECT * FROM projects ORDER BY is_bau, name")]
        people = [dict(r) for r in c.execute(
            "SELECT * FROM people WHERE active=1 ORDER BY team, tier, name")]

        open_cases = q("SELECT COUNT(*) FROM cases WHERE status='open'")
        at_zd = q("""SELECT COUNT(*) FROM cases ca JOIN case_lanes l
                     ON l.case_id=ca.id AND l.idx=ca.position
                     WHERE ca.status='open' AND l.is_stub=0""")
        stuck = q("""SELECT COUNT(*) FROM cases ca JOIN case_lanes l
                     ON l.case_id=ca.id AND l.idx=ca.position
                     WHERE ca.status='open' AND l.is_stub=1""")
        coord_open = q("SELECT COUNT(*) FROM coordination WHERE closed_at IS NULL")
        coord_over = q("""SELECT COUNT(*) FROM coordination WHERE closed_at IS NULL
                          AND sla_days IS NOT NULL
                          AND julianday('now')-julianday(opened_at) > sla_days*1.4""")
        ob_miss = q("SELECT COUNT(*) FROM obligations WHERE done_at IS NULL "
                    "AND due_on < date('now')")

        # the headline: total wait time booked against parties outside the department
        wait_total = q("SELECT COALESCE(SUM(wait_days),0) FROM tasks") or 0
        own_total = q("SELECT COALESCE(SUM(own_days),0) FROM tasks") or 0

        stages_late = q("""SELECT COUNT(*) FROM project_stages ps
                           WHERE ps.status='running' AND ps.planned_end IS NOT NULL
                           AND date(ps.planned_end) < date('now')""")

        return {
            "ok": True,
            "user": public_user(who["email"], who),
            "projects": projects, "people": people,
            "teams": catalog.TEAMS,
            "departments": [{"name": n, "kind": k} for n, k in catalog.DEPARTMENTS],
            "priorities": store.priorities(c),
            "priority_default": store.setting(c, "priority.default", "Medium"),
            "unconfirmed": q("SELECT COUNT(*) FROM settings WHERE confirmed=0"),
            "ack_window": (store.setting(c, "ack.window_value", "24") + " "
                           + (store.setting(c, "ack.window_unit", "calendar_hours")
                              or "").replace("_", " ")),
            "finding_categories": actions.FINDING_CATEGORIES,
            "stages": [{"stage": s, "name": n, "phase": ph, "detail": d}
                       for s, n, ph, d in catalog.STAGES],
            "phases": catalog.PHASES,
            "routes": {k: {"label": v["label"], "source": v["source"],
                           "stage": v.get("stage"),
                           "value_routed": bool(v.get("value_routed")),
                           "lanes": [{"label": a, "owner": b, "sla": cc,
                                      "stub": store.is_stub(b)}
                                     for a, b, cc in v["lanes"]]}
                       for k, v in store.ROUTES.items()},
            "thresholds": {"petty": store.PKR_PETTY, "cpc": store.PKR_CPC,
                           "ceo": store.PKR_CEO},
            "kpi": {
                "projects": len([p for p in projects if not p["is_bau"]]),
                "people": len(people),
                "stages_late": stages_late,
                "open_cases": open_cases, "cases_at_zd": at_zd, "cases_stuck": stuck,
                "coord_open": coord_open, "coord_over": coord_over,
                "oblig_missed": ob_miss,
                "drawings": q("SELECT COUNT(*) FROM drawings"),
                "sheets_issued": q("SELECT COUNT(*) FROM transmittal_drawings"),
                "visits": q("SELECT COUNT(*) FROM site_visits"),
                "ncr_open": q("SELECT COUNT(*) FROM cases WHERE type='NCR' "
                              "AND status='open'"),
                "authority_open": q("SELECT COUNT(*) FROM authority WHERE status IN "
                                    "('submitted','observations')"),
                "authority_days": q("SELECT COALESCE(SUM(julianday('now')-"
                                    "julianday(submitted_on)),0) FROM authority "
                                    "WHERE status IN ('submitted','observations')"),
                "findings": q("SELECT COUNT(*) FROM findings"),
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
                "lessons_open": q("SELECT COUNT(*) FROM llr WHERE status='open'"),
                "lessons_adopted": q("SELECT COUNT(*) FROM llr WHERE status='adopted'"),
                "template_items": q("SELECT COUNT(*) FROM checklist_templates "
                                    "WHERE active=1"),
                "blocked": q("SELECT COUNT(*) FROM changes WHERE blocked=1"),
                "own_days": own_total, "wait_days": wait_total,
                "wait_share": round(wait_total / (own_total + wait_total) * 100, 1)
                              if (own_total + wait_total) else 0,
            },
            "catalog_stats": catalog.stats(),
            "conflicts": catalog.conflicts(),
        }

    def _matrix(self, c):
        projects = [dict(r) for r in c.execute(
            "SELECT * FROM projects WHERE is_bau=0 ORDER BY name")]
        cells = {}
        for r in c.execute("SELECT * FROM project_stages"):
            cells[(r["project_id"], r["stage"])] = dict(r)
        # per (project,stage) task rollup
        # Backlog #24/#28/#29. The heatmap has to answer "how much time is being
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
            roll[(r["project_id"], r["stage"])] = dict(r)
        out = []
        for p in projects:
            row = {"project": p, "cells": []}
            for s, name, ph, _d in catalog.STAGES:
                cell = cells.get((p["id"], s), {"status": "not_started"})
                rr = roll.get((p["id"], s), {})
                own = rr.get("own") or 0
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
                    "late": rr.get("late") or 0,
                    "overdue": bool(cell.get("status") == "running"
                                    and cell.get("planned_end")
                                    and cell["planned_end"][:10] < store.today().isoformat()),
                })
            out.append(row)
        return {"rows": out,
                "stages": [{"stage": s, "name": n, "phase": ph}
                           for s, n, ph, _ in catalog.STAGES]}

    def _project(self, c, pid):
        p = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not p:
            return {"error": "no such project"}
        stages = [dict(r) for r in c.execute(
            "SELECT * FROM project_stages WHERE project_id=? ORDER BY stage", (pid,))]
        tasks = [task_view(r, timecfg(c)) for r in c.execute(
            "SELECT * FROM tasks WHERE project_id=? ORDER BY stage,team,seq", (pid,))]
        cases = [dict(r) for r in c.execute(
            "SELECT * FROM cases WHERE project_id=? ORDER BY status,raised_at DESC", (pid,))]
        coord = [dict(r, age=age_days(r["opened_at"])) for r in c.execute(
            "SELECT * FROM coordination WHERE project_id=? AND closed_at IS NULL "
            "ORDER BY opened_at", (pid,))]
        ob = [dict(r) for r in c.execute(
            "SELECT * FROM obligations WHERE project_id=? ORDER BY due_on DESC LIMIT 20", (pid,))]
        by_team = {}
        for t in tasks:
            b = by_team.setdefault(t["team"], {"own": 0, "wait": 0, "n": 0, "late": 0})
            b["own"] += t["own"]; b["wait"] += t["wait"]; b["n"] += 1
            b["late"] += 1 if t["late"] else 0
        visits = [dict(r) for r in c.execute(
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
                "stage_names": {s: n for s, n, _p, _d in catalog.STAGES}}

    def _team(self, c, team):
        tasks = [task_view(r, timecfg(c)) for r in c.execute(
            "SELECT * FROM tasks WHERE team=? ORDER BY stage,seq", (team,))]
        people = [dict(r) for r in c.execute(
            "SELECT * FROM people WHERE team=? AND active=1 ORDER BY tier,name", (team,))]
        done = [t for t in tasks if t["status"] == "done" and t["baseline"] is not None]
        on_time = sum(1 for t in done if not t["late"])
        own = sum(t["own"] for t in tasks)
        wait = sum(t["wait"] for t in tasks)
        rev = sum(t["revision"] for t in tasks)
        # per-workflow SLA
        wf = {}
        for t in tasks:
            w = wf.setdefault(t["workflow"] or "—",
                              {"n": 0, "done": 0, "late": 0, "own": 0, "wait": 0,
                               "base": 0, "rev": 0})
            w["n"] += 1
            w["own"] += t["own"]; w["wait"] += t["wait"]; w["rev"] += t["revision"]
            if t["baseline"]: w["base"] += t["baseline"]
            if t["status"] == "done":
                w["done"] += 1
                if t["late"]: w["late"] += 1
        # who owes this team what
        owed = [dict(r, age=age_days(r["opened_at"])) for r in c.execute(
            "SELECT * FROM coordination WHERE from_team=? AND closed_at IS NULL "
            "ORDER BY opened_at", (team,))]
        return {
            "team": team, "people": people, "workflows": wf, "owed": owed,
            "kpi": {"tasks": len(tasks), "done": len(done),
                    "on_time_pct": round(on_time / len(done) * 100, 1) if done else None,
                    "own_days": own, "wait_days": wait, "revisions": rev,
                    "wait_share": round(wait / (own + wait) * 100, 1) if (own + wait) else 0},
            "tasks": tasks[:400],
        }

    def _tasks(self, c):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        sql = "SELECT * FROM tasks WHERE 1=1"
        args = []
        for key, col in (("team", "team"), ("stage", "stage"), ("status", "status")):
            if key in q:
                sql += f" AND {col}=?"; args.append(q[key][0])
        if "project" in q:
            sql += " AND project_id=?"; args.append(int(q["project"][0]))
        sql += " ORDER BY stage,team,seq LIMIT 600"
        cfg = timecfg(c)
        return {"rows": [task_view(r, cfg) for r in c.execute(sql, args)]}

    def _cases(self, c):
        out = []
        for r in c.execute("SELECT ca.*, p.name pname, p.code pcode FROM cases ca "
                           "LEFT JOIN projects p ON p.id=ca.project_id "
                           "ORDER BY ca.status, ca.raised_at"):
            lanes = [dict(l) for l in c.execute(
                "SELECT * FROM case_lanes WHERE case_id=? ORDER BY idx", (r["id"],))]
            cur = lanes[r["position"]] if r["position"] < len(lanes) else None
            v = r["value_pkr"]
            gate = ("CEO Office" if v and v >= store.PKR_CEO else
                    "CPC" if v and v >= store.PKR_CPC else
                    "Petty cash" if v and v < store.PKR_PETTY else
                    "Dept head" if v else None)
            out.append(dict(r, lanes=lanes, current=cur,
                            at_zd=bool(cur and not cur["is_stub"]),
                            age=age_days(cur["entered_at"]) if cur else 0,
                            overdue=bool(cur and cur["sla_days"] and
                                         age_days(cur["entered_at"]) > cur["sla_days"]),
                            value_gate=gate,
                            route=store.ROUTES.get(r["type"], {}).get("label", r["type"]),
                            source=store.ROUTES.get(r["type"], {}).get("source", "")))
        return {"rows": out, "routes": list(store.ROUTES.keys())}

    def _coord(self, c):
        rows = []
        for r in c.execute("SELECT co.*, p.name pname, p.code pcode FROM coordination co "
                           "LEFT JOIN projects p ON p.id=co.project_id "
                           "WHERE co.closed_at IS NULL ORDER BY co.opened_at"):
            a = age_days(r["opened_at"])
            rows.append(dict(r, age=a, external=store.is_stub(r["to_lane"]),
                             over=bool(r["sla_days"] and a > r["sla_days"]),
                             overrun=(a - r["sla_days"]) if r["sla_days"] else None))
        # who owes the department the most days
        by_lane = {}
        for r in rows:
            b = by_lane.setdefault(r["to_lane"], {"n": 0, "days": 0, "over": 0})
            b["n"] += 1; b["days"] += r["age"]; b["over"] += 1 if r["over"] else 0
        return {"rows": rows, "by_lane": by_lane}

    def _oblig(self, c):
        rows = [dict(r) for r in c.execute(
            "SELECT o.*, p.name pname FROM obligations o "
            "LEFT JOIN projects p ON p.id=o.project_id ORDER BY o.due_on DESC LIMIT 200")]
        t = store.today().isoformat()
        for r in rows:
            r["missed"] = bool(not r["done_at"] and r["due_on"] < t)
            r["pending"] = bool(not r["done_at"] and r["due_on"] >= t)
        agg = {}
        for r in rows:
            a = agg.setdefault(r["label"], {"due": 0, "done": 0, "missed": 0})
            a["due"] += 1
            a["done"] += 1 if r["done_at"] else 0
            a["missed"] += 1 if r["missed"] else 0
        return {"rows": rows, "summary": agg}

    # ── writes ──
    def do_POST(self):
        if not self._strip():
            self.send_error(404); return
        p = self.path.split("?")[0]

        if p == "/api/login":
            return self._login()

        who = self._who()
        if not who:
            return self._json(401, {"error": "Sign in to use ZD PULSE."})
        d = self._body() or {}
        c = store.conn()
        try:
            if p in actions.DISPATCH:
                try:
                    out = actions.DISPATCH[p](c, who, d)
                    c.commit()
                    return self._json(200, out)
                except actions.Refused as x:
                    c.commit()          # the refusal itself was logged
                    return self._json(409, x.payload)
                except Exception as x:
                    c.rollback()
                    return self._json(400, {"error": str(x)})

            if p == "/api/task/start":
                return self._task_move(c, who, d, "start")
            if p == "/api/task/finish":
                return self._task_move(c, who, d, "finish")
            if p == "/api/task/revise":
                return self._task_move(c, who, d, "revise")
            if p == "/api/case/advance":
                return self._case_advance(c, who, d)
            if p == "/api/coordination/close":
                cid = int(d.get("id") or 0)
                r = c.execute("SELECT * FROM coordination WHERE id=?", (cid,)).fetchone()
                if not r:
                    return self._json(404, {"error": "no such item"})
                c.execute("UPDATE coordination SET closed_at=? WHERE id=?", (store.now(), cid))
                store.log(c, who["name"], who.get("tier", 3), "coordination", cid, "close",
                          f"Closed ask to {r['to_lane']}: {r['ask']}", team=r["from_team"])
                c.commit()
                return self._json(200, {"ok": True})
            return self._json(404, {"error": "no such endpoint"})
        finally:
            c.close()

    def _task_move(self, c, who, d, action):
        tid = int(d.get("id") or 0)
        r = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        if not r:
            return self._json(404, {"error": "no such task"})
        pname = c.execute("SELECT name FROM projects WHERE id=?",
                          (r["project_id"],)).fetchone()["name"]
        t = store.today().isoformat()

        if action == "start":
            if r["actual_sd"]:
                return self._json(409, {"error": "already started"})
            c.execute("UPDATE tasks SET actual_sd=?,status=?,updated_at=? WHERE id=?",
                      (t, "waiting" if r["is_external"] else "running", store.now(), tid))
            summ = f"Started · {r['title']}"
        elif action == "finish":
            if not r["actual_sd"]:
                # a soft gate: refused, and the refusal is logged. blocked attempts
                # are the highest-signal rows in the ledger — nobody counts them today.
                store.log(c, who["name"], who.get("tier", 3), "task", tid, "finish",
                          f"BLOCKED — finish before start · {r['title']}",
                          project=pname, team=r["team"], blocked=1)
                c.commit()
                return self._json(409, {"error": "Cannot finish a task that never started.",
                                        "blocked": True})
            days = store.working_days_between(r["actual_sd"], t) or 0
            if r["is_external"]:
                c.execute("UPDATE tasks SET actual_ed=?,status='done',wait_days=?,"
                          "updated_at=? WHERE id=?", (t, days, store.now(), tid))
                c.execute("UPDATE coordination SET closed_at=? WHERE task_id=? "
                          "AND closed_at IS NULL", (store.now(), tid))
            else:
                c.execute("UPDATE tasks SET actual_ed=?,status='done',own_days=?,"
                          "updated_at=? WHERE id=?", (t, days, store.now(), tid))
            summ = f"Finished in {days}d · {r['title']}"
        else:  # revise — the "Changes Required" loop
            c.execute("UPDATE tasks SET revision=revision+1,status='running',"
                      "actual_ed=NULL,updated_at=? WHERE id=?", (store.now(), tid))
            summ = f"Revision {r['revision']+1} · {r['title']}"

        store.log(c, who["name"], who.get("tier", 3), "task", tid, action, summ,
                  project=pname, team=r["team"])
        c.commit()
        row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        return self._json(200, {"ok": True, "task": task_view(row, timecfg(c))})

    def _case_advance(self, c, who, d):
        cid = int(d.get("id") or 0)
        ca = c.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
        if not ca:
            return self._json(404, {"error": "no such case"})
        lanes = [dict(l) for l in c.execute(
            "SELECT * FROM case_lanes WHERE case_id=? ORDER BY idx", (cid,))]
        pos = ca["position"]
        if pos >= len(lanes):
            return self._json(409, {"error": "case already at end of route"})
        cur = lanes[pos]
        pname = c.execute("SELECT name FROM projects WHERE id=?",
                          (ca["project_id"],)).fetchone()["name"]

        # The gate. A lane owned by a department whose system does not exist yet
        # cannot be actioned from inside ZD PULSE — and the attempt is recorded,
        # because "how often are we blocked waiting on PM" is the number that
        # justifies building the PM system.
        if cur["is_stub"] and not d.get("force"):
            store.log(c, who["name"], who.get("tier", 3), "case", cid, "advance",
                      f"BLOCKED — {ca['ref']} sits with {cur['owner_lane']} "
                      f"({age_days(cur['entered_at'])}d), outside ZD PULSE",
                      project=pname, blocked=1)
            c.commit()
            return self._json(409, {
                "error": f"This lane belongs to {cur['owner_lane']} — outside Arch & Design.",
                "detail": "Logged as an external wait. It becomes actionable when that "
                          "department's system is connected.",
                "blocked": True, "lane": cur["owner_lane"],
                "waiting_days": age_days(cur["entered_at"])})

        c.execute("UPDATE case_lanes SET left_at=?,actor=?,outcome=? WHERE id=?",
                  (store.now(), who["name"], d.get("outcome") or "passed", cur["id"]))
        nxt = pos + 1
        if nxt >= len(lanes):
            c.execute("UPDATE cases SET position=?,status='approved',closed_at=? WHERE id=?",
                      (nxt, store.now(), cid))
        else:
            c.execute("UPDATE case_lanes SET entered_at=? WHERE id=?",
                      (store.now(), lanes[nxt]["id"]))
            c.execute("UPDATE cases SET position=? WHERE id=?", (nxt, cid))
        store.log(c, who["name"], who.get("tier", 3), "case", cid, "advance",
                  f"{ca['ref']} · {cur['label']} → "
                  f"{lanes[nxt]['label'] if nxt < len(lanes) else 'CLOSED'}",
                  project=pname)
        c.commit()
        return self._json(200, {"ok": True})

    def _login(self):
        d = self._body()
        if d is None:
            return self._json(400, {"error": "bad json"})
        email = str(d.get("email", "")).strip().lower()
        pw = d.get("password") or ""
        users = load_users()
        u = users.get(email)
        if not u or not verify_pw(pw, u.get("salt", ""), u.get("hash", "")):
            return self._json(401, {"error": "That email or password is not right."})
        u["lastLogin"] = store.now()
        save_users(users)
        return self._json(200, {"ok": True, "token": make_token(email),
                                "user": public_user(email, u)})

    def end_headers(self):
        if self.path.endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    store.seed()
    c = store.conn(); store.demo(c); c.close()
    seed_users()
    s = catalog.stats()
    print(f"ZD PULSE on http://{HOST}:{PORT}{MOUNT}/")
    print(f"  catalog  {s['workflows']} workflows ({s['from_booklet']} booklet + "
          f"{s['from_manual']} manual) · {s['steps']} steps · {s['stations']} stations")
    print(f"           {s['tat_conflicts']} TAT conflicts · "
          f"{s['unknown_tat']} steps with no duration · "
          f"{len(store.ROUTES)} case routes · {len(actions.DISPATCH) + 5} write actions")
    Server((HOST, PORT), H).serve_forever()
