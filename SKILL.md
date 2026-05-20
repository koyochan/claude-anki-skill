---
name: anki-add-from-screenshot
description: "Turn a pasted screenshot (YouTube/TED-Ed/drama subtitle frame) into an IELTS-focused Anki card. Front = the screenshot image only, Back = Japanese translation + a 1-line vocabulary gloss for unknown/IELTS-relevant words. Filters out screenshots with no IELTS value (everyday chitchat with no notable vocab). Pushes into `英語` deck via AnkiConnect. AUTOMATIC ACTIVATION: whenever the user pastes a screenshot/image in this directory (`/Users/kota/Documents/anki`) OR mentions Anki/字幕/デッキ/英語デッキ/IELTS/スクショ学習/英語学習 alongside an image. Triggers on phrases like `Ankiに入れて`, `デッキに追加`, `これカード化`, `字幕を訳して`, or simply pasting a subtitle screenshot."
license: MIT
metadata:
  author: kota + Claude
  version: "1.0"
  created: 2026-05-20
---

# anki-add-from-screenshot

ペーストされた字幕スクショを **英語** デッキに 1 枚のカードとして自動投入する。
- 表面: 画像のみ（テキストは載せない）
- 裏面: `【日本語訳】` + `【解説】`（語彙・文法・スラング・背景）
- 経由: AnkiConnect (`http://127.0.0.1:8765`)

## When to invoke

- 当ディレクトリ (`/Users/kota/Documents/anki`) で画像（スクショ）がペーストされた
- 字幕/英語/Anki/デッキ/カード化 などの語と一緒に画像が渡された
- ユーザーが明示的に「Ankiに追加して」「カード作って」などと言った

複数枚渡された場合は 1 枚ずつカードを作る。

## Required runtime checks (順番に必ず実施)

1. **Anki アプリが起動しているか**
   ```bash
   pgrep -x Anki >/dev/null || open -a Anki
   ```
   起動した直後ならコレクションが立ち上がるまで 2〜3 秒待つ。

2. **AnkiConnect が到達可能か** (デフォルトポート 8765)
   ```bash
   curl -sS -X POST http://127.0.0.1:8765 \
     -H 'Content-Type: application/json' \
     -d '{"action":"version","version":6}'
   ```
   - 成功すると `{"result": 6, "error": null}` (バージョン番号) が返る。
   - 失敗（Connection refused / タイムアウト）した場合は **セットアップ案内**（下記）を出してユーザー対応待ち。**勝手に進めない。**

## First-time setup (AnkiConnect 未導入時のみ案内)

ユーザーに次の手順を伝える：

> Anki を起動したまま下記を実施してください（初回のみ）:
> 1. メニュー `Tools → Add-ons → Get Add-ons...`
> 2. コード `2055492159` を入力して OK
> 3. Anki を一度再起動
>
> 再起動後にもう一度スクショを送ってください。

## Per-screenshot workflow

### Step 1: 画像の絶対パスを特定

ユーザーがチャットにペーストした画像は `~/.claude/image-cache/<session-id>/<N>.png` に保存される。最新のものを取得：

```bash
ls -t ~/.claude/image-cache/*/*.png 2>/dev/null | head -1
```

複数枚渡された場合は更新時刻順に古→新で処理する：

```bash
ls -tr ~/.claude/image-cache/*/*.png | tail -n <枚数>
```

判別が曖昧な時は、どのファイルか必ずユーザーに確認する。

### Step 2: 画像を解析・IELTS関連性チェック・訳と語彙メモを作る

Read ツールで画像ファイルを開く。**原文（英語）は裏に載せない** — 画像にすでに写っている前提。

#### 2-a. IELTS 関連性フィルタ（重要）

学習目的は **IELTS**。スクショの中身が IELTS で出てこなさそうなら **カード化せずスキップ** し、ユーザーに「これスキップしました（IELTS的に薄いので）」と一行で報告する。

