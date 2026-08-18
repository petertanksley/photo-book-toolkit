#!/usr/bin/env python3
"""
Photo browser — browse raw/, copy keepers to selected/.

Normal mode  — browse raw/, copy keepers to selected/
  python3 scripts/browser.py

Cull mode    — browse selected/, remove photos you no longer want
  python3 scripts/browser.py --cull

Controls (lightbox):
  K / Space   — keep (normal) or remove (cull)
  Left/Right  — previous / next
  Esc         — close
"""

import argparse
import io
import os
import re
import sys
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file
from PIL import Image, ImageOps
import shutil

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# Parse --cull before Flask sees argv
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--cull", action="store_true")
_args, _remaining = _parser.parse_known_args()
sys.argv = [sys.argv[0]] + _remaining
CULL = _args.cull

app = Flask(__name__)

PROJECT  = Path(__file__).resolve().parent.parent
RAW      = PROJECT / "raw"
SELECTED = PROJECT / "selected"
THUMBS   = RAW / ".thumbs"

# Shown in the page header. Defaults to the project folder name; override with
#   PHOTO_PROJECT_TITLE="Iceland 2026" python3 scripts/browser.py
PROJECT_TITLE = os.environ.get(
    "PHOTO_PROJECT_TITLE",
    PROJECT.name.replace("_", " ").replace("-", " ").title(),
)

SELECTED.mkdir(exist_ok=True)
THUMBS.mkdir(exist_ok=True)

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
THUMB_SIZE = (280, 280)

MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def month_from_filename(filename: str) -> str | None:
    m = re.match(r"^\d{4}-(\d{2})", filename)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 12:
            return f"{n:02d} - {MONTH_NAMES[n - 1]}"
    return None


def month_dirs():
    return sorted(d for d in RAW.iterdir() if d.is_dir() and not d.name.startswith("."))


def photos_in(directory: Path):
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in PHOTO_EXTS)


def is_kept(filename: str) -> bool:
    return (SELECTED / filename).exists()


def make_thumb(month: str, filename: str) -> Path:
    thumb_dir = THUMBS / month
    thumb_dir.mkdir(exist_ok=True)
    thumb_path = thumb_dir / (Path(filename).stem + ".jpg")
    if not thumb_path.exists():
        # In cull mode the source is selected/; otherwise raw/<month>/
        src = (SELECTED / filename) if CULL else (RAW / month / filename)
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            img.convert("RGB").save(thumb_path, "JPEG", quality=75)
    return thumb_path


# ---------------------------------------------------------------------------
# API — months
# ---------------------------------------------------------------------------

@app.route("/api/months")
def api_months():
    if CULL:
        groups: dict[str, list] = {}
        for p in photos_in(SELECTED):
            month = month_from_filename(p.name) or "Unknown"
            groups.setdefault(month, []).append(p)
        return jsonify([
            {"name": m, "count": len(ps), "kept": len(ps)}
            for m, ps in sorted(groups.items())
        ])
    result = []
    for d in month_dirs():
        ps = photos_in(d)
        kept = sum(1 for p in ps if is_kept(p.name))
        result.append({"name": d.name, "count": len(ps), "kept": kept})
    return jsonify(result)


@app.route("/api/photos/<month>")
def api_photos(month):
    if CULL:
        prefix = month[:2] + "-"   # "01 - January" → "01-"
        # match YYYY-<MM>- e.g. "2025-01-"
        ps = sorted(
            p for p in photos_in(SELECTED)
            if re.match(r"^\d{4}-" + re.escape(month[:2]) + r"-", p.name)
        )
        return jsonify([{"filename": p.name, "kept": True} for p in ps])
    d = RAW / month
    if not d.exists():
        abort(404)
    return jsonify([
        {"filename": p.name, "kept": is_kept(p.name)}
        for p in photos_in(d)
    ])


@app.route("/api/stats")
def api_stats():
    if CULL:
        remaining = sum(1 for p in SELECTED.iterdir() if p.suffix.lower() in PHOTO_EXTS)
        return jsonify({"total": remaining, "kept": remaining, "cull": True})
    total = sum(len(photos_in(d)) for d in month_dirs())
    kept  = sum(1 for p in SELECTED.iterdir() if p.suffix.lower() in PHOTO_EXTS)
    return jsonify({"total": total, "kept": kept, "cull": False})


