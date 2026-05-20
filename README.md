# claude-anki-skill

A [Claude Code](https://github.com/anthropics/claude-code) skill that turns subtitle screenshots into IELTS-focused Anki cards — fully automated.

Paste a screenshot of an English subtitle (YouTube, TED-Ed, Netflix, a TED talk, etc.) into Claude Code, and you get one Anki card per unknown word / idiom / grammar pattern, each with:

- **Front**: the target item + British English audio (macOS `say -v Daniel`)
- **Back**:
  - Japanese translation
  - Illustration image (DuckDuckGo image search)
  - Short IELTS-usage note
  - Original source sentence + audio for listening practice

Cards land in your `英語` deck via [AnkiConnect](https://ankiweb.net/shared/info/2055492159) and auto-sync to AnkiWeb every 10 additions, so your phone (AnkiMobile / AnkiDroid) stays current with zero manual work.

## Features

- **IELTS relevance filter** — skips items that won't help your IELTS score (e.g., specialised medical anatomy, casual slang) and gives a one-line reason
- **One item = one card** — atomic SRS units: each vocab / phrasal verb / idiom / grammar pattern gets its own card and its own forgetting curve
- **British English TTS** — uses macOS `say -v Daniel` (no API key, no cost) to embed `.m4a` audio in every card so pronunciation drilling works on every device
- **Vocab illustrations** — fetches a relevant image per item from DuckDuckGo and embeds it in the back so meaning sticks faster
- **Auto-sync to AnkiWeb** — every 10 cards a `sync` action fires so phone/desktop stay aligned without thinking about it

## Prerequisites

- macOS (uses built-in `say` and `afconvert` for TTS — Linux/Windows users would need to swap these out)
- Python 3.8+
- [Anki](https://apps.ankiweb.net/) desktop app
- [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on (code `2055492159`)
- Claude Code

## Setup

1. **Install Anki and AnkiConnect**:
   - Launch Anki, then `Tools → Add-ons → Get Add-ons...`
   - Enter code `2055492159`, click OK
   - Restart Anki
   - Verify with `curl -sS -X POST http://127.0.0.1:8765 -d '{"action":"version","version":6}' -H 'Content-Type: application/json'` — should return `{"result": 6, "error": null}`

2. **Install this skill into Claude Code**:
   ```bash
   git clone https://github.com/koyochan/claude-anki-skill.git ~/claude-anki-skill
   mkdir -p ~/.claude/skills/anki-add-from-screenshot
   ln -s ~/claude-anki-skill/SKILL.md ~/.claude/skills/anki-add-from-screenshot/SKILL.md
   ln -s ~/claude-anki-skill/add_card.py ~/.claude/skills/anki-add-from-screenshot/add_card.py
   ```
   (Or copy the files instead of symlinking if you prefer.)

3. **(Optional) Sign in to AnkiWeb** in Anki desktop so cards sync to your phone:
   - https://ankiweb.net/account/signup
   - In Anki: `Preferences → Network → AnkiWeb` and log in

## Usage

In Claude Code, in any directory:

1. Paste a screenshot of an English subtitle into the chat.
2. Claude analyses the image, picks IELTS-worthy items, and adds one card per item.
3. After every 10 cards, the deck auto-syncs to AnkiWeb.
4. Open Anki on your phone, tap Sync — cards arrive.

You can also explicitly ask Claude:
- "What does X mean?" — get a quick explanation without carding
- "Skip this one" — process the screenshot but don't add a card
- "Make a card for X only" — narrow the picks

## Configuration

Edit `add_card.py`:

- `SYNC_EVERY` — change auto-sync interval (default `10`)
- `ANKI_URL` — point at a different AnkiConnect endpoint
- Voice — change the default by passing `"voice": "Samantha"` in the JSON job, or edit the `voice` fallback in `add_card.py`

To use a different deck name (default `英語`), pass `"deck": "<your-deck>"` in the JSON job.

## Card JSON job schema

The script reads a JSON job from stdin. Minimum:

```json
{
  "deck": "英語",
  "english_text": "regurgitate",
  "source_text": "So your sleepless brain might be able to regurgitate facts.",
  "vocab_images": {"term": "parrot repeating mimicking"},
  "front_html": "<div style='...'>regurgitate</div>",
  "back_html": "<div>...{{IMG:term}}...{{SOURCE_AUDIO}}...</div>",
  "tags": ["item-based", "ielts", "vocab"]
}
```

Placeholders `{{IMG:slug}}` and `{{SOURCE_AUDIO}}` get substituted by the script.

See `SKILL.md` for the full Claude-facing skill spec.

## License

MIT — see `LICENSE`.