**カード化する**:
- アカデミック語彙（Coxhead AWL 系、ラテン語源、formal 表現）
- IELTS 頻出トピックの語彙（health / sleep / environment / education / technology / society / culture / science）
- 言い換え・コロケーション・connective として使い回せる表現
- formal な文法構造（仮定法、倒置、関係詞、複雑な複文）

**カード化しない（スキップ）**:
- 完全な日常雑談・口語スラング・固有名詞のみで構成された字幕
- IELTS では使わない、ドラマ世界特有の俗語
- 既知の中学英語レベルで、見直す価値がない平易な文
- ユーザーがすでに知っていそうな超基礎語彙のみ

判断に迷うボーダーラインは **ユーザーに 1 行で確認** する（例: 「これ Macbeth の古語表現ですが IELTS 直結ではないです。入れますか？」）。

#### 2-b. **1 アイテム = 1 カード** の原則（重要）

字幕に IELTS 価値ある項目が複数あれば、**それぞれ別カードに分割**する。1 枚に複数項目を詰め込まない。SRS の効率（各項目に独立した忘却曲線）を最大化するため。

カード化単位：
- **基本語彙**: `circadian rhythm`, `dwindle`, `bottleneck` 等の単語
- **句動詞・熟語**: `figure out`, `power through`, `latch onto`, `take a hit` 等
- **イディオム**: `go haywire`, `regurgitate facts` 等
- **文法パターン**: `be supposed to V`, `the more X the more Y`, `periods of X that last for Y` 等

各カードの構成（裏面）:
- **日本語訳・意味**: 1 文で簡潔に
- **語彙画像**: そのアイテム 1 つに対応する `{{IMG:slug}}` 1 個
- **例文**: 原典の字幕文 + 必要に応じて追加例 1 個

各カードの表面（自動生成）:
- ターゲット項目 (bold) + 出典文 + Daniel 音声

**禁止**: 1 枚に 2 アイテム以上の解説を詰め込む。冗長な箇条書き。Wikipedia 的薀蓄。

### Step 3: 裏面 HTML を組み立てる

カードの Back フィールドはミニマル HTML。**裏に原文は入れない**（フロントの音声＋英文で十分）。各語彙には `{{IMG:slug}}` プレースホルダを挿入し、`vocab_images` で対応する検索クエリを渡す。

```html
<div style="font-family: -apple-system, 'Helvetica Neue', sans-serif; line-height:1.6; text-align:left;">
  <div style="font-weight:500; font-size:1.05em; margin-bottom:14px;">{JP_TRANSLATION_HTML}</div>
  <div style="font-size:0.95em; color:#444;">
    <b>word1</b>: 和訳/補足<br>
    {{IMG:word1}}
    <b>word2</b>: 和訳/補足<br>
    {{IMG:word2}}
  </div>
</div>
```

- 語彙は 1〜3 個を目安。各語に対応する `{{IMG:slug}}` を入れる（slug は英数字とハイフンで命名）。
- 検索クエリ設計のコツ:
  - 名詞は「具体物 + visualization」: `bottleneck` → `bottleneck pipe diagram` / `bottleneck illustration`
  - 動詞・形容詞は「典型的場面」: `jittery` → `nervous shaking hands cartoon` / `dwindle` → `decreasing diminishing illustration`
  - イディオムは「文字通り解釈の絵」: `go haywire` → `tangled wires chaos` / `take a hit` → `boxing punch`
- 文法ポイント中心のカード（`be supposed to V` など）は画像なしで OK。
- 装飾的なヘッダ（「日本語訳」「解説」のラベル）は **付けない**。
- 改行は `<br>`。`<`, `>`, `&` は `&lt; &gt; &amp;` にエスケープ。

### Step 4: AnkiConnect 経由で投入

`add_card.py` に JSON を stdin で渡す。**必ず Python ヒアドキュメントは使わず、`Write` で一時ファイルに JSON を書いてから流し込む**（クォート事故防止）：

