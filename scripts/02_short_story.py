"""Narrated-story example with AI video generation per scene.

Run:
    python scripts/02_short_story.py

Cost note: this calls Token360 video gen once per scene. With ~5 scenes at
seedance-2.0-fast that's a few minutes of wall time. Reruns hit the cache.
"""

from aivideo.pipelines.narrated_story import run

run(
    topic="一只想环游世界的章鱼",
    style="水彩绘本，温暖治愈，竖屏构图",
    voice="alloy",
    duration_target=30,
    motion="video_gen",
    output="octopus.mp4",
)
