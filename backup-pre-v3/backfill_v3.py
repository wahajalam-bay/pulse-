"""
backfill_v3.py -- populate the v3 tables from data already in the system.

Register section 7 is explicit that existing records must not be discarded
when ZD becomes the structured system. So the single free-text findings blob
on each site visit is parsed into structured visit_findings rows, with the
original text preserved verbatim on the visit record.

Idempotent: skips any visit that already has structured findings.
Pass --reset to clear and rebuild the derived finding rows.
"""
import re
import sqlite3
import sys
from datetime import datetime, timedelta

import definitions as D

DB = "data/zd.db"


def iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def split_findings(blob):
    """Best-effort split of a free-text findings blob into separate findings.

    Splits on numbered lists and line breaks only. Deliberately NOT on
    semicolons: in this data a semicolon joins clauses of a single finding
    ("joint width does not match; shade variation across crates"), and
    splitting there produces dangling fragments that read as phantom issues.
    """
    if not blob or not blob.strip():
        return []
    t = blob.strip()
    parts = re.split(r"(?:(?<=\.)|(?<=\s)|^)\s*\d+\s*[.)]\s+", t)
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) > 1:
        return parts
    parts = [p.strip(" -*•\t") for p in re.split(r"[\n]+", t)]
    parts = [p for p in parts if p and len(p) > 3]
    return parts or [t]


CATEGORY_HINTS = [
    ("structural",    r"\b(crack|beam|column|slab|rebar|reinforc|structur|found)"),
    ("mep",           r"\b(mep|duct|hvac|conduit|plumb|drain|electric|cable|pipe|penetration)"),
    ("finishes",      r"\b(finish|paint|tile|marble|plaster|joint|render|mock-?up)"),
    ("safety",        r"\b(safety|hse|scaffold|ppe|hazard|guard)"),
    ("compliance",    r"\b(complian|ncr|deviat|approval|permit|code)"),
    ("workmanship",   r"\b(workmanship|align|level|tolerance|setting out)"),
    ("documentation", r"\b(drawing|document|as-?built|shop|revision|rev [a-z])"),
]

# Two traps here, both hit real seed rows:
#   "against"        -- appears in the neutral "inspected against S-301 Rev C",
#                       which would flag every clean inspection as a problem.
#   "deviation found"-- appears inside "NO deviation found", so matching it
#                       turns a passed inspection into an open finding. The
#                       negative case is handled by CLEAR_PAT instead.
PROBLEM_PAT = (r"\b(not match|does not|do not|clash|missing|not shown|variation|"
               r"defect|crack|fail|reject|shortfall)")

CLEAR_PAT = (r"\b(no deviation|no issue|no defect|as approved|setting out correct|"
             r"satisfactory|complies|in order|acceptable|correct)")


def categorise(text):
    low = text.lower()
    for key, pat in CATEGORY_HINTS:
        if re.search(pat, low):
            return key
    return "general"


def is_clear(text):
    """True when the note records a PASS rather than a problem.

    The seed blobs mix both: "slab reinforcement inspected against S-301
    Rev C. No deviation found." is a clean inspection, not an open finding,
    and must not sit in someone's queue as work to do. A problem phrase
    always wins over a clear phrase.
    """
    low = text.lower()
    if re.search(PROBLEM_PAT, low):
        return False
    return bool(re.search(CLEAR_PAT, low))


def severity_of(text):
    low = text.lower()
    if is_clear(text):
        return "none"
    if re.search(r"\b(urgent|critical|unsafe|collapse|severe|stop work)", low):
        return "high"
    if re.search(r"\b(clash|not match|does not match|missing|not shown|reject)", low):
        return "high"
    if re.search(r"\b(minor|cosmetic|small|touch.?up|shade variation)", low):
        return "low"
    return "medium"


def priority_of(sev):
    return {"none": "low", "high": "high",
            "medium": "medium", "low": "low"}.get(sev, "medium")


