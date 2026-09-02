# tests

Stdlib only, like the rest of the system. No pytest, no node modules, nothing to
install.

```bash
python tests/run-all.py          # rebuild, start a server, run everything
python tests/run-all.py --api    # the two API suites only (fast, no browser)
python tests/run-all.py --keep    # against whatever is already running
```

Expected, on a fresh database: **51/51**, **63/63**, and the browser checks with
**0 console errors**.

---

## What each one covers

| File | Drives | Asserts |
|---|---|---|
| `e2e.py` | the 1 Sep build, over HTTP | 51 checks — visit→NCR, the §4.2 template stamp, the §7.6 lesson loop, transmittal sheet lists, drawing revisions, the authority clock, closeout gates, search, the entity drawer |
| `e2e_v3.py` | Haroon's 1 Sep review backlog, over HTTP | 63 checks — cross-team routing, acknowledgement, threads, escalation, priority history, five findings on one visit, recurrence, finding→RFI, root cause, hold/resume, and every §36 setting actually moving the numbers |
| `v3check.py` | all 19 rails in headless Chrome | every rail renders with real rows, the cross-team drawer, the finding drawer, the definitions rail — and no console errors |
| `browsercheck.py` | the shell in headless Chrome | rails, the 14-station matrix, a case drawer, the command palette |
| `tipcheck.py` | the rail at a short viewport | the hover label escapes the scrolling nav (see PROJECT-MEMORY §11) |

`_out/` collects screenshots. `_build-patches/` is history, not tests — see below.

---

## Two things that will otherwise waste your afternoon

**Run them against a fresh database.** Both API suites assert on counts and on
first-time refusals: *"the unconfirmed count drops to 25"* is true exactly once.
Re-running against the same database produces failures that look like defects and are
not. `run-all.py` rebuilds by default for this reason. If you run a suite directly, do
`python store.py --force` first.

**Kill every listener, not "the" listener.** `Server.allow_reuse_address = True` lets a
second process bind `:4010` on Windows while the first keeps serving — so you can spend
a long time testing a server that is not the code on disk. `run-all.py` kills them all
and asserts exactly one. By hand:

```bash
for PID in $(netstat -ano | grep ":4010 " | grep LISTENING | awk '{print $5}' | sort -u); do
  taskkill //PID $PID //F
done
```

---

## How the browser checks work

There is no playwright and no chromium-cli on this machine, and the app gates on a
token in `localStorage`, so a plain headless load just bounces to the login page.

Instead: fetch a token from `/api/login`, write a throwaway harness page into the
**project root** — same origin, so it shares `localStorage` — have it set the token and
*then* point an iframe at `index.html`. Same-origin means the harness can read
`contentDocument`, hook `contentWindow.onerror`, and call into the app
(`f.contentWindow.go("matrix")`, `E.open("case", 12)`). Chrome runs with
`--headless=new --virtual-time-budget=…`, once with `--dump-dom` to read a status block
the harness paints and once with `--screenshot`. The harness file is deleted afterwards.

Gotchas already paid for:

- Set the iframe `src` from JS, never as an attribute — it starts loading before the
  token is set and bounces to login.
- `--virtual-time-budget` **does not advance CSS transitions**. A faded-in element reads
  `opacity: 0` forever and never appears in a screenshot. Set
  `style.transition = "none"` before measuring or capturing.
- Classic-script `const` does not attach to `window`; that is why `js/entity.js` ends
  with `window.E = E`.
- `PYTHONIOENCODING=utf-8`, or printing the report dies on cp1252.

---

## `_build-patches/`

The one-shot scripts that produced the 1 Sep and 2 Sep builds, kept only because
**this project has no git repo** and they are the closest thing to a diff history.

They are **already applied and not re-runnable** — each anchors on the exact file state
that preceded it. Do not execute them. Read them if you need to know how a file came to
look the way it does, then delete the folder once `git init` has happened.
