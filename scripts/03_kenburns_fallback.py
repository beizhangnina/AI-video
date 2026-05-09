"""Same narrated-story flow but with Ken Burns zoom instead of video gen.

Useful when you're iterating on the script/voice and don't want to pay for
video generation on every run.

Run:
    python scripts/03_kenburns_fallback.py
"""

from aivideo.pipelines.narrated_story import run

run(
    topic="A late-night ramen shop in 2089 Tokyo",
    style="cyberpunk, neon, rain-slick streets, vertical poster",
    voice="onyx",
    duration_target=25,
    motion="kenburns",
    output="ramen_2089.mp4",
)