def main(reset=False):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    if reset:
        c.execute("delete from finding_evidence")
        c.execute("delete from visit_findings")
        c.commit()
        print("reset: cleared derived finding rows\n")

    added_f = added_e = skipped_nc = 0

    # ---------- visits -> structured findings (#7 #8 #10) ----------
    visits = c.execute("""select id, project_id, visited_on, by_whom,
                                 findings, non_compliance, photos
                          from site_visits order by id""").fetchall()
    for v in visits:
        if c.execute("select count(*) from visit_findings where visit_id=?",
                     (v["id"],)).fetchone()[0]:
            continue

        chunks = split_findings(v["findings"])

        # non_compliance in the seed data is a COUNT, not a description.
        # Inventing a finding row from a bare number produces noise, so it is
        # only promoted when it carries real text. The count still shows on
        # the visit record itself.
        nc_raw = str(v["non_compliance"] or "").strip()
        if nc_raw and nc_raw not in ("0", "None"):
            if nc_raw.isdigit():
                skipped_nc += int(nc_raw)
            else:
                chunks.append(nc_raw)

        for i, text in enumerate(chunks, start=1):
            sev = severity_of(text)
            clear = (sev == "none")
            title = text if len(text) <= 90 else text[:87].rsplit(" ", 1)[0] + "..."
            created = "%s 09:00:00" % v["visited_on"]
            tat = None if clear else (7 if sev == "high" else 14)
            due = None
            if tat:
                try:
                    due = iso(datetime.strptime(v["visited_on"], "%Y-%m-%d")
                              + timedelta(days=tat))
                except (ValueError, TypeError):
                    pass
            cur = c.execute("""insert into visit_findings
                (visit_id, seq, category, title, description, location,
                 severity, priority, assigned_dept, status, tat_days, due_at,
                 created_at)
                values (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (v["id"], i, categorise(text), title, text, None,
                             sev, priority_of(sev), None,
                             "observation" if clear else "open",
                             tat, due, created))
            fid = cur.lastrowid
            added_f += 1

            # photos on the visit attach to its first ACTIONABLE finding so
            # the evidence link is never orphaned (#8)
            if i == 1 and v["photos"] and not clear:
                try:
                    n = int(v["photos"])
                except (TypeError, ValueError):
                    n = 0
                for p in range(1, n + 1):
                    c.execute("""insert into finding_evidence
                        (finding_id, kind, filename, caption, uploaded_at)
                        values (?,?,?,?,?)""",
                              (fid, "photo",
                               "visit%d-photo%d.jpg" % (v["id"], p),
                               "Migrated from visit record", created))
                    added_e += 1

    # ---------- recurring detection (#10) ----------
    # a finding recurs when an earlier visit on the same project raised one in
    # the same category. Observations (passes) are excluded.
    recurring = 0
    rows = c.execute("""select f.id, f.category, v.project_id, v.visited_on
                        from visit_findings f join site_visits v on v.id=f.visit_id
                        where f.status != 'observation'
                        order by v.visited_on, f.id""").fetchall()
    seen = {}
    for r in rows:
        key = (r["project_id"], r["category"])
        if key in seen:
            c.execute("update visit_findings set recurring_of=? where id=?",
                      (seen[key], r["id"]))
            recurring += 1
        else:
            seen[key] = r["id"]

    # ---------- cases: ack window, TAT, priority (#3 #5 #6) ----------
    PRI = {"NCR": "high", "RFI": "medium", "DCR": "medium",
           "MAR": "medium", "SHOP": "low", "VET": "low"}
    TAT = {"NCR": 7, "RFI": 10, "DCR": 14, "MAR": 14, "SHOP": 10, "VET": 21}
    cased = 0
    for row in c.execute("select id, raised_at, type from cases").fetchall():
        raised = None
        for fmt, cut in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
            try:
                raised = datetime.strptime(row["raised_at"][:cut], fmt)
                break
            except (ValueError, TypeError):
                continue
        if raised is None:
            continue
        tat = TAT.get(row["type"], 14)
        # assigned directly, not via coalesce: the column DEFAULT already put
        # 'medium' on every row, so coalesce would never fall through.
        c.execute("""update cases set ack_due_at=?, tat_days=?, due_at=?,
                     priority=? where id=?""",
                  (iso(raised + timedelta(hours=D.ACK_WINDOW_HOURS)),
                   tat, iso(raised + timedelta(days=tat)),
                   PRI.get(row["type"], D.DEFAULT_PRIORITY), row["id"]))
        cased += 1

    # ---------- tasks: priority reflects real pressure (#5) ----------
    c.execute("update tasks set priority='high' where status in ('blocked','overdue')")
    c.execute("update tasks set priority=? where priority is null",
              (D.DEFAULT_PRIORITY,))

    # ---------- lessons: head + audit visibility (#11) ----------
    c.execute("update llr set head_visible=1 where head_visible is null")
    c.execute("""update llr set audit_visible=1
                 where lower(coalesce(category,'')) like '%delay%'
                    or lower(coalesce(title,''))    like '%delay%'
                    or lower(coalesce(category,'')) like '%sla%'
                    or lower(coalesce(title,''))    like '%tat%'""")
    c.execute("update llr set improvement_status='open' where improvement_status is null")

    c.commit()

    print("backfill_v3 complete\n")
    print("  visit findings created    %4d   (from %d visits)" % (added_f, len(visits)))
    print("  evidence rows created     %4d" % added_e)
    print("  recurring findings        %4d" % recurring)
    print("  cases given ack/TAT/pri   %4d" % cased)
    if skipped_nc:
        print("  non-compliance counts noted %2d  (bare counts, not made into findings)"
              % skipped_nc)

    print("\n  findings by status:")
    for r in c.execute("""select status, count(*) n from visit_findings
                          group by status order by n desc"""):
        print("    %-14s %3d" % (r[0], r[1]))
    print("\n  actionable findings by severity:")
    for r in c.execute("""select severity, count(*) n from visit_findings
                          where status != 'observation'
                          group by severity order by n desc"""):
        print("    %-14s %3d" % (r[0], r[1]))
    print("\n  cases by priority:")
    for r in c.execute("""select priority, count(*) n,
                                 group_concat(distinct type) t
                          from cases group by priority
                          order by case priority when 'critical' then 1
                                   when 'high' then 2 when 'medium' then 3
                                   else 4 end"""):
        print("    %-8s %3d   (%s)" % (r[0], r[1], r[2]))
    c.close()


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
