#!/usr/bin/env python3
"""Add a card to Anki via the AnkiConnect add-on.

Reads a JSON job from stdin:
  {
    "deck": "英語",
    "image": "/absolute/path/to/screenshot.png",
    "back_html": "<div>...</div>",
    "front_html": "<img src=\"{{IMAGE}}\">",   # optional, {{IMAGE}} is substituted
    "tags": ["screenshot", "subtitle"],         # optional
    "model": "Basic",                             # optional, default Basic
    "english_text": "Sleep deprivation can ...", # optional; if set, TTS audio is
                                                  # generated with macOS `say` and
                                                  # embedded as [sound:...] in the
                                                  # front (auto-plays on show).
    "voice": "Daniel"                             # optional, default Daniel (en_GB)
  }

Prints a single JSON line on stdout:
  {"ok": true, "note_id": 123, "media": "anki-shot-...png", "audio": "anki-...m4a", "deck": "英語"}
On failure prints {"ok": false, "error": "...", "detail": "..."} and exits 1.
"""
import sys
import os
import json
import re
import time
import base64
import hashlib
import subprocess
import tempfile
import urllib.parse
import urllib.request
import urllib.error

ANKI_URL = "http://127.0.0.1:8765"
COUNTER_PATH = os.path.join(
    os.path.expanduser("~"),
    ".claude/skills/anki-add-from-screenshot/.card_count",
)
SYNC_EVERY = 10
DDG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://duckduckgo.com/",
}


