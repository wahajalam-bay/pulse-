"""
migrate_v3.py -- schema changes for Haroon's 1 Sep 2026 review backlog.

Idempotent: safe to run repeatedly. Adds columns/tables only when absent and
never drops or rewrites existing data.

Backlog items covered here (the schema half):
  #1  cross-team case routing          cases.to_dept / to_person_id
  #2  back-and-forth communication     case_thread
  #3  24h acknowledgement              cases.ack_due_at / acked_at / acked_by
  #4  escalation                       escalations
  #5  priority                         *.priority
  #6  priority separate from TAT       priority_history + *.tat_days
  #7  multiple findings per visit      visit_findings
  #8  evidence on findings             finding_evidence
  #9  finding -> team -> RFI           visit_findings.assigned_dept / rfi_case_id
  #10 historical visit data            (query-side, uses visit_findings)
  #17 root cause on lessons            llr.root_cause etc.
  #18 department list incl. Legal      departments
  #19 cross-module collaboration       entity_links
  #25 SLA -> TAT terminology           coordination.tat_days
  #36 tasks linked to origin           tasks.origin_kind / origin_id
"""
import sqlite3
import sys

import definitions as D

DB = "data/zd.db"


def cols(c, table):
    return {r[1] for r in c.execute("pragma table_info(%s)" % table)}


def tables(c):
    return {r[0] for r in c.execute(
        "select name from sqlite_master where type='table'")}


def addcol(c, table, col, decl, log):
    if col not in cols(c, table):
        c.execute("alter table %s add column %s %s" % (table, col, decl))
        log.append("  + %s.%s" % (table, col))


