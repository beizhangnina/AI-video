"""Video generation via Token360 (POST /v1/videos).

Supports the Seedance video modes:
- text-to-video        : from_text(prompt, ...)
- first-frame I2V      : from_first_frame(image_path, motion_prompt, ...)
- first & last frame   : from_first_last(start, end, prompt, ...)
- reference images     : from_references([...], prompt, ...)
- extend video         : extend(video_path, prompt, ...)
- chained long shot    : chain_from_first_frame(image, [prompt1, prompt2, ...])

Token360 uses an async task model:
  POST /v1/videos -> task_id; poll GET /v1/videos/{id} until completed.
This module hides that loop behind a sync API; webhooks are exposed via
the optional callback_url parameter for advanced users.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from .. import assets
from ..cache import cache_path, hit
from ..client import http_client
from ..config import settings

ALLOWED_DURATIONS = {3, 4, 5, 6, 7, 8, 9, 10, 12}


def _ensure_asset_uri(image_path_or_uri: str | Path) -> str:
    """Accept a local path or an existing asset:// URI. Upload if needed."""
    s = str(image_path_or_uri)
    if s.startswith("asset://"):
        return s
    return assets.upload_and_wait(s)


def _poll_task(task_id: str, timeout: float = 600.0, poll: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = http_client().get(f"/videos/{task_id}")
        r.raise_for_status()
        body = r.json()
        status = (body.get("status") or "").lower()
        if status == "completed":
            return body
        if status == "failed":
            raise RuntimeError(f"Video task {task_id} failed: {body}")
        time.sleep(poll)
    raise TimeoutError(f"Video task {task_id} did not finish within {timeout}s")


def _download(url: str, dest: Path) -> Path:
    with httpx.stream("GET", url, timeout=300) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    return dest


def _extract_video_url(body: dict) -> str:
    # Token360 typically returns either body["url"] or body["video"]["url"];
    # handle both shapes defensively.
    for key in ("video_url", "url"):
        if isinstance(body.get(key), str):
            return body[key]
    video = body.get("video") or body.get("data") or {}
    if isinstance(video, dict):
        for key in ("url", "video_url"):
            if isinstance(video.get(key), str):
                return video[key]
    raise RuntimeError(f"Could not find video URL in response: {body}")


def _submit_and_wait(
    *,
    payload: dict,
    cache_params: dict,
    callback_url: str | None,
) -> Path:
    """Shared submit-poll-download flow for all modes."""
    model = payload["model"]
    path = cache_path("video", model, cache_params, "mp4")
    if hit(path):
        return path

    if callback_url:
        payload = {**payload, "callback_url": callback_url, "request_id": cache_params.get("rid")}

    # /v1/videos is Token360-specific; not part of OpenAI SDK surface.
    r = http_client().post("/videos", json=payload)
    r.raise_for_status()
    resp = r.json()
    task_id = resp.get("id") or resp.get("task_id") or resp.get("data", {}).get("id")
    if not task_id:
        raise RuntimeError(f"No task id in /videos response: {resp}")

    if callback_url:
        # User opted into webhook delivery; don't poll. Return a placeholder path
        # that the caller's webhook handler should fill in.
        path.write_bytes(b"")
        return path

    final = _poll_task(task_id)
    return _download(_extract_video_url(final), path)


def from_text(
    prompt: str,
    *,
    model: str | None = None,
    duration: int = 5,
    size: str | None = None,
    callback_url: str | None = None,
) -> Path:
    """Text-to-video. Returns a local MP4 path."""
    if duration not in ALLOWED_DURATIONS:
        raise ValueError(f"duration must be in {sorted(ALLOWED_DURATIONS)}, got {duration}")
    model = model or settings.video_model
    size = size or f"{settings.width}x{settings.height}"
    payload = {
        "model": model,
        "prompt": prompt,
        "seconds": duration,
        "size": size,
    }
    return _submit_and_wait(
        payload=payload,
        cache_params={"prompt": prompt, "duration": duration, "size": size},
        callback_url=callback_url,
    )


def from_first_frame(
    image: str | Path,
    motion_prompt: str,
    *,
    model: str | None = None,
    duration: int = 5,
    portrait: str | None = None,
    callback_url: str | None = None,
) -> Path:
    """Animate a single image (first-frame I2V). Recommended for narrated_story.

    image: local path or asset:// URI for the starting frame.
    portrait: optional asset:// URI of a Virtual Portrait / RealFace asset
              for character consistency (Seedance 2.0 series only).
    """
    if duration not in ALLOWED_DURATIONS:
        raise ValueError(f"duration must be in {sorted(ALLOWED_DURATIONS)}, got {duration}")
    model = model or settings.video_model
    first_uri = _ensure_asset_uri(image)
    payload: dict[str, Any] = {
        "model": model,
        "prompt": motion_prompt,
        "seconds": duration,
        "frame_images": [
            {"type": "image_url", "frame_type": "first_frame", "image_url": {"url": first_uri}},
        ],
    }
    if portrait:
        payload["input_references"] = [{"type": "image_url", "image_url": {"url": portrait}}]
    return _submit_and_wait(
        payload=payload,
        cache_params={"first": first_uri, "prompt": motion_prompt, "duration": duration, "portrait": portrait},
        callback_url=callback_url,
    )


def from_first_last(
    start: str | Path,
    end: str | Path,
    prompt: str,
    *,
    model: str | None = None,
    duration: int = 5,
    callback_url: str | None = None,
) -> Path:
    """Interpolate between two key frames."""
    if duration not in ALLOWED_DURATIONS:
        raise ValueError(f"duration must be in {sorted(ALLOWED_DURATIONS)}, got {duration}")
    model = model or settings.video_model
    start_uri = _ensure_asset_uri(start)
    end_uri = _ensure_asset_uri(end)
    payload = {
        "model": model,
        "prompt": prompt,
        "seconds": duration,
        "frame_images": [
            {"type": "image_url", "frame_type": "first_frame", "image_url": {"url": start_uri}},
            {"type": "image_url", "frame_type": "last_frame", "image_url": {"url": end_uri}},
        ],
    }
    return _submit_and_wait(
        payload=payload,
        cache_params={"start": start_uri, "end": end_uri, "prompt": prompt, "duration": duration},
        callback_url=callback_url,
    )


def from_references(
    images: list[str | Path],
    prompt: str,
    *,
    model: str | None = None,
    duration: int = 5,
    callback_url: str | None = None,
) -> Path:
    """Use multiple reference images (style/character) plus a text prompt."""
    if duration not in ALLOWED_DURATIONS:
        raise ValueError(f"duration must be in {sorted(ALLOWED_DURATIONS)}, got {duration}")
    model = model or settings.video_model
    uris = [_ensure_asset_uri(p) for p in images]
    payload = {
        "model": model,
        "prompt": prompt,
        "seconds": duration,
        "input_references": [
            {"type": "image_url", "image_url": {"url": u}} for u in uris
        ],
    }
    return _submit_and_wait(
        payload=payload,
        cache_params={"refs": uris, "prompt": prompt, "duration": duration},
        callback_url=callback_url,
    )


def extend(
    video_path: str | Path,
    prompt: str,
    *,
    model: str | None = None,
    duration: int = 8,
    callback_url: str | None = None,
) -> Path:
    """Continue an existing video for `duration` more seconds.

    Maps to Token360's \"Extend video\" mode (Seedance 2.0 series). The provider
    sees the existing clip's tail and synthesizes a continuation that flows
    from the last frame, no manual frame-handoff needed.

    Note: per-call duration cap still applies. For sequences longer than that
    cap, prefer `chain_from_first_frame()` which handles the segmenting.
    """
    if duration not in ALLOWED_DURATIONS:
        raise ValueError(f"duration must be in {sorted(ALLOWED_DURATIONS)}, got {duration}")
    model = model or settings.video_model
    src_uri = _ensure_asset_uri(video_path)
    payload = {
        "model": model,
        "prompt": prompt,
        "seconds": duration,
        "mode": "extend",
        "source_video": {"type": "video_url", "video_url": {"url": src_uri}},
    }
    return _submit_and_wait(
        payload=payload,
        cache_params={"extend": src_uri, "prompt": prompt, "duration": duration},
        callback_url=callback_url,
    )


def chain_from_first_frame(
    image: str | Path,
    motion_prompts: list[str],
    *,
    seconds_per_clip: int = 8,
    model: str | None = None,
    portrait: str | None = None,
) -> Path:
    """Build a long continuous shot by chaining first-frame I2V calls.

    Strategy:
      clip_1 = video.from_first_frame(image,           motion_prompts[0])
      clip_2 = video.from_first_frame(last(clip_1),    motion_prompts[1])
      clip_3 = video.from_first_frame(last(clip_2),    motion_prompts[2])
      ...
    The clips share a true visual handoff (the last frame is literally the
    next first frame), so concatenating them looks like one camera move.

    Returns the path of a SINGLE concatenated mp4 of length
    `seconds_per_clip * len(motion_prompts)`.

    Use this when the desired shot exceeds the per-call max duration, or when
    you want a guaranteed seamless transition between two beats.
    """
    if not motion_prompts:
        raise ValueError("motion_prompts must contain at least one prompt")
    if seconds_per_clip not in ALLOWED_DURATIONS:
        raise ValueError(
            f"seconds_per_clip must be in {sorted(ALLOWED_DURATIONS)}, got {seconds_per_clip}"
        )

    # Lazy imports to avoid pulling moviepy/handoff during simple text-only video calls.
    from moviepy import concatenate_videoclips
    from ..compose import handoff
    from ..compose.stitch import load as load_clip

    cache_params = {
        "chain_image": str(image),
        "prompts": motion_prompts,
        "seconds_per_clip": seconds_per_clip,
        "portrait": portrait,
    }
    final_path = cache_path("video", model or settings.video_model, cache_params, "mp4")
    if hit(final_path):
        return final_path

    seed: str | Path = image
    sub_clips: list[Path] = []
    for i, mp in enumerate(motion_prompts):
        clip_path = from_first_frame(
            seed,
            mp,
            duration=seconds_per_clip,
            model=model,
            portrait=portrait,
        )
        sub_clips.append(clip_path)
        if i < len(motion_prompts) - 1:
            seed = handoff.last_frame(clip_path)

    loaded = [load_clip(p) for p in sub_clips]
    concatenated = concatenate_videoclips(loaded, method="compose")
    concatenated.write_videofile(
        str(final_path),
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )
    return final_path


def native(body: dict, *, callback_url: str | None = None) -> Path:
    """Escape hatch: send a vendor-native JSON body to /v1/videos.

    Adds the Token360-Native-Params header. Use only when the normalized
    OpenAI-style fields don't expose what you need. Body must include 'model'.
    """
    if "model" not in body:
        raise ValueError("native() body must include 'model'")
    model = body["model"]
    cache_params = {"native": body}
    path = cache_path("video", model, cache_params, "mp4")
    if hit(path):
        return path

    if callback_url:
        body = {**body, "callback_url": callback_url}

    r = http_client().post(
        "/videos",
        json=body,
        headers={"Token360-Native-Params": "true", "Content-Type": "application/json"},
    )
    r.raise_for_status()
    resp = r.json()
    task_id = resp.get("id") or resp.get("task_id") or resp.get("data", {}).get("id")
    if not task_id:
        raise RuntimeError(f"No task id in /videos response: {resp}")
    if callback_url:
        path.write_bytes(b"")
        return path
    final = _poll_task(task_id)
    return _download(_extract_video_url(final), path)