def ddg_image(query, timeout=15, max_bytes=2_500_000):
    """Search DuckDuckGo Images and return (bytes, ext) of the first usable result.
    Returns None on any failure (image enrichment is best-effort)."""
    try:
        # Step 1: fetch vqd token
        token_url = (
            "https://duckduckgo.com/?q=" + urllib.parse.quote(query) + "&iar=images&iax=images&ia=images"
        )
        req = urllib.request.Request(token_url, headers=DDG_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")
        m = re.search(r"vqd=[\"']?([\d-]+)[\"']?", html)
        if not m:
            return None
        vqd = m.group(1)

        # Step 2: query JSON image endpoint
        params = {
            "l": "us-en",
            "o": "json",
            "q": query,
            "vqd": vqd,
            "f": ",,,",
            "p": "1",
        }
        api_url = "https://duckduckgo.com/i.js?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(api_url, headers=DDG_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        results = data.get("results") or []

        # Step 3: try first few candidates; return first that downloads cleanly
        for result in results[:6]:
            img_url = result.get("image") or result.get("thumbnail")
            if not img_url:
                continue
            try:
                ireq = urllib.request.Request(img_url, headers=DDG_HEADERS)
                with urllib.request.urlopen(ireq, timeout=timeout) as ir:
                    content = ir.read(max_bytes)
                    ctype = (ir.headers.get("Content-Type") or "").lower()
                if not content:
                    continue
                if "png" in ctype:
                    ext = ".png"
                elif "webp" in ctype:
                    ext = ".webp"
                elif "gif" in ctype:
                    ext = ".gif"
                else:
                    ext = ".jpg"
                return content, ext
            except Exception:
                continue
    except Exception:
        return None
    return None


def fail(error, detail=""):
    print(json.dumps({"ok": False, "error": error, "detail": str(detail)}))
    sys.exit(1)


def invoke(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(
        ANKI_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        fail("anki_connect_unreachable", e)
    except json.JSONDecodeError as e:
        fail("anki_connect_bad_response", e)
    if body.get("error"):
        fail("anki_connect_error", body["error"])
    return body.get("result")


def main():
    try:
        job = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        fail("invalid_input_json", e)

    deck = job.get("deck") or "英語"
    image_path = job.get("image")
    back_html = job.get("back_html")
    front_html = job.get("front_html")
    tags = job.get("tags") or ["screenshot"]
    model = job.get("model")
    english_text = (job.get("english_text") or "").strip()
    source_text = (job.get("source_text") or "").strip()
    voice = job.get("voice") or "Daniel"
    vocab_images = job.get("vocab_images") or {}  # {slug: search_query}

    if image_path and not os.path.isfile(image_path):
        fail("image_not_found", image_path)
    if not back_html:
        fail("missing_back_html", "back_html is required")
    if not image_path and not front_html and not english_text:
        fail(
            "missing_front_content",
            "Need at least one of: image, front_html, english_text",
        )

    # Reachability + version handshake
    invoke("version")

    # Ensure deck exists
    decks = invoke("deckNames") or []
    if deck not in decks:
        invoke("createDeck", deck=deck)

    # Resolve model: explicit > "Basic" > "基本" > first available
    models = invoke("modelNames") or []
    if not models:
        fail("no_models", "Anki has no note types")
    if model is None:
        for candidate in ("Basic", "基本"):
            if candidate in models:
                model = candidate
                break
        else:
            model = models[0]
    elif model not in models:
        fail(
            "model_missing",
            f"Note type '{model}' not found in Anki. Available: {models}",
        )

    # Resolve field names: use first field as front, second as back
    field_names = invoke("modelFieldNames", modelName=model) or []
    if len(field_names) < 2:
        fail(
            "model_unsupported",
            f"Note type '{model}' needs at least 2 fields, got: {field_names}",
        )
    front_field, back_field = field_names[0], field_names[1]

    # Store image as media (if provided)
    stored = None
    if image_path:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        ext = os.path.splitext(image_path)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            ext = ".png"
        digest = hashlib.sha1(img_bytes).hexdigest()[:12]
        filename = f"anki-shot-{int(time.time())}-{digest}{ext}"
        b64 = base64.b64encode(img_bytes).decode()
        stored = invoke("storeMediaFile", filename=filename, data=b64) or filename

    if front_html:
        front_final = front_html.replace("{{IMAGE}}", stored or "")
    elif stored:
        front_final = f'<img src="{stored}">'
    else:
        # Sentence-only card: use english_text as front, styled
        front_final = (
            "<div style=\"font-family: 'Georgia', 'Helvetica Neue', serif; "
            "font-size: 1.3em; line-height:1.6; text-align:center; "
            "padding: 24px 16px; color:#222;\">"
            f"&ldquo;{english_text}&rdquo;"
            "</div>"
        )

    def synthesize_audio(text):
        """macOS `say` -> aiff -> m4a -> store in Anki media. Returns filename."""
        with tempfile.TemporaryDirectory() as td:
            aiff = os.path.join(td, "tts.aiff")
            m4a = os.path.join(td, "tts.m4a")
            try:
                subprocess.run(
                    ["say", "-v", voice, "-o", aiff, text],
                    check=True, capture_output=True, timeout=30,
                )
                subprocess.run(
                    ["afconvert", aiff, m4a, "-d", "aac", "-f", "m4af"],
                    check=True, capture_output=True, timeout=30,
                )
                with open(m4a, "rb") as af:
                    audio_bytes = af.read()
            except subprocess.CalledProcessError as e:
                fail("tts_failed", e.stderr.decode(errors="replace") if e.stderr else str(e))
            except FileNotFoundError as e:
                fail("tts_tool_missing", e)
            adigest = hashlib.sha1(audio_bytes).hexdigest()[:12]
            fname = f"anki-tts-{int(time.time())}-{adigest}.m4a"
            invoke(
                "storeMediaFile",
                filename=fname,
                data=base64.b64encode(audio_bytes).decode(),
            )
            return fname

    # Front audio (english_text)
    audio_filename = None
    if english_text:
        audio_filename = synthesize_audio(english_text)
        front_final = f"[sound:{audio_filename}]" + front_final

    # Source-sentence audio (source_text) -> substitute {{SOURCE_AUDIO}} in back
    source_audio_filename = None
    if source_text:
        source_audio_filename = synthesize_audio(source_text)
        back_html = back_html.replace(
            "{{SOURCE_AUDIO}}", f"[sound:{source_audio_filename}]"
        )
    else:
        back_html = back_html.replace("{{SOURCE_AUDIO}}", "")

    # Vocab images: fetch via DuckDuckGo, store as media, substitute {{IMG:slug}}
    vocab_image_filenames = {}
    for slug, query in (vocab_images or {}).items():
        if not query:
            continue
        result = ddg_image(query)
        if not result:
            # Substitute placeholder with empty string so card still renders cleanly
            back_html = back_html.replace(f"{{{{IMG:{slug}}}}}", "")
            continue
        img_bytes, ext = result
        d = hashlib.sha1(img_bytes).hexdigest()[:12]
        fname = f"anki-vocab-{slug}-{d}{ext}"
        # Sanitize filename — Anki requires basic ASCII for media
        fname = re.sub(r"[^A-Za-z0-9._-]", "_", fname)
        invoke(
            "storeMediaFile",
            filename=fname,
            data=base64.b64encode(img_bytes).decode(),
        )
        vocab_image_filenames[slug] = fname
        img_tag = (
            f'<img src="{fname}" style="display:block; max-width:200px; '
            'max-height:140px; margin:6px 0; border-radius:6px;">'
        )
        back_html = back_html.replace(f"{{{{IMG:{slug}}}}}", img_tag)

    note = {
        "deckName": deck,
        "modelName": model,
        "fields": {front_field: front_final, back_field: back_html},
        "options": {"allowDuplicate": True},
        "tags": tags,
    }
    note_id = invoke("addNote", note=note)

    # Increment per-skill counter and auto-sync every SYNC_EVERY cards.
    synced = False
    try:
        try:
            with open(COUNTER_PATH, "r") as f:
                count = int(f.read().strip() or "0")
        except (FileNotFoundError, ValueError):
            count = 0
        count += 1
        with open(COUNTER_PATH, "w") as f:
            f.write(str(count))
        if count % SYNC_EVERY == 0:
            # Direct call instead of invoke() — sync failures must NOT abort
            # the script (the card has already been added successfully).
            try:
                sync_payload = json.dumps(
                    {"action": "sync", "version": 6, "params": {}}
                ).encode()
                sync_req = urllib.request.Request(
                    ANKI_URL,
                    data=sync_payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(sync_req, timeout=60) as r:
                    sync_body = json.loads(r.read())
                synced = sync_body.get("error") is None
            except (urllib.error.URLError, ConnectionError, TimeoutError,
                    json.JSONDecodeError, OSError):
                synced = False
    except OSError:
        pass

    print(
        json.dumps(
            {
                "ok": True,
                "note_id": note_id,
                "media": stored,
                "audio": audio_filename,
                "source_audio": source_audio_filename,
                "vocab_images": vocab_image_filenames,
                "deck": deck,
                "synced": synced,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
