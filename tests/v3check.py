"""Drive every new review-layer rail in a real browser and report."""
import json, os, subprocess, urllib.request

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

HARNESS = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>v3</title>
<style>body{margin:0;font:13px system-ui;background:#101418}
#st{padding:9px 12px;background:#0b0f13;color:#7ee787;font-family:Consolas,monospace;
white-space:pre-wrap;font-size:11.5px;line-height:1.5}
iframe{width:1560px;height:1000px;border:0;display:block;background:#fff}</style>
</head><body>
<div id="st">booting...</div><iframe id="f"></iframe>
<script>
const errs=[], steps=[];
try{ localStorage.setItem("zd.tok","__TOK__"); }catch(e){ errs.push("localStorage: "+e); }
const f=document.getElementById("f"), st=document.getElementById("st");
f.addEventListener("load",function(){ try{
  f.contentWindow.onerror=function(m,s,l){ errs.push("ERROR "+m+" :"+l); };
  f.contentWindow.addEventListener("unhandledrejection",function(e){
    errs.push("REJECTION "+e.reason); });
}catch(e){} });
f.src="index.html?v="+Date.now();
function q(s){ try{ return f.contentDocument.querySelectorAll(s).length; }catch(e){ return -1; } }
function txt(s){ try{ return (f.contentDocument.querySelector(s)||{}).textContent||""; }catch(e){ return "?"; } }
function paint(){ st.textContent="ZD PULSE v3 (Haroon register) check\n"+steps.join("\n")
  +"\n\nCONSOLE ERRORS: "+errs.length+(errs.length?"\n"+errs.join("\n"):"  (none)"); }

const RAILS=["today","settings","findings_via_site","learning","delivery","exec",
             "matrix","llr","queue","catalog"];
let i=0;
function step(){
  const w=f.contentWindow, d=f.contentDocument;
  const tab=RAILS[i];
  if(i===0){
    steps.push("rails            "+q("#railNav [data-tab]"));
    steps.push("landing rail     "+txt("#headTitle"));
  }
  const real = tab==="findings_via_site" ? "site" : tab;
  try{ w.go(real); }catch(e){ errs.push("go("+real+"): "+e.message); }
  setTimeout(function(){
    const rows=q("#page tr"), clickable=q("#page [data-e]"), cards=q("#page .card");
    steps.push(("rail "+real).padEnd(17)+"title="+txt("#headTitle").slice(0,26).padEnd(28)
      +"rows="+String(rows).padEnd(5)+"clickable="+String(clickable).padEnd(5)
      +"cards="+cards);
    i++; paint();
    if(i<RAILS.length) setTimeout(step, 500); else setTimeout(deep, 500);
  }, 850);
}
setTimeout(step, 3500);

function deep(){
  const w=f.contentWindow, d=f.contentDocument;
  // a cross-team case, which is the largest new flow
  (async function(){
    try{
      const r = await w.api("/api/cases");
      const ctr = r.rows.filter(x=>x.type==="CTR")[0];
      if(!ctr){ errs.push("no CTR case seeded"); return; }
      await w.E.open("case", ctr.id);
      setTimeout(function(){
        steps.push("");
        steps.push("cross-team drawer  "+txt(".zdrw .zw-t h2").slice(0,44));
        steps.push("  thread messages  "+q(".zdrw .feed .fe"));
        steps.push("  route lanes      "+q(".zdrw .tli"));
        steps.push("  drawer actions   "+q(".zdrw .zw-act .btn"));
        steps.push("  ack/esc shown    "+(txt(".zdrw").indexOf("Acknowledg")>-1));
        paint();
        // and a finding, with its history
        (async function(){
          const fr = await w.api("/api/findings");
          const fid = (fr.rows.filter(x=>x.recurrence_of)[0] || fr.rows[0]).id;
          await w.E.open("finding", fid);
          setTimeout(function(){
            steps.push("finding drawer     "+txt(".zdrw .zw-t h2").slice(0,44));
            steps.push("  sections         "+q(".zdrw .zw-s"));
            steps.push("  actions          "+q(".zdrw .zw-act .btn"));
            steps.push("  history rows     "+q(".zdrw tr.rc"));
            steps.push("  evidence         "+(txt(".zdrw").indexOf("Photo set")>-1
              || txt(".zdrw").indexOf("Inspection")>-1));
            try{ w.E.close(); }catch(e){}
            try{ w.go("settings"); }catch(e){}
            setTimeout(function(){
              steps.push("");
              steps.push("definitions rail   unconfirmed banner="
                +(txt("#page").indexOf("UNCONFIRMED")>-1));
              steps.push("  setting rows     "+q("#page [data-set]"));
              paint();
            }, 900);
          }, 900);
        })();
      }, 1000);
    }catch(e){ errs.push("deep: "+e.message); paint(); }
  })();
}
</script></body></html>"""

hpath = os.path.join(ROOT, "_v3.html")
open(hpath, "w", encoding="utf-8").write(HARNESS.replace("__TOK__", TOK))
url = BASE + "/_v3.html"
common = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
          "--window-size=1580,1500", "--virtual-time-budget=40000",
          "--user-data-dir=" + os.path.join(OUT, "chromeprof")]
try:
    dom = subprocess.run(common + ["--dump-dom", url], capture_output=True, text=True,
                         timeout=240, encoding="utf-8", errors="replace")
    b = dom.stdout or ""
    i = b.find('id="st"')
    j = b.find("</div>", i)
    print("---- v3 rail check ----")
    print(b[i + 8:j].replace("&lt;", "<").replace("&gt;", ">")
          .replace("&amp;", "&").replace("&quot;", '"') if i > 0 else b[:1500])
    shot = os.path.join(OUT, "zd-v3.png")
    subprocess.run(common + ["--screenshot=" + shot, url], capture_output=True, timeout=240)
    print("\nscreenshot:", shot)
finally:
    os.remove(hpath)
