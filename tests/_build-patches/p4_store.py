"""Backlog #7-#10: visit -> multiple findings -> evidence -> team -> RFI -> history.
   Backlog #15/#17: lessons carry root cause, delay ownership and head/audit visibility."""
PATH = r"c:\Users\Muhammad Ashhad\Desktop\pulsearch\store.py"
src = open(PATH, encoding="utf-8").read()
S = "\u00a7"
D = "\u2014"


def sub(old, new):
    global src
    assert old in src, "anchor: " + old[:70]
    src = src.replace(old, new, 1)


# ══════════════════════════════════════════════════════════════════════════
# replace _demo_visits wholesale
# ══════════════════════════════════════════════════════════════════════════
start = src.index("def _demo_visits(c):")
end = src.index("def _demo_llr(c):")

NEWVISITS = '''def _demo_visits(c):
    """Manual %(S)s15 and Haroon's review %(S)s4-%(S)s6.

    The old shape put every observation from a visit into one `findings` text
    column. The review killed it in one line: "A visit should not become one large
    unstructured record." Five problems found on one walk were one row, with one
    owner, one status and one clock %(D)s so four of them could not be assigned,
    timed or closed, and none could be shown to have happened before.

    Now: a visit is a container with a date and a person. Each finding is its own
    record with a category, a location, an owner, a priority, a TAT and evidence,
    and any finding can become an NCR or a task on its own. The visit summary is
    derived from its findings rather than being the place they hide.
    """
    if c.execute("SELECT COUNT(*) FROM site_visits").fetchone()[0]:
        return
    people = {}
    for r in c.execute("SELECT id,name,team FROM people WHERE tier<=2"):
        people.setdefault(r["team"], []).append((r["id"], r["name"]))
    visitors = ["Ahmed Khan", "Umer Farooq", "Aarij Ali", "Yahya Ali Khan"]

    k = 0
    for pr in c.execute("SELECT id,name,code FROM projects WHERE is_bau=0").fetchall():
        pid, code = pr["id"], pr["code"]
        _done, top = _reached(c, pid)
        if top < 11:
            continue
        seen = {}          # (category, location) -> earliest finding id, for #10
        for m in range(3):
            k += 1
            day = today() - datetime.timedelta(days=28 * m + 4)
            # The review's own example: "During one visit, 5 separate problems
            # may be identified." The most recent visit on the furthest-along
            # project is that visit.
            n_find = 5 if (m == 0 and top >= 13) else (1 + (k %% 4))
            picks = [FINDING_SET[(k * 3 + i) %% len(FINDING_SET)] for i in range(n_find)]
            nc_total = sum(1 for p in picks if p[6])
            c.execute("INSERT INTO site_visits(project_id,visited_on,by_whom,findings,"
                      "non_compliance,photos,created_at) VALUES(?,?,?,?,?,?,?)",
                      (pid, day.isoformat(), visitors[k %% len(visitors)],
                       f"{n_find} finding{'s' if n_find != 1 else ''} recorded"
                       + (f", {nc_total} non-compliant" if nc_total else
                          ", none non-compliant"),
                       1 if nc_total else 0, 4 + (k %% 11), now()))
            vid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

            for i, (cat, title, desc, loc, team, prio, nc) in enumerate(picks):
                tat = {"Critical": 3, "High": 7, "Medium": 14, "Low": 21}[prio]
                due = _add_working_days(day, tat)
                pool = people.get(team) or [(None, None)]
                pid_person, _pname = pool[(k + i) %% len(pool)]
                # oldest visits are mostly closed out; the newest are live
                if m >= 2:
                    st, res = "closed", "Rectified and verified on the following visit."
                elif m == 1:
                    st, res = ("resolved", "Contractor rectified; awaiting joint "
                               "re-inspection.") if i %% 2 == 0 else ("in_progress", None)
                else:
                    st, res = ("assigned" if pid_person else "open"), None
                prev = seen.get((cat, loc))
                c.execute("INSERT INTO findings(visit_id,project_id,seq,category,title,"
                          "description,location,responsible_team,person_id,priority,"
                          "tat_days,due_on,status,non_compliance,raised_by,raised_at,"
                          "resolution,resolved_by,resolved_at,recurrence_of) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (vid, pid, i + 1, cat, title, desc, loc, team, pid_person,
                           prio, tat, due.isoformat(), st, nc,
                           visitors[k %% len(visitors)], day.isoformat(),
                           res, "Ahmed Khan" if res else None,
                           (day + datetime.timedelta(days=tat)).isoformat()
                           if res else None, prev))
                fid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                seen.setdefault((cat, loc), fid)

                # #8 — evidence stays attached to the FINDING, not the visit
                for kind, label in (("Photo set", "Site photographs"),
                                    ("Report", "Inspection note")):
                    if kind == "Report" and prio in ("Medium", "Low"):
                        continue
                    _add_doc(c, "finding", fid, pid,
                             f"{label} %(D)s {title[:44]}", kind,
                             f"https://drive.zameen.com/zd/{code}/visits/"
                             f"{day.isoformat()}/F{fid}-{kind.split()[0].lower()}.pdf",
                             who=visitors[k %% len(visitors)])

                # #9 — a non-compliant finding becomes an NCR on the %(S)s16 route,
                # raised FROM the finding, so the chain is walkable both ways
                if nc and st in ("open", "assigned", "in_progress"):
                    cid, ref = open_case(
                        c, "NCR", pid, code, title, None,
                        visitors[k %% len(visitors)], day.isoformat(),
                        f"{cat} %(D)s {loc}. {desc}", position=1,
                        origin=f"finding #{fid} on site visit #{vid}",
                        priority=prio, tat_days=tat,
                        from_team="Architecture", to_team=team,
                        origin_entity="finding", origin_id=fid)
                    c.execute("UPDATE findings SET case_id=? WHERE id=?", (cid, fid))
                    c.execute("INSERT INTO coordination(project_id,stage,from_team,"
                              "to_lane,ask,sla_days,priority,opened_at) "
                              "VALUES(?,?,?,?,?,?,?,?)",
                              (pid, 13, "Architecture", "QA/QC",
                               f"{ref} %(D)s joint re-inspection after rectification",
                               5, prio, day.isoformat()))
                    log(c, visitors[k %% len(visitors)], 1, "finding", fid, "create",
                        f"Non-compliance %(D)s {title[:60]} %(D)s {ref} raised",
                        project=pr["name"])


'''  % {"S": S, "D": D}