# ---------------------------------------------------------------------------
# API — keep / remove
# ---------------------------------------------------------------------------

@app.route("/api/keep", methods=["POST"])
def api_keep():
    data = request.json
    if CULL:
        # Restore: copy back from raw/<month>/ → selected/
        month = month_from_filename(data["filename"])
        src = RAW / month / data["filename"] if month else None
        dst = SELECTED / data["filename"]
        if src and src.exists() and not dst.exists():
            shutil.copy2(str(src), str(dst))
        return jsonify({"kept": dst.exists()})
    src = RAW / data["month"] / data["filename"]
    dst = SELECTED / data["filename"]
    if src.exists() and not dst.exists():
        shutil.copy2(str(src), str(dst))
    return jsonify({"kept": dst.exists()})


@app.route("/api/unkept", methods=["POST"])
def api_unkept():
    dst = SELECTED / request.json["filename"]
    if dst.exists():
        dst.unlink()
    return jsonify({"kept": False})


# ---------------------------------------------------------------------------
# Media routes
# ---------------------------------------------------------------------------

@app.route("/thumb/<month>/<filename>")
def thumb(month, filename):
    try:
        return send_file(make_thumb(month, filename), mimetype="image/jpeg")
    except Exception:
        abort(404)


@app.route("/photo/<month>/<filename>")
def photo(month, filename):
    path = (SELECTED / filename) if CULL else (RAW / month / filename)
    if not path.exists():
        abort(404)
    if path.suffix.lower() in {".heic", ".heif"}:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=90)
            buf.seek(0)
            return send_file(buf, mimetype="image/jpeg")
    return send_file(path)


@app.route("/api/mode")
def api_mode():
    return jsonify({"cull": CULL})


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__PROJECT_TITLE__ — Photo Browser</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#111;color:#ddd;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#hdr{background:#1c1c1c;border-bottom:1px solid #2e2e2e;padding:10px 18px;
     display:flex;align-items:center;gap:16px;flex-shrink:0}
#hdr h1{font-size:14px;font-weight:600;color:#fff;white-space:nowrap}
#mode-badge{font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600;white-space:nowrap}
#mode-badge.select{background:#1a3a1a;color:#4caf50}
#mode-badge.cull{background:#3a1a1a;color:#e57373}
#pb-wrap{flex:1;background:#2e2e2e;height:6px;border-radius:3px;overflow:hidden}
#pb{height:100%;width:0%;transition:width .4s}
#pb.select{background:#4caf50}
#pb.cull{background:#e57373}
#pt{font-size:12px;color:#888;white-space:nowrap}
#main{display:flex;flex:1;overflow:hidden}
#sidebar{width:190px;background:#161616;border-right:1px solid #2a2a2a;
         overflow-y:auto;padding:6px 0;flex-shrink:0}
.mi{padding:9px 14px;cursor:pointer;display:flex;justify-content:space-between;
    align-items:center;border-left:3px solid transparent;transition:background .1s}
