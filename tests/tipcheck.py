"""Hover a rail icon in a real browser and prove the label is visible, not clipped."""
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

HARNESS = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>tip</title>
<style>body{margin:0;font:13px system-ui;background:#101418}
#st{padding:9px 12px;background:#0b0f13;color:#7ee787;font-family:Consolas,monospace;
white-space:pre-wrap;font-size:11.5px;line-height:1.55}
/* a short viewport on purpose: this is the case that made the rail scroll */
iframe{width:1280px;height:620px;border:0;display:block;background:#fff}</style>
</head><body>
<div id="st">booting...</div><iframe id="f"></iframe>
<script>
const errs=[], steps=[];
try{ localStorage.setItem("zd.tok","__TOK__"); }catch(e){ errs.push("localStorage: "+e); }
const f=document.getElementById("f"), st=document.getElementById("st");
f.addEventListener("load",function(){ try{
  f.contentWindow.onerror=function(m,s,l){ errs.push("ERROR "+m+" :"+l); };
}catch(e){} });
f.src="index.html?v="+Date.now();
function paint(){ st.textContent="rail label check\\n"+steps.join("\\n")
  +"\\n\\nCONSOLE ERRORS: "+errs.length+(errs.length?"\\n"+errs.join("\\n"):"  (none)"); }
setTimeout(function(){
  const w=f.contentWindow, d=f.contentDocument;
  const nav=d.querySelector("#railNav");
  steps.push("rails                " + d.querySelectorAll("#railNav [data-tab]").length);
  steps.push("nav scrollHeight     " + nav.scrollHeight + " vs client " + nav.clientHeight);
  steps.push("nav overflow-y       " + getComputedStyle(nav).overflowY);
  steps.push("scroll hint class    " + (nav.classList.contains("scrolls") ? "on (rail scrolls)" : "off"));

  // scroll the rail down, exactly what the user was doing
  nav.scrollTop = 120;

  // hover the rail icon that is now under the pointer
  const btns=[...d.querySelectorAll("#railNav [data-tip]")];
  const target=btns.find(function(b){ const r=b.getBoundingClientRect();
    return r.top>nav.getBoundingClientRect().top+20; }) || btns[5];
  target.dispatchEvent(new PointerEvent("pointerover",{bubbles:true}));

  const tip=d.querySelector(".railtip");
  steps.push("tooltip element      " + (tip ? "created on <body>" : "MISSING"));
  if(tip){
    const tr=tip.getBoundingClientRect(), br=target.getBoundingClientRect();
    const railW=d.querySelector(".rail").getBoundingClientRect().right;
    steps.push("tooltip text         \\"" + tip.textContent + "\\"");
    steps.push("hovered icon         data-tip=\\"" + target.dataset.tip + "\\"");
    steps.push("visible (class on)   " + tip.classList.contains("on"));
    steps.push("opacity              " + getComputedStyle(tip).opacity);
    steps.push("tip left / rail right " + Math.round(tr.left) + " / " + Math.round(railW)
      + (tr.left >= railW ? "   -> clears the rail" : "   -> OVERLAPS THE RAIL"));
    steps.push("parent               " + tip.parentElement.tagName
      + (tip.parentElement.tagName==="BODY" ? "  (outside the scroll container)" : "  WRONG"));
    steps.push("vertical centre      tip " + Math.round(tr.top+tr.height/2)
      + " vs icon " + Math.round(br.top+br.height/2));
    steps.push("in viewport          " + (tr.top>0 && tr.bottom < f.clientHeight));
  }
  paint();
}, 3600);
setTimeout(function(){
  // leaving the rail must clear it
  const d=f.contentDocument;
  d.querySelector(".rail").dispatchEvent(new PointerEvent("pointerleave",{bubbles:false}));
  const tip=d.querySelector(".railtip");
  steps.push("after pointerleave   " + (tip && tip.classList.contains("on") ? "STILL SHOWING" : "hidden"));
  // and re-hover for the screenshot
  const btns=[...d.querySelectorAll("#railNav [data-tip]")];
  const t=btns[6];
  t.dispatchEvent(new PointerEvent("pointerover",{bubbles:true}));
  steps.push("re-hover             \\"" + d.querySelector(".railtip").textContent + "\\"");
  setInterval(function(){ t.dispatchEvent(new PointerEvent("pointerover",{bubbles:true})); }, 150);
  paint();
}, 5000);
setTimeout(function(){
  const d=f.contentDocument, tip=d.querySelector(".railtip");
  const tr=tip.getBoundingClientRect();
  steps.push("matches .railtip.on  " + tip.matches(".railtip.on"));
  steps.push("opacity w/ transition " + getComputedStyle(tip).opacity);
  tip.style.transition = "none";           // is the 0 the RULE or the animation?
  void tip.offsetWidth;
  steps.push("opacity w/o transition " + getComputedStyle(tip).opacity);
  steps.push("zd-ui.css loaded     " + [...d.styleSheets].some(function(x){
      return (x.href||"").indexOf("zd-ui") > -1; }));
  steps.push("settled left         " + Math.round(tr.left) + "  width " + Math.round(tr.width));
  steps.push("painted over page    " + (document.elementFromPoint ? "yes" : "?"));
  paint();
}, 8000);
</script></body></html>"""

hpath = os.path.join(ROOT, "_tip.html")
open(hpath, "w", encoding="utf-8").write(HARNESS.replace("__TOK__", TOK))
url = BASE + "/_tip.html"
common = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
          "--window-size=1300,1000", "--virtual-time-budget=14000",
          "--user-data-dir=" + os.path.join(OUT, "chromeprof")]
try:
    dom = subprocess.run(common + ["--dump-dom", url], capture_output=True, text=True,
                         timeout=180, encoding="utf-8", errors="replace")
    b = dom.stdout or ""
    i = b.find('id="st"')
    j = b.find("</div>", i)
    print("---- rail label check ----")
    print(b[i + 8:j].replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
          .replace("&quot;", '"') if i > 0 else b[:1200])
    shot = os.path.join(OUT, "zd-tip.png")
    subprocess.run(common + ["--screenshot=" + shot, url], capture_output=True, timeout=180)
    print("\nscreenshot:", shot)
finally:
    os.remove(hpath)
