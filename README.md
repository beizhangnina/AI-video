# ai-video

A repo-as-app for going from a one-line idea to a finished short video,
powered by [Token360](https://www.token360.ai) — one OpenAI-compatible
gateway for LLM, image generation, TTS, and video generation.

No UI. No web server. You write `aivideo make "an octopus that wants to see
the world"` and a Python pipeline plans the shots, generates each one,
quality-checks them, and stitches the result into an mp4.

---

## How it works

```
┌──────────┐   ┌─────────┐   ┌──────────┐   ┌────┐   ┌──────────┐
│  idea    │ → │ planner │ → │ executor │ → │ QC │ → │ delivery │
│ (string) │   │  (LLM)  │   │  (loop)  │   │(LLM│   │ (folder) │
└──────────┘   └─────────┘   └──────────┘   │vis)│   └──────────┘
                                            └────┘
```

| Stage | Module | What it does |
|---|---|---|
| Planner | `agents/planner.py` | LLM turns a fuzzy idea into a strict `Plan` JSON: title, style, voice, full narration, 4–7 keyframes (each with image_prompt + motion_prompt + seconds) |
| Executor | `agents/executor.py` | For each keyframe: image gen → QC → (retry if fail) → first-frame I2V video gen → QC. Persists every artifact into the run folder |
| QC | `agents/qc.py` | Multimodal LLM scores each artifact (0–1) against the director's intent, suggests refinements when below threshold |
| Delivery | `pipelines/auto.py` + `runs.py` | Stitches video clips, burns subtitles, mixes narration audio, writes `final.mp4` and `report.md` into `runs/<timestamp>-<slug>/` |

Every run is fully traceable: the plan, every image, every video clip, every
QC report, and a markdown summary all live next to the final mp4.

---

## Install

```bash
# 1. System deps
sudo apt-get install ffmpeg            # Debian/Ubuntu
# or:  brew install ffmpeg             # macOS

# 2. Python package
git clone https://github.com/beizhangnina/AI-video.git
cd AI-video
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Configure Token360
cp .env.example .env
# Edit .env and set TOKEN360_API_KEY=sk-...
```

---

## Quickstart: idea → mp4

```bash
aivideo make "an octopus that wants to see the world"
```

That single command:

1. Allocates `runs/20260509-184523-an-octopus-that-wants-to-see-the-world/`
2. Asks the planner LLM to produce a Plan JSON (writes `plan.json`)
3. For each of the ~5 keyframes:
   - generates an image (writes `scenes/k01-image.png`)
   - QC the image; if rejected, asks the planner to refine the prompt and retries once
   - feeds the image to Seedance first-frame I2V (writes `scenes/k01-video.mp4`)
   - QC the video clip
4. Synthesizes narration with TTS (writes `narration.mp3`)
5. Concatenates clips, burns subtitles, mixes audio
6. Writes `final.mp4` and `report.md`

Re-running the same idea string is cheap: every Token360 call is content-hashed
and cached under `cache/`.

### Presets — fight choice fatigue

Pass any of `--style / --duration / --aspect / --mood / --voice / --pacing`
with a preset slug, and the planner will honor it as a hard constraint. Each
preset accepts either a slug or a raw user-supplied descriptor (so power users
aren't trapped):

```bash
aivideo make "a cat learns to surf" --style ghibli --duration short --mood cheerful

aivideo make "a midnight ramen shop" --style cyberpunk --voice deep --pacing slow

aivideo make "侠客江湖归来" --style wuxia --aspect vertical --voice dramatic
```

Run `aivideo styles` to see every preset slug and what it expands to.

| Flag | Slugs |
|---|---|
| `--style` | `cyberpunk` · `ghibli` · `pixar_3d` · `photorealistic` · `wuxia` · `cinematic` · `anime` · `cartoon_2d` · `noir` · `watercolor` |
| `--duration` | `snippet` (15s) · `short` (30s) · `standard` (45s) · `long_form` (75s) — or a raw integer |
| `--aspect` | `vertical` (9:16) · `horizontal` (16:9) · `square` (1:1) |
| `--mood` | `cheerful` · `melancholic` · `mysterious` · `epic` · `comedic` · `romantic` · `suspenseful` · `serene` |
| `--voice` | `warm` (alloy) · `energetic` (nova) · `deep` (onyx) · `bright` (shimmer) · `gentle` (fable) · `dramatic` (echo) |
| `--pacing` | `slow` · `normal` · `fast` |

### Other flags

```bash
# Cheap iteration: skip video gen, use Ken Burns zoom over still images
aivideo make "..." --motion kenburns

# Disable the QC loop (faster, no retry)
aivideo make "..." --no-qc

# Force character consistency with a Virtual Portrait or RealFace asset
aivideo make "..." --portrait asset://ta_xxxxxxxx
```

### Run folder layout

```
runs/20260509-184523-an-octopus-.../
├── plan.json                # full Plan dataclass dump
├── scenes/
│   ├── k01-image.png
│   ├── k01-qc-image.json
│   ├── k01-video.mp4
│   ├── k01-qc-video.json
│   ├── k02-image.png
│   ...
├── narration.mp3
├── final.mp4
└── report.md                # human-readable: plan summary + per-scene QC
```

`runs/` is gitignored. Move or zip a folder anywhere to keep a "version" of
that idea, or delete to free disk.

---

## Two ways to use the repo

### A. The app — `aivideo make`

For 95% of cases. You bring the idea, the agents handle planning, generation,
QC, and packaging.

```bash
aivideo make "a meditative day in the life of a lighthouse keeper"
aivideo make "一只想环游世界的章鱼，水彩绘本风格"
aivideo make "cyberpunk ramen shop in 2089 Tokyo, neon, 30 seconds"
```

### B. Hand-rolled scripts under `scripts/`

When you want full control, drop a Python file in `scripts/` and import the
building blocks directly. Examples shipped with the repo:

| File | Purpose |
|---|---|
| `scripts/00_make.py` | Same as `aivideo make`, runnable as `python scripts/00_make.py "..."` |
| `scripts/01_hello_world.py` | Minimal smoke test: 1 image + 1 TTS line + 5s mp4 |
| `scripts/02_short_story.py` | Hard-coded narrated_story (skips planner) |
| `scripts/03_kenburns_fallback.py` | Same flow as 02 but with Ken Burns instead of video gen |

Hand-rolled freestyle:

```python
from aivideo.generate import llm, image, tts, video
from aivideo.compose import stitch, render
from aivideo.config import settings

idea = llm.script(
    "Write a 15-second cyberpunk trailer voiceover and 3 shot descriptions",
    json_mode=True,
)
clips = []
for shot in idea["shots"]:
    img = image.image(shot["image_prompt"], size="1024x1792")
    mp4 = video.from_first_frame(img, shot["motion"], duration=5)
    clips.append(stitch.fit_to_size(stitch.load(mp4), settings.width, settings.height))
final = stitch.with_audio(stitch.concat(clips), tts.speak(idea["narration"], voice="onyx"))
render.to_mp4(final, "cyberpunk.mp4")
```

---

## Repository layout

```
src/aivideo/
├── config.py              # .env loading, default models, paths
├── client.py              # OpenAI SDK + httpx client (both pointed at Token360)
├── cache.py               # content-addressed disk cache for AI outputs
├── runs.py                # run-folder allocation + artifact paths
├── assets.py              # Token360 native Assets API (RealFace, Virtual Portrait)
├── presets.py             # 10 styles + duration/aspect/mood/voice/pacing slugs
│
├── agents/                # the "app" brain
│   ├── schemas.py         # Plan, Keyframe, QCReport dataclasses
│   ├── planner.py         # idea -> Plan (honors presets)
│   ├── executor.py        # walks Plan, generates + QC + retry, frame handoff
│   └── qc.py              # multimodal artifact review
│
├── generate/              # Token360 wrappers, each with disk caching
│   ├── llm.py
│   ├── image.py
│   ├── tts.py
│   └── video.py           # text / I2V / first-last / references / extend / chain / native
│
├── compose/               # ffmpeg-based composition
│   ├── stitch.py          # concat / audio overlay / fit-to-size
│   ├── kenburns.py        # zoom-pan over a still image
│   ├── subtitles.py       # Pillow-based burned subtitles
│   ├── handoff.py         # extract last frame for cross-clip continuity
│   └── render.py          # final h264 encode
│
├── pipelines/
│   ├── auto.py            # idea -> Plan -> execute -> QC -> deliver
│   └── narrated_story.py  # rigid template (skips planner)
│
└── cli.py                 # `aivideo make` / `aivideo run` / `aivideo list`

scripts/                   # your video ideas; hand-rolled or one-liner
runs/                      # gitignored: per-run artifact folders
cache/                     # gitignored: AI output cache
output/                    # gitignored: ad-hoc mp4 dumps from scripts/
```

---

## Plan schema

The planner outputs (and the executor consumes) this JSON:

```json
{
  "title": "Octopus Wants the World",
  "logline": "A homebound octopus dreams its way across distant oceans.",
  "style": {
    "visual": "watercolor storybook, warm tones, soft focus",
    "voice": "alloy",
    "voice_direction": "warm narrator, unhurried",
    "aspect": "9:16",
    "duration_target": 30
  },
  "narration": "Down in a quiet reef ... she wonders what lies beyond.",
  "keyframes": [
    {
      "id": "k01",
      "narration": "Down in a quiet reef, an octopus pressed against the glass.",
      "image_prompt": "A small purple octopus inside a coral cave, peering out at...",
      "motion_prompt": "octopus drifts forward as camera slowly pulls back",
      "seconds": 5,
      "transition_in": "cut",
      "role": "opening",
      "continues_from_prev": false
    },
    {
      "id": "k02",
      "narration": "Past the kelp forest, the open ocean stretched endlessly.",
      "image_prompt": "Wide expanse of teal ocean, sun beams cutting through water...",
      "motion_prompt": "camera drifts forward through floating particles",
      "seconds": 8,
      "transition_in": "fade",
      "role": "build",
      "continues_from_prev": true
    }
  ]
}
```

`role` shapes narrative arc: `opening` (first scene) → one or more `build`
scenes → optional `climax` → `resolution` (last scene). The planner is
instructed to honor this structure.

`continues_from_prev=true` tells the executor to skip image generation for
that scene and instead use the **last frame of the previous scene's video
clip** as the first frame for this one's I2V call. Two uses:

1. **Long continuous shot** beyond the per-call cap: split a 24s shot into
   three keyframes (8s each), set `continues_from_prev=true` on the second
   and third — the result is one seamless 24-second camera move.
2. **Smooth scene transitions** between conceptually different beats: visual
   continuity instead of a hard cut.

You can hand-edit `runs/<id>/plan.json` and then re-run the executor on it
(forthcoming `aivideo replay <run_id>` — for now, copy the JSON into a
script that calls `executor.execute()`).

### Long shots: `chain_from_first_frame()`

For pure code-driven chained generation (no planner), use:

```python
from aivideo.generate import video

# 24-second seamless shot from a single starting image:
mp4 = video.chain_from_first_frame(
    image="opening.png",
    motion_prompts=[
        "camera drifts forward over coral reef, fish school passes",
        "camera continues forward, kelp parts to reveal open ocean",
        "camera lifts upward, sunlight breaks the surface",
    ],
    seconds_per_clip=8,
)
# -> single mp4, ~24 seconds total, last frame of clip N == first frame of clip N+1
```

---

## Token360 specifics

- **Base URL.** `https://api.token360.ai/v1`
- **Auth.** `Authorization: Bearer sk-...`
- **OpenAI-compatible.** Chat, images, TTS use the standard `openai` SDK,
  only `base_url` changes.
- **Native passthrough.** Add `Token360-Native-Params: true` header to send
  vendor-original JSON. Use `video.native(body=...)` only when normalized
  fields don't expose what you need.
- **Asset references.** Modes that need image inputs use `asset://ta_xxx`
  URIs. `video.from_first_frame()` etc. handle uploading transparently via
  `assets.py`.
- **Async tasks.** `POST /v1/videos` returns a task id; this library polls
  to completion. Pass `callback_url=` for webhook delivery (rarely needed
  in scripted use).

### Default models (override in `.env`)

| Capability | Default | Notes |
|---|---|---|
| LLM (planner + QC) | `gpt-4o` | needs vision support for QC |
| Image | `dall-e-3` | |
| TTS | `tts-1-hd` (voice `alloy`) | |
| Video | `seedance-2.0-fast` | BytePlus, supports RealFace + Virtual Portrait |

If a default isn't enabled on your Token360 workspace, the API returns a
clear "model not supported" error — update `.env` accordingly.

---

## QC behavior

- Each generated image and video is scored 0.0–1.0 by a multimodal LLM
  against the director's intent (`image_prompt`, `motion_prompt`, style).
- Threshold: `0.65`. Below that, the image gets one retry with a refined
  prompt produced by the planner.
- If the retry still fails, the keyframe is **flagged** and the run continues
  — it appears in `report.md` under "Flagged keyframes" so you can decide
  whether to manually re-run or accept.
- Disable with `--no-qc` to save LLM calls when you're iterating on style.

---

## Common errors

| Symptom | Likely cause |
|---|---|
| `401 Unauthorized` | `TOKEN360_API_KEY` missing or wrong format (must start with `sk-`) |
| `InvalidParameter on duration` | Pass an int (e.g. `5`), not a string `"5"` |
| `Asset validation failed` | The `asset://ta_xxx` id was typo'd or not yet `active`; `assets.wait_active()` should prevent this |
| `Model not supported` | The model name in `.env` is not enabled on your workspace |
| Plan JSON missing keys | The planner LLM returned a malformed JSON; rerun (caching is per-prompt so a small idea-string change forces a fresh call) |
| Subtitles render as boxes | Install Noto CJK or set `font_path=` in `subtitles.burn()` |

---

## License

MIT.
