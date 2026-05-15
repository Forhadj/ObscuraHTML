"""
ObscuraHTML v1.0.0
Author  : Forhad Hassan (@Forhadj)
GitHub  : https://github.com/Forhadj/ObscuraHTML
Purpose : HTML obfuscation / protection tool
          — stops casual copiers & scrapers.
          — NOT a claim of unbreakable security.

HONEST SECURITY NOTE:
  • All decryption happens in the browser → key is always
    accessible to a determined attacker via DevTools.
  • Goal: "annoying to reverse" — not "impossible".
"""

import base64
import hashlib
import json
import os
import random
import re
import string
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path

# ── Rich UI ───────────────────────────────────────────────────
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from time import sleep

# ── Optional brotli (Python-side only) ───────────────────────
try:
    import brotli as _brotli_lib
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False

console = Console()

OUTPUT_PREFIX = "obscura_protected_"
LOG_FILE      = "obscura_log.json"
VERSION       = "1.0.0"
AUTHOR        = "Forhad"
TOOL_NAME     = "ObscuraHTML"

PAKO_CDN = "https://cdnjs.cloudflare.com/ajax/libs/pako/2.1.0/pako.min.js"

# ═══════════════════════════════════════════════════════════════
#  THEME — Neon-Cyber Green on Dark
# ═══════════════════════════════════════════════════════════════
T_PRIMARY   = "bright_green"
T_ACCENT    = "cyan"
T_WARN      = "yellow"
T_DANGER    = "bright_red"
T_DIM       = "dim white"
T_BORDER_P  = "green"
T_BORDER_A  = "cyan"
T_BORDER_W  = "yellow"
T_BORDER_D  = "red"


# ═══════════════════════════════════════════════════════════════
#  SAFE HTML MINIFIER
#  Skips <pre> <script> <style> <textarea> blocks
# ═══════════════════════════════════════════════════════════════

_VERBATIM_RE = re.compile(
    r"(<(?:script|style|pre|textarea)[^>]*>.*?</(?:script|style|pre|textarea)>)",
    re.DOTALL | re.IGNORECASE,
)

def minify_html(html: str) -> str:
    parts  = _VERBATIM_RE.split(html)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            result.append(part)
        else:
            p = re.sub(r"<!--(?!\[if).*?-->", "", part, flags=re.DOTALL)
            p = re.sub(r">\s+<", "><", p)
            p = re.sub(r"\n\s*\n", "\n", p)
            p = "\n".join(line.strip() for line in p.splitlines())
            p = re.sub(r" {2,}", " ", p)
            result.append(p.strip())
    return "".join(result)


# ═══════════════════════════════════════════════════════════════
#  FILE READ + COMPRESS
# ═══════════════════════════════════════════════════════════════

def _compress(data: bytes) -> tuple[bytes, str]:
    compressed = zlib.compress(data, level=9)
    return compressed, "deflate"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ═══════════════════════════════════════════════════════════════
#  ENCRYPTION  (AES-256-GCM  or  SHA-256-XOR fallback)
# ═══════════════════════════════════════════════════════════════

def encrypt_bytes(data: bytes) -> tuple[str, str, str, str]:
    try:
        from Crypto.Cipher import AES
        from Crypto.Random import get_random_bytes
        key    = get_random_bytes(32)
        iv     = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ct, tag = cipher.encrypt_and_digest(data)
        return (base64.b64encode(ct + tag).decode(), key.hex(), iv.hex(), "AES-256-GCM")
    except ImportError:
        key_bytes = bytes(random.randint(0, 255) for _ in range(32))
        stream    = _sha256_keystream(key_bytes, len(data))
        xored     = bytes(a ^ b for a, b in zip(data, stream))
        return (base64.b64encode(xored).decode(), key_bytes.hex(), "00" * 12, "XOR-SHA256")


def _sha256_keystream(seed: bytes, length: int) -> bytes:
    out, blk = b"", seed
    while len(out) < length:
        blk  = hashlib.sha256(blk).digest()
        out += blk
    return out[:length]


# ═══════════════════════════════════════════════════════════════
#  JS HELPERS
# ═══════════════════════════════════════════════════════════════

def _rv(prefix: str = "_o") -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase, k=7))


def _decoys(n: int = 6) -> str:
    return " ".join(f"var {_rv()}=null;" for _ in range(n))