def main():
    c = sqlite3.connect(DB)
    c.execute("pragma foreign_keys=off")
    log, made = [], []
    have = tables(c)

    # ---- #18 departments -------------------------------------------------
    if "departments" not in have:
        c.execute("""create table departments (
            id integer primary key,
            key text unique not null,
            label text not null,
            grp text not null,
            active integer not null default 1)""")
        made.append("departments")
    for k, label, grp in D.DEPARTMENTS:
        c.execute("insert or ignore into departments(key,label,grp) values(?,?,?)",
                  (k, label, grp))

    # ---- #5 priority on the entities that carry it -----------------------
    for t in ("cases", "tasks", "coordination", "llr"):
        if t in have:
            addcol(c, t, "priority", "text default '%s'" % D.DEFAULT_PRIORITY, log)

    # ---- #6 priority history (priority may change mid-lifecycle) ---------
    if "priority_history" not in have:
        c.execute("""create table priority_history (
            id integer primary key,
            entity_kind text not null,
            entity_id integer not null,
            from_priority text,
            to_priority text not null,
            reason text,
            changed_by integer,
            changed_at text not null)""")
        c.execute("""create index ix_prihist on priority_history
                     (entity_kind, entity_id)""")
        made.append("priority_history")

    # ---- #1 #3 cross-team routing + acknowledgement ----------------------
    if "cases" in have:
        addcol(c, "cases", "to_dept",      "text", log)
        addcol(c, "cases", "to_person_id", "integer", log)
        addcol(c, "cases", "from_dept",    "text", log)
        addcol(c, "cases", "line_manager_id", "integer", log)
        addcol(c, "cases", "ack_due_at",   "text", log)
        addcol(c, "cases", "acked_at",     "text", log)
        addcol(c, "cases", "acked_by",     "integer", log)
        addcol(c, "cases", "tat_days",     "integer", log)
        addcol(c, "cases", "due_at",       "text", log)
        addcol(c, "cases", "escalated_at", "text", log)
        addcol(c, "cases", "escalation_level", "text", log)
        addcol(c, "cases", "origin_kind",  "text", log)
        addcol(c, "cases", "origin_id",    "integer", log)

    # ---- #2 back-and-forth communication ---------------------------------
    if "case_thread" not in have:
        c.execute("""create table case_thread (
            id integer primary key,
            case_id integer not null,
            author_id integer,
            author_dept text,
            kind text not null default 'message',
              -- message | ack | update | question | answer | escalation | status
            body text not null,
            is_update integer not null default 0,
            created_at text not null)""")
        c.execute("create index ix_thread_case on case_thread(case_id)")
        made.append("case_thread")

    # ---- #4 escalation ----------------------------------------------------
    if "escalations" not in have:
        c.execute("""create table escalations (
            id integer primary key,
            entity_kind text not null,
            entity_id integer not null,
            reason text not null,          -- missed_ack | tat_breach | manual
            from_level text,
            to_level text not null,
            to_person_id integer,
            note text,
            raised_by integer,
            raised_at text not null,
            resolved_at text)""")
        c.execute("create index ix_esc on escalations(entity_kind, entity_id)")
        made.append("escalations")

    # ---- #7 #8 #9 structured visit findings ------------------------------
    if "visit_findings" not in have:
        c.execute("""create table visit_findings (
            id integer primary key,
            visit_id integer not null,
            seq integer not null,
            category text,
            title text not null,
            description text,
            location text,
            severity text default 'medium',
            priority text default '%s',
            assigned_dept text,
            assigned_person_id integer,
            status text not null default 'open',
            tat_days integer,
            due_at text,
            rfi_case_id integer,
            resolution text,
            resolved_at text,
            recurring_of integer,
            created_at text not null)""" % D.DEFAULT_PRIORITY)
        c.execute("create index ix_vf_visit on visit_findings(visit_id)")
        c.execute("create index ix_vf_dept  on visit_findings(assigned_dept)")
        made.append("visit_findings")

    if "finding_evidence" not in have:
        c.execute("""create table finding_evidence (
            id integer primary key,
            finding_id integer not null,
            kind text not null,        -- photo | report | video | document | other
            filename text not null,
            path text,
            caption text,
            uploaded_by integer,
            uploaded_at text not null)""")
        c.execute("create index ix_fe_finding on finding_evidence(finding_id)")
        made.append("finding_evidence")

    # ---- #23 site & compliance evidence ----------------------------------
    if "site_visits" in have:
        addcol(c, "site_visits", "project_stage", "text", log)
        addcol(c, "site_visits", "closed_at", "text", log)

    # ---- #12 #17 lessons: root cause / performance analysis --------------
    if "llr" in have:
        addcol(c, "llr", "root_cause",        "text", log)
        addcol(c, "llr", "delay_days",        "integer", log)
        addcol(c, "llr", "delay_owner_dept",  "text", log)
        addcol(c, "llr", "delay_is_external", "integer default 0", log)
        addcol(c, "llr", "dependency",        "text", log)
        addcol(c, "llr", "what_should_change", "text", log)
        addcol(c, "llr", "preventive_action", "text", log)
        addcol(c, "llr", "head_visible",      "integer default 1", log)
        addcol(c, "llr", "audit_visible",     "integer default 0", log)
        addcol(c, "llr", "improvement_status", "text default 'open'", log)

    # ---- #25 SLA -> TAT on coordination ----------------------------------
    if "coordination" in have and "tat_days" not in cols(c, "coordination"):
        c.execute("alter table coordination add column tat_days integer")
        c.execute("update coordination set tat_days = sla_days "
                  "where sla_days is not null")
        log.append("  + coordination.tat_days (copied from sla_days)")

    # ---- #36 tasks linked to their originating process -------------------
    if "tasks" in have:
        addcol(c, "tasks", "origin_kind", "text", log)
        addcol(c, "tasks", "origin_id",   "integer", log)
        addcol(c, "tasks", "tat_days",    "integer", log)
        addcol(c, "tasks", "hold_days",   "integer default 0", log)

    # ---- #19 cross-module collaboration links ----------------------------
    if "entity_links" not in have:
        c.execute("""create table entity_links (
            id integer primary key,
            from_kind text not null,
            from_id integer not null,
            to_kind text not null,
            to_id integer not null,
            relation text not null default 'relates_to',
            note text,
            created_by integer,
            created_at text not null)""")
        c.execute("create index ix_link_from on entity_links(from_kind, from_id)")
        c.execute("create index ix_link_to   on entity_links(to_kind, to_id)")
        made.append("entity_links")

    # ---- backfill TAT from existing baselines where sensible -------------
    c.execute("update tasks set tat_days = baseline_days "
              "where tat_days is null and baseline_days is not null")

    c.commit()

    print("migrate_v3 complete")
    if made:
        print("\nnew tables:")
        for t in made:
            print("  * %s" % t)
    if log:
        print("\nnew columns:")
        for line in log:
            print(line)
    if not made and not log:
        print("  (nothing to do -- already migrated)")

    print("\nrow counts:")
    for t in ("departments", "visit_findings", "finding_evidence",
              "case_thread", "escalations", "priority_history", "entity_links"):
        try:
            n = c.execute("select count(*) from %s" % t).fetchone()[0]
            print("  %-18s %5d" % (t, n))
        except sqlite3.OperationalError:
            print("  %-18s  MISSING" % t)
    c.close()


if __name__ == "__main__":
    sys.exit(main())