src = src[:start] + NEWVISITS + src[end:]

# ══════════════════════════════════════════════════════════════════════════
# lessons gain root cause / delay ownership / head + audit visibility
# ══════════════════════════════════════════════════════════════════════════
sub('''    L = [
        # (project, stage, discipline, category, title, detail, impact, status,
        #  ruling, promote_stage, promoted_text)''',
'''    # (project, stage, discipline, category, title, detail, impact, status,
    #  ruling, promote_stage, promoted_text, root_cause, delay_kind, delay_owner,
    #  delay_days, preventive_action, improvement_status)
    #
    # Backlog #17: "SLA/TAT took too long" has to be answerable %(D)s why, where,
    # whose, internal or external, was there a dependency, what changes. Every
    # entry below carries that, because a lesson that records only the symptom
    # cannot drive an improvement and will be raised again next project.
    RC = {
     0: ("Two disciplines generated the submission set from different layout "
         "revisions and no reconciliation step existed before printing.",
         "internal", "Architecture / Structure", 20,
         "Add a joint area-statement reconciliation, initialled by all three "
         "disciplines, as a gate before the submission set is printed.", "done"),
     1: ("Approval was given verbally on a site walk. There was no register "
         "entry and no retained sample to compare the delivery against.",
         "process", "Architecture", 15,
         "No mock-up is approved without a dated register entry and a retained "
         "physical sample.", "done"),
     2: ("The architectural ceiling level was issued for construction while the "
         "MEP duct route was still under revision. Neither discipline owned the "
         "void dimension.",
         "dependency", "Architecture / MEP", 12,
         "Make the ceiling void schedule a joint deliverable that neither "
         "discipline can issue alone.", "done"),
     3: ("Three manuals define MAR with different scopes and different approval "
         "chains, and no document arbitrates between them.",
         "process", "Cross-manual governance", None,
         "One owner per acronym. Publish a single definitions annexure across "
         "the four manuals.", "proposed"),
     4: ("Two source documents publish different overall TATs for the same "
         "stage and neither is marked as superseding the other.",
         "process", "Document control", None,
         "Ahmed to rule which document is canonical, then re-baseline. Until "
         "then no stage SLA is enforceable.", "agreed"),
     5: ("The annexure the Manual makes mandatory was never written, so the "
         "gate existed but had no content behind it.",
         "process", "Document control", None,
         "Author the annexure per stage in-system and put it under the same "
         "change control as the Manual.", "in_progress"),
     6: ("The booklet's duration column is blank for these steps and no "
         "estimate was ever substituted.",
         "process", "Structure", None,
         "Every catalog step carries a duration or an explicit 'variable, "
         "depends on <party>' %(D)s never a blank.", "proposed"),
     7: ("VE was triggered on the tender return rather than on the QS estimate, "
         "so options were studied after the contractor was engaged.",
         "process", "Project Management", 30,
         "Trigger VE on the QS estimate at stage 10. A VE case raised after "
         "tender award must state why it was not raised earlier.", "agreed"),
    }
    L = [
        # (project, stage, discipline, category, title, detail, impact, status,
        #  ruling, promote_stage, promoted_text)''' % {"D": D})