def _chunked_js_array(b64: str, varname: str) -> str:
    size   = random.randint(80, 150)
    chunks = [b64[i:i+size] for i in range(0, len(b64), size)]
    items  = ",\n    ".join(f'"{c}"' for c in chunks)
    return f"const {varname} = [\n    {items}\n  ].join('');"


def _pako_script_tag() -> str:
    return f"""<script>
(function(){{
  if(typeof DecompressionStream==='undefined'){{
    var _s=document.createElement('script');
    _s.src='{PAKO_CDN}';
    _s.async=false;
    document.head.appendChild(_s);
  }}
}})();
</script>"""


def _js_decompress(bytes_var: str, result_var: str) -> str:
    return f"""
  let {result_var};
  if(typeof DecompressionStream !== 'undefined'){{
    const _ds=new DecompressionStream('deflate');
    const _dw=_ds.writable.getWriter();
    _dw.write({bytes_var}); _dw.close();
    {result_var}=new TextDecoder().decode(
      await new Response(_ds.readable).arrayBuffer()
    );
  }} else if(typeof pako!=='undefined'){{
    {result_var}=pako.inflate({bytes_var},{{to:'string'}});
  }} else {{
    throw new Error('ObscuraHTML: decompressor unavailable');
  }}
"""


_JS_XOR_HELPER = """
  function _obscXOR(_data,_key){
    var _stream=new Uint8Array(_data.length);
    var _state=Array.from(_key);
    var _pos=0;
    while(_pos<_data.length){
      var _sum=_state.reduce(function(a,b){return(a*31+b)&0xFFFFFFFF;},1);
      for(var _j=0;_j<_state.length&&_pos<_data.length;_j++,_pos++){
        _stream[_pos]=(_sum>>(_j%4)*8)&0xFF;
      }
      _state=_state.map(function(b,i){return(b^(_sum>>(i%4)*8))&0xFF;});
    }
    return _data.map(function(b,i){return b^_stream[i];});
  }
"""


def _js_decrypt(ct_b64, key_hex, iv_hex, method, result_var):
    vct  = _rv("_ct"); vkey = _rv("_k")
    viv  = _rv("_iv"); vcko = _rv("_ck")
    if method == "AES-256-GCM":
        return f"""
  const {vct}=Uint8Array.from(atob("{ct_b64}"),c=>c.charCodeAt(0));
  const {vkey}=new Uint8Array("{key_hex}".match(/../g).map(h=>parseInt(h,16)));
  const {viv}=new Uint8Array("{iv_hex}".match(/../g).map(h=>parseInt(h,16)));
  let {result_var};
  if(window.crypto&&window.crypto.subtle){{
    const {vcko}=await crypto.subtle.importKey('raw',{vkey},{{name:'AES-GCM'}},false,['decrypt']);
    {result_var}=new Uint8Array(await crypto.subtle.decrypt({{name:'AES-GCM',iv:{viv}}},{vcko},{vct}));
  }} else {{
    {result_var}=_obscXOR({vct},{vkey});
  }}
"""
    else:
        return f"""
  const {vct}=Uint8Array.from(atob("{ct_b64}"),c=>c.charCodeAt(0));
  const {vkey}=new Uint8Array("{key_hex}".match(/../g).map(h=>parseInt(h,16)));
  let {result_var}=_obscXOR({vct},{vkey});
"""


def _js_integrity(expected_hash, data_var):
    vh = _rv("_ih")
    return f"""
  if(window.crypto&&window.crypto.subtle){{
    const {vh}=Array.from(new Uint8Array(
      await crypto.subtle.digest('SHA-256',{data_var})
    )).map(b=>b.toString(16).padStart(2,'0')).join('');
    if({vh}!=="{expected_hash}"){{
      document.documentElement.innerHTML=
        '<body style="background:#0a0a0a;color:#ff4444;font-family:monospace;padding:2em">'
        +'<h2>⚠ ObscuraHTML — Integrity Check Failed</h2>'
        +'<p>This file has been tampered with.</p></body>';
      throw new Error('ObscuraHTML: tampered');
    }}
  }}
"""


def _js_safe_inject(html_var):
    return f"""
  var _p=new DOMParser();
  var _nd=_p.parseFromString({html_var},'text/html');
  document.replaceChild(document.adoptNode(_nd.documentElement),document.documentElement);
"""


