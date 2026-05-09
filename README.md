# ai-video

Script-driven AI video generation on top of [Token360](https://www.token360.ai)
— one OpenAI-compatible gateway for LLM, image gen, TTS, and video gen.

No UI, no web server. Each video is a Python script under `scripts/` that
composes reusable building blocks (`generate/`, `compose/`, `pipelines/`).

## Quick start

```bash
# 1. System deps (ffmpeg is required by moviepy and pydub)
brew install ffmpeg                    # macOS
# or:  sudo apt-get install ffmpeg     # Debian/Ubuntu

# 2. Project deps
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Configure
cp .env.example .env
# edit .env: set TOKEN360_API_KEY=sk-...

# 4. Smoke test (cheap: 1 image + 1 TTS line, ~5s mp4)
python scripts/01_hello_world.py

# 5. Full narrated story with AI video gen per scene (~30s mp4)
python scripts/02_short_story.py

# 6. Same flow with Ken Burns instead of video gen (cheap iteration)
python scripts/03_kenburns_fallback.py
```

Generated mp4s land in `output/`. AI responses are cached in `cache/`,
so re-running a script does not re-pay for unchanged prompts.

## Repository layout

```
src/aivideo/
├── config.py              # .env loading, default models, paths
├── client.py              # OpenAI SDK + httpx client (both pointed at Token360)
├── cache.py               # content-addressed disk cache for AI outputs
├── assets.py              # Token360 native Assets API (RealFace, Virtual Portrait)
├── generate/
│   ├── llm.py             # chat completions
│   ├── image.py           # image generation
│   ├── tts.py             # text-to-speech
│   └── video.py           # text-to-video / I2V / first-last / references
├── compose/
│   ├── stitch.py          # concat / audio overlay / fit-to-size
│   ├── kenburns.py        # zoom-pan over a still image
│   ├── subtitles.py       # Pillow-based burned subtitles
│   └── render.py          # final h264 encode
└── pipelines/
    └── narrated_story.py  # topic -> outline -> scenes -> mp4

scripts/                   # your video ideas; each file = one video
```

## Authoring a new video

Two patterns.

### A. Use a pipeline

```python
# scripts/my_video.py
from aivideo.pipelines.narrated_story import run

run(
    topic="A meditative day in the life of a lighthouse keeper",
    style="painterly, golden hour, vertical",
    voice="onyx",
    duration_target=45,
    motion="video_gen",   # or "kenburns" for cheap iteration
    output="lighthouse.mp4",
)
```

### B. Hand-roll the composition

```python
# scripts/my_freestyle.py
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

audio = tts.speak(idea["narration"], voice="onyx")
final = stitch.with_audio(stitch.concat(clips), audio)
render.to_mp4(final, "cyberpunk.mp4")
```

## Token360 specifics

- **Base URL**: `https://api.token360.ai/v1`
- **Auth**: `Authorization: Bearer sk-...`
- **OpenAI-compatible**: chat, images, audio.speech all use the standard
  `openai` Python SDK — only the `base_url` changes.
- **Native passthrough**: send vendor-original JSON with the
  `Token360-Native-Params: true` header. Use `video.native(body=...)` when
  the normalized fields don't expose what you need.
- **Asset references**: video gen modes that need image inputs (first frame,
  references, RealFace, Virtual Portrait) use `asset://ta_xxx` URIs.
  `generate.video.from_first_frame()` etc. handle uploading transparently
  via `assets.py`.
- **Async tasks**: `POST /v1/videos` returns a task id; this library polls
  to completion by default. Pass `callback_url=` for webhook delivery.

## Models

Defaults live in `.env` and can be overridden per-call:

| Capability | Default | Where used |
|---|---|---|
| LLM | `gpt-4o` | `generate.llm.script()` |
| Image | `dall-e-3` | `generate.image.image()` |
| TTS | `tts-1-hd` (voice `alloy`) | `generate.tts.speak()` |
| Video | `seedance-2.0-fast` | `generate.video.*` |

If a default isn't available on your account, Token360 returns a clear
error — update `.env` accordingly.

## Common errors

| Symptom | Likely cause |
|---|---|
| `401 Unauthorized` | `TOKEN360_API_KEY` missing or wrong format (must include `sk-`) |
| `InvalidParameter on duration` | Pass an int (e.g. `5`), not a string `"5"` |
| `Asset validation failed` | The `asset://ta_xxx` id was typo'd or not yet `active`; `assets.wait_active()` should prevent this |
| `Model not supported` | The model name in `.env` is not enabled on your workspace |
| Unicode glyphs render as boxes in subtitles | Install Noto CJK or set `font_path=` in `subtitles.burn()` |