```bash
python3 ~/.claude/skills/anki-add-from-screenshot/add_card.py < /tmp/anki_job_<timestamp>.json
```

JSON の中身（センテンスベース・推奨形式）：
```json
{
  "deck": "英語",
  "english_text": "The bottleneck is no longer typing.",
  "voice": "Daniel",
  "vocab_images": {
    "bottleneck": "bottleneck pipe diagram",
    "typing": "person typing keyboard"
  },
  "back_html": "<div>...{{IMG:bottleneck}}...{{IMG:typing}}...</div>",
  "tags": ["subtitle", "ted-talk", "ielts"]
}
```

主要フィールド：
- **`english_text`**: 字幕の英文をそのまま渡す（句読点込み）。`say -v Daniel` で音声合成 → afconvert で m4a 化 → Anki メディアに保存 → **表面に `[sound:...]`** を埋め込んで自動再生。字幕が複数フレームに跨る場合は完全文として連結。
- **`vocab_images`**: 辞書形式 `{slug: 検索クエリ}`。`back_html` 内の `{{IMG:slug}}` プレースホルダが、DuckDuckGo Images 経由で取得した画像 (`<img>` タグ) に置換される。クエリは具体的 (`bottleneck pipe diagram` > `bottleneck`) ほど命中率が高い。取得失敗時はプレースホルダが空文字に置換され、カードは壊れない。
- **`voice`**: デフォルト `Daniel` (en_GB)。別ボイスを使いたい時のみ指定（例: `"Samantha"`, `"Kate"`）。
- **`image`** (任意): 画像をフロントに使いたい時のみ指定。センテンスベースでは通常省略。

**カードのフロント仕様**:
- `english_text` 指定 + `image` 無し → 英文がスタイル付きで表示 + 音声自動再生（推奨）
- `image` 指定 → 画像表示 + 音声（旧形式、字幕読み取り目的）
- 両方無しは不可

- 成功時の stdout: `{"ok": true, "note_id": 1715000000000, "media": "anki-shot-...png", "audio": "anki-tts-...m4a", "deck": "英語", "synced": false}`
- **自動 AnkiWeb 同期**: 10 カード追加ごとに `sync` アクションを自動呼出（AnkiWeb 経由でスマホ等にも反映）。同期成功時は `"synced": true`。同期失敗（AnkiWeb 未ログイン等）でもカード追加自体は成功扱い。カウンタは `~/.claude/skills/anki-add-from-screenshot/.card_count` に保持。
- 失敗時 (exit 1): `{"ok": false, "error": "...", "detail": "..."}` ── error の値で次の対処を判断する：
  - `anki_connect_unreachable`: Anki/AnkiConnect の状態を再確認。ユーザーに再起動を依頼。
  - `model_missing`: `Basic` ノートタイプが Anki に無い。ユーザーに Anki を一度起動して初期化させる。
  - `anki_connect_error`: AnkiConnect が返したエラー文字列をそのまま伝え、対応を相談。
  - `tts_failed` / `tts_tool_missing`: `say` または `afconvert` が動かなかった。`english_text` を省いて再投入してもよい。

### Step 5: ユーザーに結果を簡潔に報告

```
✅ 英語 デッキにカード追加 (note id: 1715000000000)
   日本語訳: 早起きは三文の徳。
```

note id と日本語訳のワンライナーで十分。長文サマリは不要。

## Notes

- `Basic` モデル（Front/Back 2 フィールド）を使う。ユーザーが別モデルを要求した場合は `model_missing` を許容しつつ呼び出し時に上書きする。
- 重複検出は `allowDuplicate: true` でオフ。Front は画像なので実質ぶつからない。
- `tags` には `screenshot`, `subtitle` を基本に、ドラマ名/動画タイトルが判明していれば追加する。
- 一時 JSON ファイル (`/tmp/anki_job_*.json`) は使い終わったら削除する。
- カード追加後に Anki に自動でフォーカスを移したり、ブラウザを開いたりはしない（ユーザーが学習中の集中を切らない）。
