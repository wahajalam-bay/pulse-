#!/usr/bin/env python3
"""ZD PULSE — run every check.

  python tests/run-all.py            rebuild the database, start a server, run everything
  python tests/run-all.py --keep     use the server and database already running
  python tests/run-all.py --api      the two API suites only, no browser

WHY IT REBUILDS BY DEFAULT
  Both API suites assert on counts and on refusals that only hold against a freshly
  seeded database — "the unconfirmed count drops to 25" is true once. Running them
  twice against the same database produces failures that look like defects and are
  not. So the default is: rebuild, run, tell you the truth.

WHY IT KILLS EVERY LISTENER
  `Server.allow_reuse_address = True` means a second process can bind :4010 on
  Windows while the first keeps serving. That once cost half an hour of debugging a
  server that was not the code on disk. So: kill them all, assert exactly one, then
  test. See PROJECT-MEMORY.md §13.
"""
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "tests")
PORT = os.environ.get("PORT", "4010")
MOUNT = os.environ.get("MOUNT", "/zd")
BASE = f"http://127.0.0.1:{PORT}{MOUNT}"
PY = sys.executable

API = ["e2e.py", "e2e_v3.py"]
BROWSER = ["v3check.py", "browsercheck.py", "tipcheck.py"]


def listeners():
    """PIDs holding the port. netstat because this has to work with no deps."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pids = set()
    for line in out.splitlines():
        if f":{PORT} " in line and "LISTENING" in line:
            m = re.search(r"(\d+)\s*$", line.strip())
            if m:
                pids.add(m.group(1))
    return sorted(pids)


def kill_all():
    for pid in listeners():
        subprocess.run(["taskkill", "/PID", pid, "/F"],
                       capture_output=True, timeout=30)
    for _ in range(20):
        if not listeners():
            return True
        time.sleep(0.25)
    return False


def up():
    try:
        with urllib.request.urlopen(BASE + "/api/health", timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main():
    keep = "--keep" in sys.argv
    api_only = "--api" in sys.argv
    server = None

    if not keep:
        print("· stopping every listener on :" + PORT)
        if not kill_all():
            print("  could not free the port — stop it by hand and retry")
            return 2
        print("· rebuilding the database (store.py --force)")
        r = subprocess.run([PY, "store.py", "--force"], cwd=ROOT,
                           capture_output=True, text=True, timeout=300)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            return 2
        print("· starting the server")
        log = open(os.path.join(ROOT, "logs", "test-server.log"), "w")
        server = subprocess.Popen([PY, "server.py"], cwd=ROOT,
                                  stdout=log, stderr=subprocess.STDOUT)
        for _ in range(40):
            if up():
                break
            time.sleep(0.4)

    if not up():
        print("! nothing serving " + BASE + " — start it with `python server.py`")
        return 2
    n = len(listeners())
    print(f"· one server expected on :{PORT}, found {n}"
          + ("  OK" if n == 1 else "  <- MORE THAN ONE, results are not trustworthy"))

    suites = API if api_only else API + BROWSER
    results, failed = [], 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for s in suites:
        print(f"\n{'=' * 70}\n  {s}\n{'=' * 70}")
        r = subprocess.run([PY, os.path.join(HERE, s)], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        print(out.strip()[-4000:])
        m = re.search(r"(\d+) passed, (\d+) failed", out)
        errs = re.search(r"CONSOLE ERRORS: (\d+)", out)
        if m:
            p, f = int(m.group(1)), int(m.group(2))
            failed += f
            results.append(f"{s:<18} {p} passed, {f} failed")
        elif errs:
            e = int(errs.group(1))
            failed += e
            results.append(f"{s:<18} rendered, {e} console errors")
        else:
            failed += 1 if r.returncode else 0
            results.append(f"{s:<18} exit {r.returncode} (no summary line)")

    print("\n" + "=" * 70)
    for line in results:
        print("  " + line)
    print("=" * 70)
    print("  ALL GREEN" if not failed else f"  {failed} PROBLEM(S)")
    if server and not keep:
        print("\n· the server is still running so you can look at "
              + BASE + "/  (Ctrl+C here does not stop it)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
