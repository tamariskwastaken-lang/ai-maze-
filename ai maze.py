#!/usr/bin/env python3
"""
AI Maze Race (local app) - the same picker page as the web version, but every AI
(Claude, ChatGPT, Gemini, Grok, DeepSeek) is asked AUTOMATICALLY by API. No copy/paste.

How it works: this script starts a small server on your own computer and opens the
page in your browser. Pick an AI, click "Ask the AI", and the page asks that AI
through this script, times it, and walks its route through the maze.
Your API keys stay inside this script and are never sent to the browser.

Setup:
  1. Python 3.8+ (no extra packages needed).
  2. Paste the API keys you have into KEYS_IN_FILE below (or set them as
     environment variables with the same names). AIs without a key are greyed out.
  3. Run it:  python maze_app.py        (Mac: python3 maze_app.py)
  Test without keys: set DEMO_MODE = True below.
Stop it with Ctrl+C or by closing the window.
"""
import argparse, json, os, random, re, sys, threading, time, urllib.request, urllib.error, webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---- EASY SETTINGS ----
MAZE_SEED = 2024    # the maze every AI gets. Same number = exactly the same maze, every time.
                    # Set to None to get a different random maze each time you start the script.
DEMO_MODE = True   # True = fake "AI" that solves it perfectly, for testing with no keys
KEYS_IN_FILE = {    # paste your keys between the quotes
    "ANTHROPIC_API_KEY": "",
    "OPENAI_API_KEY": "",
    "GEMINI_API_KEY": "",
    "XAI_API_KEY": "",
    "DEEPSEEK_API_KEY": "",
}
# Model names change often - check each company's docs and edit if a call errors.
MODELS = {
    "Claude":   "claude-sonnet-5-5",
    "ChatGPT":  "gpt-5",
    "Gemini":   "gemini-2.5-pro",
    "Grok":     "grok-4",
    "DeepSeek": "deepseek-chat",
}
TIMEOUT = 300   # seconds to wait for an AI before giving up
PORT = 8765
SEED = None   # filled in at startup

KEYNAMES = {"Claude": "ANTHROPIC_API_KEY", "ChatGPT": "OPENAI_API_KEY", "Gemini": "GEMINI_API_KEY",
            "Grok": "XAI_API_KEY", "DeepSeek": "DEEPSEEK_API_KEY"}
for _k, _v in KEYS_IN_FILE.items():
    if _v:
        os.environ[_k] = _v


# ---------------- AI calls ----------------
def post(url, headers, body):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:200]}")


def solve_demo(grid):
    H, W = len(grid), len(grid[0])
    dist = {(H - 2, W - 2): 0}
    q = deque([(H - 2, W - 2)])
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (y + dy, x + dx)
            if grid[n[0]][n[1]] != "#" and n not in dist:
                dist[n] = dist[(y, x)] + 1
                q.append(n)
    y, x, out = 1, 1, ""
    while (y, x) != (H - 2, W - 2):
        for m, (dy, dx) in {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}.items():
            if dist.get((y + dy, x + dx), 10**9) < dist[(y, x)]:
                out += m; y += dy; x += dx
                break
    return out


def ask(ai, prompt, grid):
    if DEMO_MODE:
        time.sleep(0.5 + (hash(ai) % 30) / 10)
        return json.dumps({"moves": solve_demo(grid)})
    key, model = os.environ.get(KEYNAMES[ai]), MODELS[ai]
    if not key:
        raise RuntimeError(f"No {KEYNAMES[ai]} set")
    msg = [{"role": "user", "content": prompt}]
    if ai == "Claude":
        d = post("https://api.anthropic.com/v1/messages",
                 {"x-api-key": key, "anthropic-version": "2023-06-01"},
                 {"model": model, "max_tokens": 8000, "messages": msg})
        return "".join(b.get("text", "") for b in d["content"])
    if ai == "Gemini":
        d = post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                 {}, {"contents": [{"parts": [{"text": prompt}]}]})
        return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
    url = {"ChatGPT": "https://api.openai.com/v1/chat/completions",
           "Grok": "https://api.x.ai/v1/chat/completions",
           "DeepSeek": "https://api.deepseek.com/chat/completions"}[ai]
    d = post(url, {"Authorization": f"Bearer {key}"}, {"model": model, "messages": msg})
    return d["choices"][0]["message"]["content"]