def _js_anti_debug():
    return """
  (function(){
    setInterval(function(){debugger;},150);
    var _t=0;
    setInterval(function(){
      var _s=window.outerWidth-window.innerWidth>160||window.outerHeight-window.innerHeight>160;
      if(_s){
        if(!_t){
          _t=1;
          var _o=document.createElement('div');
          _o.id='_obscguard';
          _o.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;background:#000;color:#0f0;font-family:monospace;font-size:2em;display:flex;align-items:center;justify-content:center;z-index:99999';
          _o.textContent='⚠ Protected by ObscuraHTML';
          document.body.appendChild(_o);
        }
      }else{_t=0;var _e=document.getElementById('_obscguard');if(_e)_e.remove();}
    },500);
  })();
"""


# ═══════════════════════════════════════════════════════════════
#  LOADER BUILDERS
# ═══════════════════════════════════════════════════════════════

def _build_l1(b64, comp_hash):
    vd = _rv("_d"); vb = _rv("_b"); vh = _rv("_h")
    return f"""
(async function(){{
  /* ObscuraHTML v{VERSION} — Level 1 */
  {_decoys(4)}
  {_chunked_js_array(b64, vd)}
  const {vb}=Uint8Array.from(atob({vd}),c=>c.charCodeAt(0));
  {_js_integrity(comp_hash, vb)}
  {_js_decompress(vb, vh)}
  {_js_safe_inject(vh)}
}})();
"""


def _build_l2(ct_b64, key_hex, iv_hex, method, comp_hash):
    vp = _rv("_p"); vh = _rv("_h")
    return f"""
(async function(){{
  /* ObscuraHTML v{VERSION} — Level 2 | {method} */
  {_JS_XOR_HELPER}
  {_decoys(9)}
  {_js_decrypt(ct_b64, key_hex, iv_hex, method, vp)}
  {_js_integrity(comp_hash, vp)}
  {_js_decompress(vp, vh)}
  {_js_safe_inject(vh)}
}})();
"""


def _build_l3(ct_b64, key_hex, iv_hex, method, comp_hash):
    inner   = _build_l2(ct_b64, key_hex, iv_hex, method, comp_hash)
    enc     = base64.b64encode(inner.encode("utf-8")).decode()
    venc    = _rv("_e"); vcode = _rv("_c")
    vblob   = _rv("_bl"); vurl = _rv("_u")
    return f"""
(async function(){{
  /* ObscuraHTML v{VERSION} — Level 3 MAX */
  {_JS_XOR_HELPER}
  {_decoys(14)}
  {_js_anti_debug()}
  {_chunked_js_array(enc, venc)}
  const {vcode}=new TextDecoder().decode(
    Uint8Array.from(atob({venc}),c=>c.charCodeAt(0))
  );
  const {vblob}=new Blob([{vcode}],{{type:'application/javascript'}});
  const {vurl}=URL.createObjectURL({vblob});
  try{{await import({vurl});}}finally{{URL.revokeObjectURL({vurl});}}
}})();
"""


# ═══════════════════════════════════════════════════════════════
#  MASTER PROTECTION
# ═══════════════════════════════════════════════════════════════

def protect_html(html_text: str, level: int = 2) -> tuple[str, dict]:
    ts        = int(time.time())
    minified  = minify_html(html_text)
    raw_bytes = minified.encode("utf-8")
    compressed, comp_method = _compress(raw_bytes)
    comp_hash = sha256_hex(compressed)
    enc_method = "none"; key_label = "n/a"

    if level == 1:
        b64    = base64.b64encode(compressed).decode()
        loader = _build_l1(b64, comp_hash)
    elif level == 2:
        ct_b64, key_hex, iv_hex, enc_method = encrypt_bytes(compressed)
        key_label = f"{key_hex[:8]}…"
        loader = _build_l2(ct_b64, key_hex, iv_hex, enc_method, comp_hash)
    else:
        ct_b64, key_hex, iv_hex, enc_method = encrypt_bytes(compressed)
        key_label = f"{key_hex[:8]}…"
        loader = _build_l3(ct_b64, key_hex, iv_hex, enc_method, comp_hash)

    info = {
        "level": level, "compress": comp_method, "encrypt": enc_method,
        "key_label": key_label, "comp_hash": comp_hash[:16] + "…",
        "minified_sz": len(raw_bytes), "comp_sz": len(compressed),
        "timestamp": ts,
    }
    return _wrap_html(loader, info), info


