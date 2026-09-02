# ZD PULSE — Architecture & Design

A working system for Haroon Noon's department, built on the same shell, rail and flow
as Bayut Studios PULSE.

## Run it

```bash
python server.py                       # http://127.0.0.1:4010/zd/
PORT=4010 MOUNT=/zd python server.py   # explicit
python store.py --force                # rebuild the database from scratch
python catalog.py                      # print catalog stats + TAT conflicts
```

46 workflows · 350 steps · **14 stations** · 10 case routes · 33 write actions ·
15 rails. `Ctrl+K` searches every register; every row opens a record.

Python 3.9+. **No dependencies** — standard library only, same as PULSE.

```powershell
.un-live.ps1              # start detached, killing any stale listener first
python testsun-all.py     # rebuild, start, and run every check (see tests/README.md)
```

Use `run-live.ps1` rather than a bare `python server.py` if you have been restarting a
lot: `allow_reuse_address` lets a second server bind :4010 on Windows while the first
keeps answering, and you can lose a long time testing a process that is not the code on
disk. It stops every listener on the port before starting one.

**Status of record:** `BACKLOG.md` tracks Haroon's 1 Sep review — 31 of 36 items done,
5 open with the reasons stated. `PROJECT-MEMORY.md` is the working state.
`DEMO-WALKTHROUGH.html` is **stale** — written against the 27 Aug build (13 stations,
17 actions, 39 workflows) and not updated since. Rewrite it before the next demo.

## Sign in

| Account | Who |
|---|---|
| `haroon@zameen.com` | Haroon Noon — Head of Architecture & Design |
| `ahmed@zameen.com` | Ahmed Khan — Sr. Manager Architecture |
| `rashid@zameen.com` | Hafiz Rashid Khalid — Sr. Manager Structure |
| `yahya@zameen.com` | Yahya Ali Khan — Sr. Manager MEP |
| `ali@zameen.com` | Ali Aslam — Creative Lead |

Password for all: `ZDesign!2026` — review build only, rotate before this leaves a laptop.

## What you can DO in it — 33 write actions

| Action | Manual |
|---|---|
| Open a project · fill the intake | §3 / §3.1 — seven fields, each with a named owner |
| Initiate a stage · sign it off | generates tasks from the catalog; both gated |
| Create a task · assign it | ad-hoc work; assignment is team-checked |
| **Raise** a MAR / DCR / RFI / shop drawing / vetting | §11 §14 §13 §7 |
| **Decide** — approve · **return** · **reject** | reason mandatory for return/reject |
| Ask another team | the coordination clock starts |
| Complete an obligation | §9 §15 — evidence mandatory |
| Log a site visit | §15 — auto-closes the monthly obligation |
| Register a drawing · issue a transmittal | §5 — the contractual milestone |
| Author, tick and sign a checklist | §4.1 / §4.2 |
| Add a note to anything | replaces WhatsApp |
| **Revise a drawing** · issue a transmittal with its **sheet list** | §5 — the register keeps every revision |
| **Log an authority submission** · record what came back | §7 / §17 — the longest clock the department carries |
| **Raise a lesson** · rule on it · **adopt it into the stage checklist** | §7.6 → §4.2 — the loop |
| Author, retire and version the **§4.2 checklist template** | the annexure the Manual marks "(to be added)" |
| Attach a document to anything | a versioned link register, not file storage |
| Withdraw a case · **close a project out** | §18 — the lifecycle finally has an end |

### The seven workflows the booklet never drew

Volume 1 stops at the drawing. These are transcribed from the Manual's prose and are
tagged as such everywhere they appear — provenance is never blurred:

| Workflow | Section | Why it matters |
|---|---|---|
| Value Engineering | §8 | VE ran after tender award, so every change became a DCR with a cost claim |
| BOQ Endorsement | §10 | The gate between the tender set and Supply Chain |
| Finishing Items & Sampling | §12 | Mock-ups were approved verbally with no record |
| QA/QC Site Coordination | §16 | Non-compliance had nowhere to go |
| Regulatory Inspection Support | §17 | The authority clock was never totalled |
| Project Closeout & As-Built | §18 | **Station 14** — before it, stage 13 ran forever |
| Lessons Learned Review | §7.6 | The loop that changes the next project |

### The connections (this is the part that matters)

- A **site visit** finding non-compliance **raises an NCR** on the §16 route and starts
  the QA/QC re-inspection clock — not a checkbox on a row nobody reads.
- **Authority observations** come back as a **task on the design team**; answering them
  closes the clock that submitting opened.
- A **transmittal** carries the sheet list with each sheet's revision, and issuing for
  construction updates the register.
- **Initiating a stage stamps the §4.2 template** onto its checklist, so the mandatory
  gate arrives with content instead of blank.
- **A ruled lesson is adopted into that template** and lands on every unsigned checklist
  for the stage — so the checklist that blocks the next transmittal is one the last
  project's mistake wrote.

### The gates that fire (all logged as blocked attempts)

