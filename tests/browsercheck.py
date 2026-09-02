"""Drive the real app in headless Chrome: log in, render, open a drawer, report errors."""
import json, os, subprocess, sys, urllib.request, time

# Portable: the project is this file's parent directory, and the browser is
# whichever Chromium is installed. See tests/README.md.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = next((c for c in (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
) if os.path.exists(c)), None)
assert CHROME, "no Chrome or Edge found — see tests/README.md"
OUT = os.environ.get("SCRATCH") or os.path.join(ROOT, "tests", "_out")
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:4010/zd"

req = urllib.request.Request(BASE + "/api/login", method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, json.dumps(
        {"email": "haroon@zameen.com", "password": "ZDesign!2026"}).encode()) as r:
    TOK = json.loads(r.read())["token"]

HARNESS = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>verify</title>
<style>body{margin:0;font:13px system-ui;background:#101418}
#st{padding:9px 12px;background:#0b0f13;color:#7ee787;font-family:Consolas,monospace;
white-space:pre-wrap;font-size:11.5px;line-height:1.5}
iframe{width:1560px;height:940px;border:0;display:block;background:#fff}</style>
</head><body>
<div id="st">booting...</div><iframe id="f"></iframe>
<script>
const errs=[], steps=[];
try{ localStorage.setItem("zd.tok", "__TOK__"); }catch(e){ errs.push("localStorage: "+e); }
const f=document.getElementById("f"), st=document.getElementById("st");
function hook(){ try{ const w=f.contentWindow;
  w.onerror=function(m,s,l,c,e){ errs.push("ERROR "+m+" @"+(s||"").split("/").pop()+":"+l); };
  w.addEventListener("unhandledrejection",function(e){ errs.push("REJECTION "+e.reason); });
}catch(e){ errs.push("hook: "+e); } }
f.addEventListener("load", hook);
f.src = "index.html?v=" + Date.now();
function q(sel){ try{ return f.contentDocument.querySelectorAll(sel).length; }catch(e){ return -1; } }
function txt(sel){ try{ return (f.contentDocument.querySelector(sel)||{}).textContent||""; }
  catch(e){ return "?"; } }
function paint(){ st.textContent = "ZD PULSE headless check\\n" + steps.join("\\n")
  + "\\n\\nCONSOLE ERRORS: " + errs.length + (errs.length? "\\n"+errs.join("\\n") : "  (none)"); }
setTimeout(function(){
  steps.push("url            " + (f.contentWindow.location.pathname||""));
  steps.push("rails          " + q("#railNav [data-tab]"));
  steps.push("head title     " + txt("#headTitle"));
  steps.push("page bytes     " + (function(){ try{
      return f.contentDocument.querySelector("#page").innerHTML.length; }catch(e){ return -1; }})());
  steps.push("kpi cards      " + q("#page .card"));
  steps.push("clickable      " + q("#page [data-e]") + " data-e targets");
  steps.push("action buttons " + q("#page .btn"));
  steps.push("bell badge     " + txt("#bellCount"));
  steps.push("search box     " + q("#hSearch"));
  paint();
}, 3500);
setTimeout(function(){
  try{ f.contentWindow.go("matrix"); }catch(e){ errs.push("go(matrix): "+e.message); }
}, 4200);
setTimeout(function(){
  steps.push("matrix cols    " + q("#page .mx thead th"));
  steps.push("matrix cells   " + q("#page .cell"));
  try{ f.contentWindow.go("llr"); }catch(e){ errs.push("go(llr): "+e.message); }
}, 5200);
setTimeout(function(){
  steps.push("lessons rows   " + q("#page tr.rc"));
  try{ f.contentWindow.go("site"); }catch(e){ errs.push("go(site): "+e.message); }
}, 6200);
setTimeout(function(){
  steps.push("site rows      " + q("#page tr.rc"));
  try{ f.contentWindow.go("queue"); }catch(e){ errs.push("go(queue): "+e.message); }
}, 7000);
setTimeout(function(){
  try{ f.contentWindow.E.open("case", 1); }catch(e){ errs.push("E.open(case,1): "+e.message); }
}, 7800);
setTimeout(function(){
  steps.push("drawer         " + q(".zdrw") + " open");
  steps.push("drawer route   " + q(".zdrw .tli") + " lanes");
  steps.push("drawer sections" + q(".zdrw .zw-s"));
  steps.push("drawer actions " + q(".zdrw .zw-act .btn"));
  steps.push("drawer title   " + txt(".zdrw .zw-t h2"));
  paint();
}, 9000);
setTimeout(function(){
  try{ f.contentWindow.E.pal(); }catch(e){ errs.push("E.pal(): "+e.message); }
}, 9600);
setTimeout(function(){
  steps.push("palette        " + q(".zpal") + " open");
  paint();
}, 10400);
</script></body></html>"""

hpath = os.path.join(ROOT, "_verify.html")
open(hpath, "w", encoding="utf-8").write(HARNESS.replace("__TOK__", TOK))

url = BASE + "/_verify.html"
common = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
          "--hide-scrollbars", "--window-size=1580,1400",
          "--virtual-time-budget=22000",
          "--user-data-dir=" + os.path.join(OUT, "chromeprof")]
try:
    dom = subprocess.run(common + ["--dump-dom", url], capture_output=True,
                         text=True, timeout=180, encoding="utf-8", errors="replace")
    body = dom.stdout or ""
    i, j = body.find('id="st"'), body.find("</div>", body.find('id="st"'))
    print("---- harness report ----")
    print(body[i + 8:j].replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
          if i > 0 else "(status block not found)\n" + body[:1500])
    shot = os.path.join(OUT, "zd-verify.png")
    subprocess.run(common + ["--screenshot=" + shot, url],
                   capture_output=True, timeout=180)
    print("\nscreenshot:", shot, os.path.getsize(shot) if os.path.exists(shot) else "MISSING")
finally:
    os.remove(hpath)