def status():
    return {n: bool(DEMO_MODE or os.environ.get(KEYNAMES[n])) for n in MODELS}


# ---------------- page ----------------
PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Maze Race</title>
<style>
:root{--bg:#f6f7f9;--fg:#15171a;--card:#fff;--muted:#6b7280;--line:#e2e5ea;--wall:#15171a;--floor:#fff;--trail:#bcd3ff;--me:#2f6fed;--goal:#1db954;--bad:#d93025;--accent:#2f6fed}
@media (prefers-color-scheme:dark){:root{--bg:#111317;--fg:#eceef1;--card:#1a1d23;--muted:#9aa3af;--line:#2a2e36;--wall:#05070a;--floor:#262a33;--trail:#2c4a86;--me:#6b9bff;--goal:#34d17a;--bad:#ff6b61;--accent:#6b9bff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:720px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:0 0 4px}
p.sub{margin:0 0 14px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:12px}
canvas{display:block;width:100%;height:auto;border-radius:8px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
button,select{font:inherit;padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
input{font:inherit;padding:9px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);width:120px}
button.go{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:600}
button:disabled,select:disabled{opacity:.5}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;text-align:center}
.stat b{display:block;font-size:1.35rem;font-variant-numeric:tabular-nums}
.stat span{color:var(--muted);font-size:.8rem}
#status{min-height:1.5em;margin:8px 0 0}
.ok{color:var(--goal)}.bad{color:var(--bad)}
.tbl{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:500}
</style></head>
<body><main>
<h1> AI Maze Race</h1>
<p class="sub">Pick an AI and ask it to solve the maze. The clock runs from your click until the player reaches the green square. Every AI is asked automatically.</p>

<div class="stats">
  <div class="stat"><b id="clock">0.0s</b><span>total time</span></div>
  <div class="stat"><b id="think">-</b><span>AI thinking</span></div>
  <div class="stat"><b id="pts">0</b><span>points</span></div>
</div>

<div class="card">
  <canvas id="cv"></canvas>
  <p id="status"></p>
</div>

<div class="card row">
  <button class="go" id="ask">Ask the AI to solve it</button>
  <select id="tier" aria-label="Which AI"></select>
  <button id="new">New random maze</button>
</div>
<div class="card row">
  <span>Maze number:</span>
  <input id="seed" type="number" min="0" step="1" aria-label="Maze number">
  <button id="load">Load this maze</button>
  <span class="sub" style="margin:0">Same number = same maze for every AI.</span>
</div>

<div class="card tbl">
  <table>
    <thead><tr><th>#</th><th>Maze</th><th>AI</th><th>Result</th><th>Time</th><th>Points</th></tr></thead>
    <tbody id="log"><tr><td colspan="6" style="color:var(--muted)">No runs yet</td></tr></tbody>
  </table>
</div>
<p class="sub">Points: 1000 for reaching the end, fewer the further away the player stops (10 per step of distance).</p>
</main>

<script>
(function(){
var CFG=__CFG__, STATUS=CFG.status;
var CW=10, CH=7, W=CW*2+1, H=CH*2+1;
var grid, dist, seed=CFG.seed;
var px, py, trail, busy=false, t0=0, ticker=null, runNo=0;
var cv=document.getElementById('cv'), ctx=cv.getContext('2d');
var $=function(id){return document.getElementById(id)};

// picker: greyed out when no API key is set
var first=null;
Object.keys(STATUS).forEach(function(n){
  var o=document.createElement('option');o.value=n;o.textContent=n+(STATUS[n]?'':' (no key)');o.disabled=!STATUS[n];
  $('tier').appendChild(o);if(STATUS[n]&&!first)first=n;
});
if(first)$('tier').value=first;else $('ask').disabled=true;

function rng(a){return function(){a|=0;a=a+0x6D2B79F5|0;var t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}

function makeMaze(){
  var r=rng(seed), g=[], y, x;
  for(y=0;y<H;y++){g.push([]);for(x=0;x<W;x++)g[y].push('#')}
  var stack=[[1,1]]; g[1][1]=' ';
  while(stack.length){
    var c=stack[stack.length-1], opts=[], d=[[0,-2],[0,2],[-2,0],[2,0]];
    d.forEach(function(v){var ny=c[0]+v[0],nx=c[1]+v[1];if(ny>0&&ny<H-1&&nx>0&&nx<W-1&&g[ny][nx]==='#')opts.push(v)});
    if(!opts.length){stack.pop();continue}
    var v=opts[Math.floor(r()*opts.length)];
    g[c[0]+v[0]/2][c[1]+v[1]/2]=' '; g[c[0]+v[0]][c[1]+v[1]]=' ';
    stack.push([c[0]+v[0],c[1]+v[1]]);
  }
  grid=g;
  dist=[];for(y=0;y<H;y++)dist.push(new Array(W).fill(-1));
  var q=[[H-2,W-2]];dist[H-2][W-2]=0;
  while(q.length){var p=q.shift();[[1,0],[-1,0],[0,1],[0,-1]].forEach(function(v){var ny=p[0]+v[0],nx=p[1]+v[1];if(g[ny][nx]===' '&&dist[ny][nx]<0){dist[ny][nx]=dist[p[0]][p[1]]+1;q.push([ny,nx])}})}
}

function reset(){
  px=1;py=1;trail=[[1,1]];
  $('clock').textContent='0.0s';$('think').textContent='-';$('pts').textContent='0';
  setStatus('');draw();
}
function setStatus(t,cls){var s=$('status');s.textContent=t;s.className=cls||''}

function draw(){
  var dpr=window.devicePixelRatio||1, w=cv.clientWidth||600, cs=w/W;
  cv.width=Math.round(w*dpr);cv.height=Math.round(cs*H*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  var cssv=function(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()};
  var y,x;
  for(y=0;y<H;y++)for(x=0;x<W;x++){
    ctx.fillStyle=grid[y][x]==='#'?cssv('--wall'):cssv('--floor');
    ctx.fillRect(x*cs,y*cs,cs+.5,cs+.5);
  }
  ctx.fillStyle=cssv('--trail');
  trail.forEach(function(t){ctx.fillRect(t[1]*cs,t[0]*cs,cs+.5,cs+.5)});
  ctx.fillStyle=cssv('--goal');ctx.fillRect((W-2)*cs,(H-2)*cs,cs,cs);
  ctx.fillStyle=cssv('--me');ctx.beginPath();ctx.arc((px+.5)*cs,(py+.5)*cs,cs*.36,0,7);ctx.fill();
}

function fmt(ms){return (ms/1000).toFixed(1)+'s'}
function startTicker(){t0=performance.now();ticker=setInterval(function(){$('clock').textContent=fmt(performance.now()-t0)},50)}
function stopTicker(){clearInterval(ticker);var t=performance.now()-t0;$('clock').textContent=fmt(t);return t}
function release(){busy=false;$('ask').disabled=!first;$('new').disabled=false;$('load').disabled=false;$('seed').disabled=false;$('tier').disabled=false}
function lock(){busy=true;$('ask').disabled=true;$('new').disabled=true;$('load').disabled=true;$('seed').disabled=true;$('tier').disabled=true}

function addLog(who,res,ms,pts,mz){
  var tb=$('log');if(runNo===1)tb.innerHTML='';
  var tr=document.createElement('tr');
  [runNo,mz,who,res,fmt(ms),pts].forEach(function(v){var td=document.createElement('td');td.textContent=v;tr.appendChild(td)});
  tb.insertBefore(tr,tb.firstChild);
}

function finish(who,res,ok){
  var ms=stopTicker(), rem=dist[py][px], pts=Math.max(0,1000-rem*10);
  $('pts').textContent=pts;
  runNo++;addLog(who,res,ms,pts,seed);
  setStatus(who+': '+res+' ('+fmt(ms)+', '+pts+' points)',ok?'ok':'bad');
  release();
}

function walk(who,moves,thinkMs){
  var i=0, D={U:[-1,0],D:[1,0],L:[0,-1],R:[0,1]};
  setStatus(who+' answered in '+fmt(thinkMs)+' - walking '+moves.length+' moves...');
  var iv=setInterval(function(){
    if(i>=moves.length){clearInterval(iv);return finish(who,'Ran out of moves before the end',false)}
    var d=D[moves[i]];i++;
    var ny=py+d[0],nx=px+d[1];
    if(grid[ny][nx]==='#'){clearInterval(iv);return finish(who,'Hit a wall at move '+i,false)}
    py=ny;px=nx;trail.push([py,px]);draw();
    if(px===W-2&&py===H-2){clearInterval(iv);finish(who,'Reached the end in '+i+' moves',true)}
  },35);
}

function buildPrompt(){
  var map=grid.map(function(r,y){return r.map(function(c,x){return (y===1&&x===1)?'S':(y===H-2&&x===W-2)?'G':c}).join('')}).join('\n');
  return 'Solve this maze. # is a wall, a space is open floor, S is the start (row 1, col 1) and G is the goal (row '+(H-2)+', col '+(W-2)+'). Rows and columns are 0-indexed from the top-left.\n\n'+map+'\n\nEach move steps exactly one character: U = up (row-1), D = down (row+1), L = left (col-1), R = right (col+1). You cannot step onto #. Give the shortest sequence of moves from S to G. Reply with ONLY JSON like {"moves":"RRDDLU"} and nothing else.';
}
function parseMoves(txt){
  var m=/"moves"\s*:\s*"([^"]*)"/i.exec(txt||'');
  if(m)return m[1].toUpperCase().replace(/[^UDLR]/g,'');
  var f=/[UDLRudlr]{8,}/.exec(txt||'');
  return f?f[0].toUpperCase():'';
}

async function ask(){
  if(busy)return;
  var who=$('tier').value;
  lock();reset();startTicker();setStatus('Asking '+who+'... it is thinking.');
  var data;
  try{
    var r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ai:who,prompt:buildPrompt(),grid:grid.map(function(r){return r.join('')})})});
    data=await r.json();
  }catch(e){stopTicker();release();setStatus('Could not reach the local script. Is it still running?','bad');return}
  if(data.error){stopTicker();release();setStatus(who+' failed: '+data.error,'bad');return}
  var thinkMs=data.secs*1000;$('think').textContent=fmt(thinkMs);
  var moves=parseMoves(data.text);
  if(!moves){finish(who,'No usable answer',false);return}
  walk(who,moves,thinkMs);
}

$('ask').onclick=ask;
function setMaze(n){seed=n;$('seed').value=n;makeMaze();reset();setStatus('Maze '+n+' loaded.')}
$('new').onclick=function(){if(!busy)setMaze(Math.floor(Math.random()*1e6))};
$('load').onclick=function(){var n=parseInt($('seed').value,10);if(!busy&&n>=0)setMaze(n)};
$('seed').onkeydown=function(e){if(e.key==='Enter')$('load').click()};
window.addEventListener('resize',function(){draw()});
makeMaze();reset();$('seed').value=seed;
if(!first)setStatus('No API keys found. Paste your keys into KEYS_IN_FILE at the top of maze_app.py (or set DEMO_MODE = True), save, then stop and restart the script and refresh this page.','bad');
})();
</script></body></html>'''


# ---------------- server ----------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = PAGE.replace("__CFG__", json.dumps({"status": status(), "seed": SEED}))
            return self._send(200, page, "text/html; charset=utf-8")
        self._send(404, "{}")

    def do_POST(self):
        origin = self.headers.get("Origin")
        okay = (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")
        if self.path != "/api/ask" or (origin and origin not in okay):
            return self._send(403, json.dumps({"error": "forbidden"}))
        t0 = time.perf_counter()
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if d.get("ai") not in MODELS:
                raise RuntimeError("unknown AI")
            text = ask(d["ai"], d["prompt"], d.get("grid"))
            self._send(200, json.dumps({"text": text, "secs": time.perf_counter() - t0}))
        except Exception as e:
            self._send(200, json.dumps({"error": str(e), "secs": time.perf_counter() - t0}))


def main():
    global PORT, SEED
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    PORT = a.port
    SEED = MAZE_SEED if MAZE_SEED is not None else random.randrange(10**6)
    st = status()
    if not any(st.values()):
        print("Heads up: no API keys found, so every AI will be greyed out.\n"
              "Paste keys into KEYS_IN_FILE at the top of this file, or set DEMO_MODE = True to test.")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    url = f"http://127.0.0.1:{PORT}/"
    print("AI Maze Race running at", url, "- press Ctrl+C to stop")
    print("Maze number:", SEED, "(every AI gets this same maze)")
    print("Ready:", ", ".join(n for n, v in st.items() if v) or "none")
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
