"""User-facing presets to reduce decision fatigue.

Each preset maps a short slug to a rich descriptor (for visual style and mood)
or a canonical value (for duration/aspect/voice). Resolvers accept either a
preset slug OR a raw user-supplied string — unknown inputs pass through so
power users can still write free-form descriptions.
"""

from __future__ import annotations

# 10 popular visual styles. Each value gets injected into the planner's
# `style.visual` field, so the LLM steers every image_prompt toward this look.
STYLES: dict[str, str] = {
    "cyberpunk": (
        "cyberpunk, neon-lit rain-slicked streets, holographic signage, "
        "gritty futurism, vivid teal and magenta palette, atmospheric haze"
    ),
    "ghibli": (
        "Studio Ghibli watercolor storybook, soft sunlight through leaves, "
        "hand-drawn warmth, gentle wind, lush nature, painterly brushwork"
    ),
    "pixar_3d": (
        "3D Pixar-style animation, expressive characters with large eyes, "
        "soft cinematic lighting, shallow depth of field, polished surfaces"
    ),
    "photorealistic": (
        "photorealistic 35mm cinematography, natural lighting, shallow depth "
        "of field, true colors, cinematic composition"
    ),
    "wuxia": (
        "Chinese wuxia ink-wash painting, swirling mist on mountain peaks, "
        "robes catching wind, calligraphic energy, restrained palette"
    ),
    "cinematic": (
        "modern cinema look, anamorphic widescreen mood, dramatic color "
        "grading, atmospheric haze, film grain"
    ),
    "anime": (
        "Japanese anime, cel-shaded with bold black outlines, vibrant "
        "saturated colors, dynamic poses, dramatic skies"
    ),
    "cartoon_2d": (
        "flat 2D cartoon, bold black outlines, saturated flat color blocks, "
        "simple expressive shapes, playful energy"
    ),
    "noir": (
        "black-and-white film noir, harsh shadows, smoky chiaroscuro, "
        "venetian-blind light, 1940s mood"
    ),
    "watercolor": (
        "soft watercolor storybook, gentle paper texture, warm sun-washed "
        "palette, loose edges, picture-book composition"
    ),
}

# Total seconds. Planner aims for this; chained scenes can exceed per-call max.
DURATIONS: dict[str, int] = {
    "snippet": 15,
    "short": 30,
    "standard": 45,
    "long_form": 75,
}

# Aspect-ratio strings the planner emits and the compositor honors.
ASPECTS: dict[str, str] = {
    "vertical": "9:16",
    "horizontal": "16:9",
    "square": "1:1",
}

# Tone hints that bend image_prompts and voice_direction.
MOODS: dict[str, str] = {
    "cheerful": "bright, upbeat, optimistic, light, energetic",
    "melancholic": "subdued, wistful, soft, introspective, gentle",
    "mysterious": "shadowed, suggestive, slow-paced, ambiguous",
    "epic": "grand, sweeping, dramatic, powerful",
    "comedic": "playful, exaggerated, bouncy, lighthearted",
    "romantic": "warm, intimate, golden hour, tender",
    "suspenseful": "tense, restrained, taut, deliberate",
    "serene": "calm, still, breathy, contemplative",
}

# Friendly aliases for the OpenAI-compatible TTS voices.
VOICES: dict[str, str] = {
    "warm": "alloy",
    "energetic": "nova",
    "deep": "onyx",
    "bright": "shimmer",
    "gentle": "fable",
    "dramatic": "echo",
}

# Pacing affects how planner distributes seconds across keyframes.
PACINGS: dict[str, str] = {
    "slow": "long contemplative shots, fewer cuts, 8-12 seconds per scene",
    "normal": "balanced pacing, 5-8 seconds per scene",
    "fast": "snappy MTV-style cuts, 3-5 seconds per scene",
}


def resolve_style(value: str | None) -> str | None:
    """Return the rich descriptor for a style preset, or pass through raw input."""
    if not value:
        return None
    return STYLES.get(value, value)


def resolve_duration(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if value in DURATIONS:
        return DURATIONS[value]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_aspect(value: str | None) -> str | None:
    if not value:
        return None
    return ASPECTS.get(value, value)


def resolve_mood(value: str | None) -> str | None:
    if not value:
        return None
    return MOODS.get(value, value)


def resolve_voice(value: str | None) -> str | None:
    if not value:
        return None
    return VOICES.get(value, value)


def resolve_pacing(value: str | None) -> str | None:
    if not value:
        return None
    return PACINGS.get(value, value)


def list_options() -> dict[str, list[str]]:
    """Return all preset slugs grouped by category — used by `aivideo styles`."""
    return {
        "style": list(STYLES.keys()),
        "duration": list(DURATIONS.keys()),
        "aspect": list(ASPECTS.keys()),
        "mood": list(MOODS.keys()),
        "voice": list(VOICES.keys()),
        "pacing": list(PACINGS.keys()),
    }
