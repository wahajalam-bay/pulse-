# backup-pre-v3 — from the concurrent session, 2 Sep 2026

Left by the other Claude session that was editing this folder at the same time.
See PROJECT-MEMORY.md §13.

`*.bak` is a snapshot of the state **before** that session's changes — i.e. the
1 Sep build. It does **not** contain that session's own schema, which is why their
work could not be recovered and mine is what survived.

`migrate_v3.py` and `backfill_v3.py` are theirs and are **dead**. They add
`visit_findings`, `escalations`, `cases.to_dept` and similar onto a schema that now
has the equivalents under different names (`findings`, `cases.to_team`,
`case_messages`, `priority_log`). Running them would create parallel, unused tables.
Moved here out of the working tree for that reason. Read them for reference; do not
execute them.

`zd.db.bak` is a database from before the 2 Sep schema change. The live schema has
moved on — `python store.py --force` rebuilds the current one.