- Intake incomplete → Stage 3 refused, and it names the missing fields
- Previous stage unsigned → next stage refused
- Checklist empty or unticked → cannot be signed
- Checklist unsigned → **transmittal refused** (§4.1: no issuance before sign-off)
- Return or reject with no reason → refused
- Assigning a Structure person to an Architecture step → refused
- Case sitting with PM / QA-QC / Supply Chain → refused, wait recorded
- PKR ≥ 500,000 → CPC · ≥ 1,500,000 → CEO Office
- Obligation ticked with no evidence → refused
- Finish before start → refused

**Soft gates, logged overrides.** Every refusal offers *Override & proceed* with a mandatory
reason that goes in the ledger. A hard block just pushes the work back onto paper; an
override with a name and a reason on it is worth more than a block.

## The thirteen rails

| Rail | What it does | New vs PULSE |
|---|---|---|
| **My Queue** | Your tasks, decisions and obligations — the landing page | **new** |
| Executive Summary | The department at a glance | re-pointed |
| **Project Stage Matrix** | 8 projects × 13 stations. Replaces the master sheet. | **redesigned** |
| Project Insights | One project: stages, teams, asks, cases | re-pointed |
| **Approvals Inbox** | MAR · DCR · RFI · shop drawings · vetting | **new** |
| **Coordination Ledger** | Who owes the department what, and for how long | **new** |
| Task Management | 1,261 tasks generated from the catalog | engine reused |
| Team Performance | Architecture · Structure · MEP · Creative | 3 configs → 4 |
| **Obligations** | Weekly reviews, site visits, compliance reports | **new** |
| **Workflow Catalog** | The booklet as data, conflicts included | **new** |
| **Drawings & Issuance** | Register + transmittals (§5) | **new** |
| **Activity Ledger** | Every action, authority, and blocked attempt | surfaced |
| People | 45 people, tiers, value thresholds | re-pointed |

## What is real vs. demo

**Real — transcribed from the source documents:**

- `catalog.py` — all **39 workflows / 296 steps**, with durations, lanes, maker/checker
  marks, rework loops and gates, from Design Workflow Booklet Vol.1
- The **13-station spine** — Manual §3 (acquisition), §4 (stages 3–12), §§5–18 (construction support)
- The **5 case routes** — Design §14 (DCR), PM §5.3 (MAR), Design §13 (shop drawings),
  Design §7 (vetting), RFI
- **Value thresholds** — PKR 15k / 500k / 1.5m, Supply Chain Manual §4.3.2 and §18
- The **6 TAT conflicts** between booklet and Manual — detected, not hidden
- **45 people** across 4 teams, from the booklet's own team pages
- **8 projects** named on the booklet cover

**Demo — so every surface has something to show:**

- Task progress, dates and case positions. Flagged on screen as a review build.

## Still not built — be straight about this

§8 Value Engineering · §10 BOQ endorsement · §12 finishing items & sampling ·
§16 QA/QC coordination · §17 regulatory visit support · §18 closeout / as-built ·
notifications · search · file upload · the LLR library.

## Three things to look at first

**1 · The two clocks.** Every task carries `own_days` and `wait_days` separately, split at
the moment of handoff. SLA variance is measured on own time only — waiting on the Authority,
a vendor or Finance never counts against the team. The Executive rail leads with the number
nobody in ZD can currently produce: **23.7% of all elapsed time was spent waiting on someone
outside the department.**

**2 · Stubbed lanes.** Open the Approvals Inbox. Six cases sit with Arch & Design and can be
advanced. Six sit with PM, QA/QC, Supply Chain or Head ZD — try to advance one and it refuses,
and *logs the refusal*. When those systems exist, the stub becomes a live lane and nothing
else changes. The blocked-attempt count is the business case for building them.

**3 · The catalog is the source.** Planned dates are generated from the department's own
published TAT, not typed by a person. Change `catalog.py`, rebuild, and every plan moves.

## Known-open — carried from the document review

| # | Question | Effect here |
|---|---|---|
| 1 | **TAT authority** — booklet vs Manual disagree on 6 of 10 stages | Both stored; `TAT_SOURCE` in `catalog.py` is the single switch |
| 2 | **Working or calendar days?** | Assumed working, Mon–Fri. One function: `_add_working_days` |
| 3 | **Is Creative in scope?** 7 of 12 workflows have no project | Parked on a "Department BAU" carrier project |
| 4 | **14 steps have no duration** — blank column in the booklet | Render as "—", never zero |
| 5 | **4 projects unnamed** — booklet says 12, cover names 8 | Not invented |
| 6 | **§4.2 checklist annexure "(to be added)"** | Engine built, ships empty — the department authors the checks in-system |
| 7 | **MAR means 3 different things** across 3 manuals | Implements PM §5.3; flagged in `store.py ROUTES` |

## Files

```
catalog.py        the booklet as data — 39 workflows, the one file to edit
store.py          schema (14 tables), seed, two-clock derivation, ROUTES
actions.py        the write layer — 17 handlers, every mutation, every gate
server.py         stdlib HTTP service + JSON API, dispatches writes to actions.py
index.html        the shell · login.html
css/zd.css        ZD navy on PULSE's layout grammar + the modal/form layer
js/forms.js       modal, field renderer, F.act(), override-with-reason
js/app.js         router + the eleven read rails
js/ui-actions.js  My Queue, Drawings, and every action button
data/zd.db        SQLite — delete and re-run to rebuild
```