sub('''        c.execute("INSERT INTO llr(project_id,stage,discipline,category,title,detail,"
                  "impact,raised_by,raised_at,source,status,ruling,ruled_by,ruled_at)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (pid, stage, disc, cat, title, detail, impact,
                   "Ahmed Khan" if i %% 2 else "Haroon Noon", raised,
                   "Design Manual %(SS)s7.6", status, ruling or None,
                   "Haroon Noon" if status in ("ruled", "adopted") else None,
                   raised if status in ("ruled", "adopted") else None))''' % {"SS": S},
'''        rc, dkind, downer, ddays, prev, istat = RC.get(
            i, (None, None, None, None, None, "proposed"))
        # #15 — the moment a lesson is raised the head sees it, and Audit sees it
        # from whichever status the governance setting says.
        head_seen = raised + "T17:00:00" if setting_bool(
            c, "lessons.notify_head", True) else None
        audit_gate = setting(c, "lessons.audit_from_status", "ruled")
        rank = {"open": 0, "ruled": 1, "adopted": 2}
        audit_seen = (raised + "T17:05:00"
                      if setting_bool(c, "lessons.notify_audit", True)
                      and rank.get(status, 0) >= rank.get(audit_gate, 1) else None)
        c.execute("INSERT INTO llr(project_id,stage,discipline,category,title,detail,"
                  "impact,raised_by,raised_at,source,status,ruling,ruled_by,ruled_at,"
                  "root_cause,delay_kind,delay_owner,delay_days,preventive_action,"
                  "improvement_status,improvement_owner,head_dept,head_notified_at,"
                  "audit_notified_at,priority)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (pid, stage, disc, cat, title, detail, impact,
                   "Ahmed Khan" if i %% 2 else "Haroon Noon", raised,
                   "Design Manual %(SS)s7.6", status, ruling or None,
                   "Haroon Noon" if status in ("ruled", "adopted") else None,
                   raised if status in ("ruled", "adopted") else None,
                   rc, dkind, downer, ddays, prev, istat,
                   "Haroon Noon" if istat in ("agreed", "in_progress", "done") else None,
                   disc or "Architecture", head_seen, audit_seen,
                   "Critical" if (ddays or 0) >= 20 else
                   "High" if ddays else "Medium"))''' % {"SS": S})

open(PATH, "w", encoding="utf-8").write(src)
print("store.py: structured findings + lesson root-cause analysis")
