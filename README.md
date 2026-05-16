# ObscuraHTML

> HTML Obfuscation Tool — by **Forhad**

Protect your HTML files from casual copying, scraping, and source inspection.

> ⚠️ **Honest disclaimer:** All decryption runs in the browser, so the key is always accessible to a skilled developer via DevTools. This tool stops **casual copiers, scrapers, and beginners** — not determined reverse engineers.

---

## Features

- **Two input modes** — scan a folder automatically, or enter any file path directly (`/storage/emulated/0/index.html`, `~/Downloads/page.html`, etc.)
- **3 protection levels** — Basic / Standard (AES-256-GCM) / Maximum (anti-debug + DevTools overlay)
- **Batch mode** — protect all `.html` files in a folder at once
- Safe HTML minification (skips `<script>`, `<style>`, `<pre>`, `<textarea>`)
- SHA-256 integrity check on compressed bytes
- Chunked + randomised base64 encoding
- pako.js fallback for older browsers without `DecompressionStream`
- Safe DOM injection via `DOMParser` — no `document.write()`
- Blob URL loader at Level 3 — no `eval()`, no `new Function()`
- Protection history log (`~/.obscura_log.json`)

---

## Requirements

- Python **3.10+**
- Packages listed in `requirements.txt`

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/Forhadj/ObscuraHTML.git
cd ObscuraHTML

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

### Install as a command (optional)

```bash
pip install -e .
# then run from anywhere:
obscura
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `rich` | Terminal UI (tables, panels, progress bars) |
| `pycryptodome` | AES-256-GCM encryption (Level 2 & 3) |

If `pycryptodome` is not installed, the tool automatically falls back to **XOR-SHA256 stream** encryption — everything still works.

---

## Usage

```
python main.py
```

### Main menu

```
[1]  Protect a file
[2]  Batch protect all files in folder
[3]  View history
[4]  Exit
```

### Input methods

When choosing option `[1]`, you will see:

```
① Scan Folder   — auto-detect all .html files in current directory
② Enter Path    — type the full path to any .html file
```

**Path examples that work:**

```
/storage/emulated/0/index.html
/sdcard/mysite/page.html
~/Desktop/index.html
./subfolder/index.html
../other/page.html
```

### Protection levels

| Level | Encryption | Anti-debug | Best for |
|---|---|---|---|
| 1 — Basic | None | No | Fast output, small file |
| 2 — Standard | AES-256-GCM | No | Recommended default |
| 3 — Maximum | AES-256-GCM | Yes (DevTools overlay + debugger trap) | Hardest to reverse |

---

## Output

Protected files are saved in the **same folder** as the original, with the prefix `obscura_`:

```
index.html  →  obscura_index.html
```

---

## Project Structure

```
ObscuraHTML/
├── main.py               # Entry point
├── requirements.txt      # Dependencies
├── setup.py              # Optional pip install
└── obscura/
    ├── __init__.py
    ├── engine.py         # Protection engine (minify, compress, encrypt, build loader)
    └── cli.py            # Terminal UI
```

---

## Security Levels — Technical Details

### Level 1 — Basic
- HTML minified → zlib/deflate compressed → base64 encoded (random chunk sizes)
- SHA-256 integrity check on compressed bytes
- Decoded in browser via `DecompressionStream` or `pako.js`
- DOM replaced safely via `DOMParser`

### Level 2 — Standard
- All of Level 1, plus:
- Compressed bytes encrypted with **AES-256-GCM** (WebCrypto API)
- Falls back to XOR-SHA256 if WebCrypto unavailable
- 9 random decoy JavaScript variables

### Level 3 — Maximum
- All of Level 2, plus:
- Inner loader wrapped as a **Blob URL** and executed via `import()` — no `eval()`, no `new Function()`
- `setInterval(debugger)` trap every 120ms
- DevTools size-detection overlay
- 14 random decoy variables

---

## Android / Termux

Works on Android via Termux:

```bash
pkg install python
pip install rich pycryptodome
git clone https://github.com/Forhadj/ObscuraHTML.git
cd ObscuraHTML
python main.py
```

To protect a file on internal storage:

```
② Enter Path → /storage/emulated/0/index.html
```

---

## Author

**Forhad** — [github.com/Forhadj](https://github.com/Forhadj)

---

## License

MIT License — free to use, modify, and distribute.
