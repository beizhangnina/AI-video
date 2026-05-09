"""Minimal end-to-end smoke test.

One AI image + one TTS line + Ken Burns motion -> ~5s vertical mp4.
Cheapest possible verification that Token360 + the local pipeline works.

Run:
    python scripts/01_hello_world.py
"""

from aivideo.compose import kenburns, render, stitch
from aivideo.generate import image, tts

img = image.image(
    "A glowing neon dolphin leaping over a quiet midnight ocean, anime style, vertical poster",
    size="1024x1792",
)

voice = tts.speak("Hello world from the Token 360 video pipeline.", voice="alloy")

clip = kenburns.from_image(img, duration=5.0)
clip = stitch.with_audio(clip, voice)

render.to_mp4(clip, "hello.mp4")
print("Wrote output/hello.mp4")