.mi:hover{background:#1f1f1f}
.mi.active{background:#1f1f1f}
.mi.active.select{border-left-color:#4caf50}
.mi.active.cull{border-left-color:#e57373}
.mn{font-size:12px}
.mm{font-size:11px;color:#555}
.mm .kc.select{color:#4caf50}
.mm .kc.cull{color:#e57373}
#gc{flex:1;overflow-y:auto;padding:14px}
#gh{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
#gt{font-size:16px;font-weight:600}
#gs{font-size:12px;color:#777}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:6px}
.card{position:relative;aspect-ratio:1;cursor:pointer;border-radius:3px;
      overflow:hidden;background:#1e1e1e;border:2px solid transparent;transition:all .1s}
.card:hover{border-color:#444}
.card.kept.select{border-color:#4caf50}
.card.kept.cull{border-color:#4caf50}
.card.removed{opacity:.35}
.card img{width:100%;height:100%;object-fit:cover;display:block}
.card .ck{position:absolute;top:5px;right:5px;border-radius:50%;
           width:20px;height:20px;display:none;
           align-items:center;justify-content:center;font-size:12px;font-weight:700}
.card.kept .ck{display:flex;background:#4caf50;color:#fff}
.card.removed .ck{display:flex;background:#555;color:#999}
.card .fn{position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.75);
           font-size:10px;padding:3px 5px;opacity:0;transition:opacity .1s;
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card:hover .fn{opacity:1}
#lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.96);z-index:100;flex-direction:column}
#lb.open{display:flex}
#lbh{padding:10px 16px;display:flex;justify-content:space-between;align-items:center;
     background:rgba(0,0,0,.4);flex-shrink:0}
#lbfn{font-size:13px;color:#bbb}
#lbacts{display:flex;gap:8px;align-items:center}
#lbbtn{padding:7px 18px;border-radius:4px;border:none;cursor:pointer;
       font-size:13px;font-weight:600;transition:all .15s;min-width:100px}
#lbbtn.action-keep{background:#4caf50;color:#fff}
#lbbtn.action-add{background:#2a2a2a;color:#888;border:1px solid #444}
#lbbtn.action-remove{background:#c62828;color:#fff}
#lbbtn.action-restore{background:#2a2a2a;color:#888;border:1px solid #444}
#lbx{background:none;border:none;color:#666;font-size:22px;cursor:pointer;padding:0 6px;line-height:1}
#lbx:hover{color:#fff}
#lbiw{flex:1;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden}
#lbimg{max-width:calc(100% - 100px);max-height:100%;object-fit:contain}
.lbnav{position:absolute;top:50%;transform:translateY(-50%);background:rgba(0,0,0,.4);
       border:none;color:#fff;font-size:32px;padding:14px 10px;cursor:pointer;
       border-radius:4px;opacity:.5;transition:opacity .15s;line-height:1}
.lbnav:hover{opacity:1}
#lbprev{left:12px}
#lbnext{right:12px}
#lbctr{text-align:center;padding:6px;font-size:12px;color:#555;flex-shrink:0}
#lbhint{font-size:11px;color:#444;margin-top:2px}
.empty{text-align:center;padding:60px;color:#444;font-size:14px}
.loading{text-align:center;padding:40px;color:#444;font-size:13px}
</style>
</head>
<body>
<div id="hdr">
  <h1>__PROJECT_TITLE__</h1>
  <span id="mode-badge"></span>
  <div id="pb-wrap"><div id="pb"></div></div>
  <div id="pt"></div>
</div>
<div id="main">
  <div id="sidebar"><div class="loading">Loading...</div></div>
  <div id="gc"><div class="empty">Select a month to begin</div></div>
</div>
<div id="lb">
  <div id="lbh">
    <span id="lbfn"></span>
    <div id="lbacts">
      <button id="lbbtn" onclick="lbToggle()"></button>
      <button id="lbx" onclick="lbClose()">&#x2715;</button>
    </div>
  </div>
  <div id="lbiw">
    <button class="lbnav" id="lbprev" onclick="lbNav(-1)">&#8249;</button>
    <img id="lbimg" src="" alt="">
    <button class="lbnav" id="lbnext" onclick="lbNav(1)">&#8250;</button>
  </div>
  <div id="lbctr">
    <div id="lbpos"></div>
    <div id="lbhint"></div>
  </div>
</div>

<script>
// photos = full list from server; visible = what's shown (filtered in cull mode)
let months=[], curMonth=null, photos=[], visible=[], lbIdx=0, CULL=false;

async function init(){
  const mode=await fetch('/api/mode').then(r=>r.json());
  CULL=mode.cull;
  const badge=document.getElementById('mode-badge'), pb=document.getElementById('pb');
  if(CULL){
    badge.textContent='CULL MODE'; badge.className='cull'; pb.className='cull';
    document.getElementById('lbhint').textContent='K / Space — remove  |  ← → — navigate  |  Esc — close';
  } else {
    badge.textContent='SELECT MODE'; badge.className='select'; pb.className='select';
    document.getElementById('lbhint').textContent='K / Space — keep  |  ← → — navigate  |  Esc — close';
  }
  months=await fetch('/api/months').then(r=>r.json());
  renderSidebar();
  updateProgress();
}

function renderSidebar(){
  const mode=CULL?'cull':'select';
  document.getElementById('sidebar').innerHTML=months.map(m=>`
    <div class="mi ${curMonth===m.name?'active '+mode:''}" onclick="selectMonth('${m.name}')">
      <span class="mn">${m.name}</span>
      <span class="mm"><span class="kc ${mode}">${m.kept}</span>/${m.count}</span>
    </div>`).join('');
}

async function selectMonth(name){
  curMonth=name; renderSidebar();
  document.getElementById('gc').innerHTML='<div class="loading">Loading...</div>';
  photos=await fetch('/api/photos/'+encodeURIComponent(name)).then(r=>r.json());
  visible=CULL ? photos.filter(p=>p.kept) : photos;
  renderGrid();
}

function renderGrid(){
  const mode=CULL?'cull':'select';
  const subtitle=CULL
    ? visible.length+' remaining'
    : photos.filter(p=>p.kept).length+' kept of '+photos.length;
  document.getElementById('gc').innerHTML=`
    <div id="gh"><div id="gt">${curMonth}</div><div id="gs">${subtitle}</div></div>
    <div id="grid">${visible.map((p,i)=>`
      <div class="card kept ${mode}" id="c${i}" onclick="openLb(${i})">
        <img src="/thumb/${encodeURIComponent(curMonth)}/${encodeURIComponent(p.filename)}"
             loading="lazy" alt="">
        <div class="ck">&#x2713;</div>
        <div class="fn">${p.filename}</div>
      </div>`).join('')}
    </div>`;
}

async function toggleKeep(i){
  const p=visible[i];
  const endpoint=p.kept?'/api/unkept':'/api/keep';
  const r=await fetch(endpoint,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({month:curMonth,filename:p.filename})
  }).then(r=>r.json());

  if(CULL){
    // Remove from visible entirely and re-render grid
    visible.splice(i,1);
    renderGrid();
    const m=months.find(m=>m.name===curMonth);
    if(m){m.kept=visible.length; renderSidebar();}
    updateProgress();
    if(document.getElementById('lb').classList.contains('open')){
      if(visible.length===0) lbClose();
      else { lbIdx=Math.min(i, visible.length-1); renderLb(); }
    }
  } else {
    visible[i].kept=r.kept;
    const card=document.getElementById('c'+i);
    if(card){
      card.classList.toggle('kept',r.kept);
      card.querySelector('.ck').innerHTML=r.kept?'&#x2713;':'&#x2715;';
    }
    const count=visible.filter(p=>p.kept).length;
    const gs=document.getElementById('gs');
    if(gs) gs.textContent=count+' kept of '+photos.length;
    const m=months.find(m=>m.name===curMonth);
    if(m){m.kept=count; renderSidebar();}
    updateProgress();
    if(lbIdx===i) renderLbBtn();
  }
}

async function updateProgress(){
  const {total,kept}=await fetch('/api/stats').then(r=>r.json());
  document.getElementById('pb').style.width=(total?kept/total*100:0)+'%';
  document.getElementById('pt').textContent=CULL ? kept+' remaining' : kept+' of '+total+' kept';
}

function openLb(i){lbIdx=i; document.getElementById('lb').classList.add('open'); renderLb();}
function lbClose(){document.getElementById('lb').classList.remove('open');}
function lbNav(d){if(!visible.length) return; lbIdx=(lbIdx+d+visible.length)%visible.length; renderLb();}

function renderLb(){
  const p=visible[lbIdx];
  document.getElementById('lbimg').src='/photo/'+encodeURIComponent(curMonth)+'/'+encodeURIComponent(p.filename);
  document.getElementById('lbfn').textContent=p.filename;
  document.getElementById('lbpos').textContent=(lbIdx+1)+' / '+visible.length;
  renderLbBtn();
}

function renderLbBtn(){
  const btn=document.getElementById('lbbtn');
  if(CULL){
    btn.textContent='Remove'; btn.className='action-remove';
  } else {
    const kept=visible[lbIdx].kept;
    btn.textContent=kept?'Kept ✓':'Keep';
    btn.className=kept?'action-keep':'action-add';
  }
}

async function lbToggle(){await toggleKeep(lbIdx);}

document.addEventListener('keydown',e=>{
  if(!document.getElementById('lb').classList.contains('open')) return;
  if(e.key==='ArrowLeft') lbNav(-1);
  else if(e.key==='ArrowRight') lbNav(1);
  else if(e.key==='k'||e.key==='K'||e.key===' '){e.preventDefault();lbToggle();}
  else if(e.key==='Escape') lbClose();
});

init();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML.replace("__PROJECT_TITLE__", PROJECT_TITLE)


if __name__ == "__main__":
    mode = "CULL mode (browsing selected/)" if CULL else "SELECT mode (browsing raw/)"
    print(f"Opening photo browser at http://localhost:8765  [{mode}]")
    print("Ctrl+C to stop.")
    app.run(port=8765, debug=False)