def _wrap_html(loader_js: str, info: dict) -> str:
    dt  = datetime.fromtimestamp(info["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    sig = hashlib.sha256(
        f"{info['comp_hash']}{AUTHOR}{VERSION}".encode()
    ).hexdigest()[:16]
    comment = f"""<!--
  ObscuraHTML v{VERSION} | Level {info['level']}/3
  By {AUTHOR} | {dt} | sig:{sig}
  Key embedded in JS — obfuscation grade, not real crypto.
-->"""
    pako = _pako_script_tag()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="generator" content="ObscuraHTML v{VERSION} by {AUTHOR}">
<title>Protected</title>
</head>
{comment}
<body>
{pako}
<script type="module">
{loader_js}
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
#  FILE DISCOVERY — two modes
#  Mode A: scan a folder (or cwd)
#  Mode B: direct path  (e.g. /storage/emulated/0/index.html)
# ═══════════════════════════════════════════════════════════════

def discover_files(folder: Path) -> list[Path]:
    """Return all .html files in folder that aren't already protected."""
    return sorted(
        [f for f in folder.glob("*.html")
         if not f.name.startswith(OUTPUT_PREFIX)],
        key=lambda x: x.name,
    )


def resolve_input_path(raw: str) -> Path | None:
    """
    Accept:
      • Absolute path  : /storage/emulated/0/index.html
      • Relative path  : ./index.html  or  index.html
      • Tilde path     : ~/mysite/index.html
    Returns Path if the file exists + is .html, else None.
    """
    p = Path(raw.strip()).expanduser().resolve()
    if p.exists() and p.is_file() and p.suffix.lower() == ".html":
        return p
    return None


# ═══════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════

def load_log() -> list:
    if Path(LOG_FILE).exists():
        try:
            return json.loads(Path(LOG_FILE).read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def append_log(src, out, info, orig_sz, prot_sz):
    entries = load_log()
    entries.append({
        "version": VERSION, "timestamp": datetime.now().isoformat(),
        "original": str(src), "output": str(out),
        "level": info["level"], "compress": info["compress"],
        "encrypt": info["encrypt"], "orig_size": orig_sz, "prot_size": prot_sz,
        "ratio_pct": round((1 - prot_sz / orig_sz) * 100, 2) if orig_sz else 0,
    })
    Path(LOG_FILE).write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ═══════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════

def fmt_size(n):
    for u in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


BANNER_LINES = [
    " ██████╗ ██████╗ ███████╗ ██████╗██╗   ██╗██████╗  █████╗ ",
    "██╔═══██╗██╔══██╗██╔════╝██╔════╝██║   ██║██╔══██╗██╔══██╗",
    "██║   ██║██████╔╝███████╗██║     ██║   ██║██████╔╝███████║",
    "██║   ██║██╔══██╗╚════██║██║     ██║   ██║██╔══██╗██╔══██║",
    "╚██████╔╝██████╔╝███████║╚██████╗╚██████╔╝██║  ██║██║  ██║",
    " ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝",
    "",
    "      ██╗  ██╗████████╗███╗   ███╗██╗                     ",
    "      ██║  ██║╚══██╔══╝████╗ ████║██║                     ",
    "      ███████║   ██║   ██╔████╔██║██║                     ",
    "      ██╔══██║   ██║   ██║╚██╔╝██║██║                     ",
    "      ██║  ██║   ██║   ██║ ╚═╝ ██║███████╗                ",
    "      ╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚═╝╚══════╝                ",
]

def display_banner():
    console.clear()
    console.print()
    for line in BANNER_LINES:
        console.print(Align.center(Text(line, style="bold bright_green")))
    console.print()
    console.print(Rule(style="green"))
    info_line = Text(justify="center")
    info_line.append("  🔐 HTML Obfuscation  ", style="bold bright_green")
    info_line.append("│", style="dim green")
    info_line.append(f"  v{VERSION}  ", style="bold cyan")
    info_line.append("│", style="dim green")
    info_line.append(f"  by {AUTHOR}  ", style="bold yellow")
    info_line.append("│", style="dim green")
    info_line.append("  github.com/Forhadj/ObscuraHTML  ", style="dim cyan")
    console.print(Align.center(info_line))
    console.print(Rule(style="green"))
    console.print(Align.center(Text(
        "⚠  Stops casual copiers — skilled devs with DevTools can still read it.",
        style="dim yellow"
    )))
    console.print()


def display_stats(html_files):
    total = sum(f.stat().st_size for f in html_files)
    log   = load_log()
    cells = [
        Panel(
            Align.center(Text(f"{len(html_files)}\n", style="bold bright_green")
                         + Text("HTML Files", style="dim")),
            box=box.ROUNDED, border_style=T_BORDER_P, padding=(1, 3)
        ),
        Panel(
            Align.center(Text(f"{fmt_size(total)}\n", style="bold cyan")
                         + Text("Total Size", style="dim")),
            box=box.ROUNDED, border_style=T_BORDER_A, padding=(1, 3)
        ),
        Panel(
            Align.center(Text(f"{len(log)}\n", style="bold yellow")
                         + Text("Protected", style="dim")),
            box=box.ROUNDED, border_style=T_BORDER_W, padding=(1, 3)
        ),
        Panel(
            Align.center(Text(f"{AUTHOR}\n", style="bold bright_green")
                         + Text("Author", style="dim")),
            box=box.ROUNDED, border_style=T_BORDER_P, padding=(1, 3)
        ),
    ]
    console.print(Columns(cells, equal=True))
    console.print()


def display_files_table(html_files) -> bool:
    if not html_files:
        console.print(Panel(
            "[bright_red]⚠  No HTML files found in current directory.[/bright_red]\n"
            "[dim]Use option [2] to enter a custom file path instead.[/dim]",
            box=box.HEAVY, border_style="red"
        ))
        return False
    t = Table(
        title=f"[bold bright_green]📄 ObscuraHTML — File Queue[/bold bright_green]",
        box=box.HEAVY_EDGE, border_style="green", show_lines=True
    )
    t.add_column("#",        style="bold bright_green", width=4,  justify="center")
    t.add_column("Filename", style="bold cyan",          min_width=28)
    t.add_column("Size",     style="yellow",             width=10, justify="right")
    t.add_column("Modified", style="dim white",          width=20)
    t.add_column("Status",   width=16,                   justify="center")
    for i, f in enumerate(html_files, 1):
        s   = f.stat()
        mod = datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M")
        exists = Path(OUTPUT_PREFIX + f.stem + ".html").exists()
        status = "[yellow]↻ Re-protect[/yellow]" if exists else "[bright_green]✓ Ready[/bright_green]"
        t.add_row(str(i), f.name, fmt_size(s.st_size), mod, status)
    console.print(t)
    console.print()
    return True


def display_level_menu() -> int:
    console.print(Rule("[bold cyan]🛡  Protection Level[/bold cyan]", style="cyan"))
    panels = [
        Panel(
            "[bold cyan]LEVEL 1 — FAST[/bold cyan]\n\n"
            "[green]✓[/green] Safe HTML minify\n"
            "[green]✓[/green] deflate compress\n"
            "[green]✓[/green] SHA-256 integrity\n"
            "[green]✓[/green] Chunked base64\n"
            "[green]✓[/green] Safe DOMParser\n"
            "[green]✓[/green] pako fallback\n\n"
            "[dim]⚡ No encryption\n  Fastest output[/dim]",
            box=box.ROUNDED, border_style="cyan", padding=(1, 2)
        ),
        Panel(
            "[bold yellow]LEVEL 2 — BALANCED ★[/bold yellow]\n\n"
            "[green]✓[/green] All of Level 1\n"
            "[green]✓[/green] AES-256-GCM *\n"
            "[green]✓[/green] XOR fallback\n"
            "[green]✓[/green] 9 decoy vars\n"
            "[green]✓[/green] Polymorphic loader\n\n"
            "[dim]* Key in JS = obfuscation\n  Best balance[/dim]",
            box=box.ROUNDED, border_style="yellow", padding=(1, 2)
        ),
        Panel(
            "[bold bright_red]LEVEL 3 — MAX 🔥[/bold bright_red]\n\n"
            "[green]✓[/green] All of Level 2\n"
            "[green]✓[/green] Blob URL loader\n"
            "[green]✓[/green] No eval() used\n"
            "[green]✓[/green] Anti-debug trap\n"
            "[green]✓[/green] DevTools overlay\n"
            "[green]✓[/green] 14 decoy vars\n\n"
            "[dim]🔒 Hardest to reverse[/dim]",
            box=box.ROUNDED, border_style="red", padding=(1, 2)
        ),
    ]
    console.print(Columns(panels, equal=True))
    console.print()
    return IntPrompt.ask(
        "[bold cyan]Select Level[/bold cyan]",
        choices=["1", "2", "3"], show_choices=True
    )


def protect_file(src: Path, level: int, out_dir: Path | None = None) -> tuple[str | None, dict | None]:
    """Core protect logic — used by both single and batch flows."""
    try:
        html_text = src.read_text(encoding="utf-8")
        prot, info = protect_html(html_text, level)

        if out_dir:
            out_path = out_dir / (OUTPUT_PREFIX + src.stem + ".html")
        else:
            out_path = src.parent / (OUTPUT_PREFIX + src.stem + ".html")

        out_path.write_text(prot, encoding="utf-8")
        append_log(src, out_path, info, src.stat().st_size, out_path.stat().st_size)
        return str(out_path), info
    except Exception as e:
        console.print(f"[bright_red]❌ Error: {e}[/bright_red]")
        return None, None


def display_result(src: Path, out_name: str, info: dict):
    orig  = src.stat().st_size
    prot  = Path(out_name).stat().st_size
    ratio = (1 - prot / orig) * 100 if orig else 0

    t = Table(
        title=f"[bold bright_green]✅ ObscuraHTML v{VERSION} — Result[/bold bright_green]",
        box=box.DOUBLE_EDGE, border_style="green", show_lines=True
    )
    t.add_column("Property", style="bold cyan",   width=22)
    t.add_column("Value",    style="bold yellow", min_width=44)
    t.add_row("🔒 Level",     f"{info['level']} / 3")
    t.add_row("🗜  Compress",  info["compress"])
    t.add_row("🔐 Encrypt",   info["encrypt"]
              + (" [dim](key embedded → obfuscation)[/dim]" if info["level"] >= 2 else ""))
    t.add_row("🛡  Integrity", f"SHA-256 [{info['comp_hash']}]")
    t.add_row("📄 Source",    str(src))
    t.add_row("💾 Output",    f"[bright_green]{out_name}[/bright_green]")
    t.add_row("📏 Orig Size", fmt_size(orig))
    t.add_row("🔐 Prot Size", fmt_size(prot))
    if ratio > 0:
        t.add_row("📉 Saved", f"[green]{fmt_size(orig-prot)} ({ratio:.1f}%)[/green]")
    else:
        t.add_row("📈 Overhead", f"[yellow]+{fmt_size(prot-orig)}[/yellow]")
    t.add_row("🕒 Time",      datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    console.print(t)
    console.print()
    console.print(Panel(
        f"[bold bright_green]🎉 Protection complete![/bold bright_green]\n\n"
        f"[cyan]Output →[/cyan] [yellow]{Path(out_name).absolute()}[/yellow]",
        box=box.HEAVY, border_style="green", padding=(1, 3)
    ))


def display_history():
    log = load_log()
    if not log:
        console.print(Panel("[dim]No protection history yet.[/dim]", border_style="dim"))
        return
    t = Table(
        title=f"[bold cyan]📜 ObscuraHTML — History (last 20)[/bold cyan]",
        box=box.SIMPLE_HEAVY, border_style="cyan", show_lines=True
    )
    t.add_column("#",        style="dim",    width=4,  justify="right")
    t.add_column("Time",     style="cyan",   width=19)
    t.add_column("Source",   style="green",  min_width=20)
    t.add_column("Output",   style="yellow", min_width=24)
    t.add_column("Lvl",      width=5,        justify="center")
    t.add_column("Encrypt",  width=14)
    t.add_column("Ratio",    width=7,        justify="right")
    for i, e in enumerate(reversed(log[-20:]), 1):
        t.add_row(
            str(i),
            e.get("timestamp", "")[:19],
            Path(e.get("original", "")).name,
            Path(e.get("output", "")).name,
            str(e.get("level", "?")),
            e.get("encrypt", "—"),
            f"{e.get('ratio_pct', 0):.1f}%",
        )
    console.print(t)
    console.print()


def batch_protect_folder(html_files: list[Path], level: int):
    console.print(Rule(
        f"[bold yellow]⚡ Batch — {len(html_files)} files — Level {level}[/bold yellow]"
    ))
    results = []
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="green"),
        TaskProgressColumn(),
        console=console
    ) as prog:
        task = prog.add_task("[cyan]Batch protecting…", total=len(html_files))
        for f in html_files:
            prog.update(task, description=f"[cyan]🔒 {f.name}")
            out, inf = protect_file(f, level)
            if out:
                results.append((f.name, out, "[green]✅[/green]"))
            else:
                results.append((f.name, "—", "[red]❌ failed[/red]"))
            prog.advance(task)
            sleep(0.04)
    console.print()
    s = Table(
        title="[bold green]📦 Batch Summary[/bold green]",
        box=box.ROUNDED, border_style="green"
    )
    s.add_column("Source",  style="cyan")
    s.add_column("Output",  style="yellow")
    s.add_column("Status",  justify="center")
    for o, u, st in results:
        s.add_row(o, u, st)
    console.print(s)


# ═══════════════════════════════════════════════════════════════
#  INPUT MODE MENU
# ═══════════════════════════════════════════════════════════════

def input_mode_menu() -> str:
    """
    Returns '1' (folder scan), '2' (manual path), '3' (history),
            '4' (batch), '5' (exit).
    """
    console.print(Rule("[bold bright_green]◈  ObscuraHTML — Main Menu[/bold bright_green]",
                        style="green"))
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    t.add_column("Key",    style="bold bright_green", width=5)
    t.add_column("Action", style="white")
    t.add_row("[1]", "Protect — scan current folder  [dim](auto-detect .html files)[/dim]")
    t.add_row("[2]", "Protect — enter file path      [dim](e.g. /storage/emulated/0/index.html)[/dim]")
    t.add_row("[3]", "Protect — enter folder path    [dim](e.g. /sdcard/mysite)[/dim]")
    t.add_row("[4]", "View protection history")
    t.add_row("[5]", "Exit")
    console.print(t)
    console.print()
    return Prompt.ask(
        "[bold bright_green]obscura ›[/bold bright_green]",
        choices=["1", "2", "3", "4", "5"], default="1"
    )


# ═══════════════════════════════════════════════════════════════
#  SINGLE FILE FLOW (from folder list)
# ═══════════════════════════════════════════════════════════════

def flow_single_from_folder(html_files):
    if not display_files_table(html_files):
        return
    while True:
        try:
            num = IntPrompt.ask(
                f"\n[bold cyan]📌 File number (1–{len(html_files)})[/bold cyan]",
                choices=[str(i) for i in range(1, len(html_files) + 1)],
                show_choices=False,
            )
            selected = html_files[num - 1]
            break
        except KeyboardInterrupt:
            console.print(f"\n[yellow]Cancelled.[/yellow]")
            return

    console.print(Panel(
        f"[bold yellow]Selected →[/bold yellow] [cyan]{selected}[/cyan]  "
        f"[dim]({fmt_size(selected.stat().st_size)})[/dim]",
        box=box.ROUNDED, border_style="blue"
    ))
    level = display_level_menu()
    if not Confirm.ask(
        f"\n[bold yellow]⚡ Protect [cyan]{selected.name}[/cyan] at Level {level}?[/bold yellow]",
        default=True
    ):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    with console.status("[cyan]Processing…[/cyan]", spinner="dots"):
        out, info = protect_file(selected, level)

    if out and info:
        console.print()
        display_result(selected, out, info)


# ═══════════════════════════════════════════════════════════════
#  DIRECT PATH FLOW
# ═══════════════════════════════════════════════════════════════

def flow_direct_path():
    console.print(Rule("[bold cyan]📂 Direct File Path[/bold cyan]", style="cyan"))
    console.print(
        "[dim]Enter the full path to your HTML file.\n"
        "Examples:\n"
        "  • /storage/emulated/0/index.html\n"
        "  • /sdcard/mysite/page.html\n"
        "  • ~/projects/site/index.html\n"
        "  • ./index.html[/dim]\n"
    )
    raw = Prompt.ask("[bold bright_green]obscura › path[/bold bright_green]").strip()
    if not raw:
        console.print("[yellow]No path entered.[/yellow]")
        return

    p = resolve_input_path(raw)
    if p is None:
        console.print(
            f"[bright_red]❌ File not found or not an HTML file:[/bright_red] [yellow]{raw}[/yellow]"
        )
        return

    console.print(Panel(
        f"[bold yellow]Found →[/bold yellow] [cyan]{p}[/cyan]  [dim]({fmt_size(p.stat().st_size)})[/dim]",
        box=box.ROUNDED, border_style="blue"
    ))
    level = display_level_menu()
    if not Confirm.ask(
        f"\n[bold yellow]⚡ Protect [cyan]{p.name}[/cyan] at Level {level}?[/bold yellow]",
        default=True
    ):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    with console.status("[cyan]Processing…[/cyan]", spinner="dots"):
        out, info = protect_file(p, level)

    if out and info:
        console.print()
        display_result(p, out, info)


# ═══════════════════════════════════════════════════════════════
#  FOLDER PATH FLOW  (batch a custom folder)
# ═══════════════════════════════════════════════════════════════

def flow_folder_path():
    console.print(Rule("[bold cyan]📁 Custom Folder Path[/bold cyan]", style="cyan"))
    console.print(
        "[dim]Enter the folder path to scan for HTML files.\n"
        "Examples:\n"
        "  • /storage/emulated/0/mysite\n"
        "  • /sdcard/projects/blog\n"
        "  • ~/websites[/dim]\n"
    )
    raw = Prompt.ask("[bold bright_green]obscura › folder[/bold bright_green]").strip()
    if not raw:
        console.print("[yellow]No path entered.[/yellow]")
        return

    folder = Path(raw.strip()).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        console.print(
            f"[bright_red]❌ Directory not found:[/bright_red] [yellow]{raw}[/yellow]"
        )
        return

    html_files = discover_files(folder)
    if not html_files:
        console.print(
            f"[yellow]No unprotected HTML files found in:[/yellow] [cyan]{folder}[/cyan]"
        )
        return

    console.print(f"\n[bright_green]Found {len(html_files)} file(s) in[/bright_green] [cyan]{folder}[/cyan]")
    for i, f in enumerate(html_files, 1):
        console.print(f"  [dim]{i}.[/dim] {f.name}  [dim]({fmt_size(f.stat().st_size)})[/dim]")
    console.print()

    mode = Prompt.ask(
        "[bold cyan]Protect all at once (batch) or pick one?[/bold cyan]",
        choices=["batch", "pick"], default="batch"
    )

    level = display_level_menu()

    if mode == "batch":
        if Confirm.ask(
            f"[bold yellow]Protect all {len(html_files)} files at Level {level}?[/bold yellow]"
        ):
            batch_protect_folder(html_files, level)
    else:
        if not display_files_table(html_files):
            return
        num = IntPrompt.ask(
            f"[bold cyan]File number (1–{len(html_files)})[/bold cyan]",
            choices=[str(i) for i in range(1, len(html_files) + 1)],
            show_choices=False,
        )
        selected = html_files[num - 1]
        with console.status("[cyan]Processing…[/cyan]", spinner="dots"):
            out, info = protect_file(selected, level)
        if out and info:
            console.print()
            display_result(selected, out, info)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    display_banner()
    html_files = discover_files(Path("."))
    display_stats(html_files)

    choice = input_mode_menu()

    if choice == "1":
        # Scan current folder
        if not html_files:
            console.print(Panel(
                "[yellow]⚠  No HTML files in current directory.\n"
                "[dim]Use option [2] to specify a file path directly.[/dim][/yellow]",
                box=box.ROUNDED, border_style="yellow"
            ))
        elif len(html_files) == 1:
            flow_single_from_folder(html_files)
        else:
            sub = Prompt.ask(
                "[bold cyan]single or batch?[/bold cyan]",
                choices=["single", "batch"], default="single"
            )
            if sub == "single":
                flow_single_from_folder(html_files)
            else:
                level = display_level_menu()
                if Confirm.ask(f"[yellow]Protect all {len(html_files)} files at Level {level}?[/yellow]"):
                    batch_protect_folder(html_files, level)

    elif choice == "2":
        flow_direct_path()

    elif choice == "3":
        flow_folder_path()

    elif choice == "4":
        display_history()
        Prompt.ask("[dim]Press Enter to return[/dim]", default="")
        return main()

    else:
        console.print(Panel(
            f"[bold bright_green]👋 Thanks for using ObscuraHTML v{VERSION}![/bold bright_green]\n"
            f"[dim cyan]Stops casual copiers. Stay honest. — {AUTHOR} 🔒[/dim cyan]",
            box=box.DOUBLE_EDGE, border_style="green"
        ))
        return

    console.print()
    if Confirm.ask("[bold bright_green]🔄 Protect another file?[/bold bright_green]", default=False):
        console.print("\n")
        main()
    else:
        console.print(Panel(
            f"[bold bright_green]✅ Done — ObscuraHTML v{VERSION} by {AUTHOR}[/bold bright_green]\n"
            f"[dim]github.com/Forhadj/ObscuraHTML[/dim]",
            box=box.DOUBLE_EDGE, border_style="green"
        ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(f"\n[yellow]👋 Interrupted — Goodbye![/yellow]")
    except Exception as e:
        console.print(f"\n[bright_red]❌ Fatal error: {e}[/bright_red]")
        raise
