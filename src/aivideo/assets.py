"""Token360 native Assets API.

POST /v1/asset-groups, POST /v1/assets, GET /v1/assets/{id}, etc.
Used to upload local images and reference them as asset://ta_xxx URIs in
video generation requests (required for Seedance first-frame I2V, RealFace,
Virtual Portrait, multi-reference modes).
"""

from __future__ import annotations

import time
from pathlib import Path

from .client import http_client

# Default group used by generate/video.py for transparent local-image uploads.
_DEFAULT_GROUP_NAME = "aivideo-default"
_DEFAULT_GROUP_KIND = "GENERIC"

# For first-frame handoff uploads we need ta_xxx asset IDs (frame_images requires
# Virtual Portrait / RealFace assets; generic ua_xxx is rejected by Token360).
_HANDOFF_GROUP_NAME = "aivideo-handoff-frames"
_HANDOFF_GROUP_KIND = "VIRTUAL_PORTRAIT"


def create_group(name: str, kind: str = "GENERIC") -> dict:
    """Create an asset group. kind: GENERIC | REAL_FACE | VIRTUAL_PORTRAIT.

    For REAL_FACE the response includes h5Link (a 120s real-person verification
    link the human must open on a phone). For other kinds the group is active
    immediately.
    """
    r = http_client().post(
        "/asset-groups",
        json={"name": name, "groupKind": kind},
    )
    r.raise_for_status()
    return r.json()


def list_groups(kind: str | None = None) -> list[dict]:
    params = {"groupKind": kind} if kind else {}
    r = http_client().get("/asset-groups", params=params)
    r.raise_for_status()
    body = r.json()
    data = body.get("data", body)
    if isinstance(data, dict):
        return data.get("list") or data.get("items") or data.get("groups") or []
    if isinstance(data, list):
        return data
    return []


def upload(file_path: str | Path, group_id: str, display_name: str | None = None) -> str:
    """Upload a local file to a group. Returns the asset id (ta_...).

    Caller is responsible for waiting until the asset is active before
    referencing it in a video request — use wait_active().
    """
    p = Path(file_path)
    with p.open("rb") as fh:
        files = {"file": (p.name, fh)}
        data = {"groupId": group_id, "displayName": display_name or p.stem}
        r = http_client().post("/assets", files=files, data=data)
    r.raise_for_status()
    body = r.json()
    return body.get("assetId") or body["data"]["assetId"]


def get(asset_id: str) -> dict:
    r = http_client().get(f"/assets/{asset_id}")
    r.raise_for_status()
    return r.json()


def wait_active(asset_id: str, timeout: float = 120.0, poll: float = 2.0) -> dict:
    """Poll until status == 'active', or raise on timeout / failure."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = get(asset_id)
        status = (info.get("status") or info.get("data", {}).get("status") or "").lower()
        if status == "active":
            return info
        if status in {"failed", "error", "expired"}:
            raise RuntimeError(f"Asset {asset_id} entered terminal state: {status}")
        time.sleep(poll)
    raise TimeoutError(f"Asset {asset_id} did not become active within {timeout}s")


def ensure_default_group() -> str:
    """Find or create the default GENERIC group used for transparent uploads."""
    for g in list_groups(kind=_DEFAULT_GROUP_KIND):
        if g.get("name") == _DEFAULT_GROUP_NAME:
            return g.get("assetGroupId") or g["id"]
    created = create_group(_DEFAULT_GROUP_NAME, kind=_DEFAULT_GROUP_KIND)
    return created.get("assetGroupId") or created["data"]["assetGroupId"]


def upload_and_wait(file_path: str | Path, group_id: str | None = None) -> str:
    """High-level helper: upload a local file and block until active.

    If group_id is None, uses (creates if needed) the default GENERIC group.
    Returns 'asset://ta_xxx' ready to drop into a video generation request.
    """
    gid = group_id or ensure_default_group()
    asset_id = upload(file_path, gid)
    wait_active(asset_id)
    return f"asset://{asset_id}"


def ensure_handoff_group() -> str:
    """Find or create the default VP group used for handoff-frame uploads.

    Uses VIRTUAL_PORTRAIT so the resulting asset gets a ta_xxx ID accepted by
    /v1/videos `frame_images`. (GENERIC groups produce ua_xxx which is rejected.)
    """
    for g in list_groups(kind=_HANDOFF_GROUP_KIND):
        if g.get("name") == _HANDOFF_GROUP_NAME:
            return g.get("assetGroupId") or g["id"]
    created = create_group(_HANDOFF_GROUP_NAME, kind=_HANDOFF_GROUP_KIND)
    data = created.get("data", created)
    return data.get("assetGroupId") or data.get("id")


def upload_handoff(file_path: str | Path) -> str:
    """Upload a handoff frame to the shared VP group; returns 'asset://ta_xxx'."""
    gid = ensure_handoff_group()
    asset_id = upload(file_path, gid)
    wait_active(asset_id)
    return f"asset://{asset_id}"


# Virtual Portrait: AI-generated character images, no real-person verification.
# Best fit for fully-scripted workflows that want consistent characters.
def setup_virtual_portrait(name: str, image_paths: list[str | Path]) -> list[str]:
    """Create a Virtual Portrait group, upload images, wait for all active.

    Returns a list of 'asset://ta_xxx' URIs ready to use as portrait references.
    """
    group = create_group(name, kind="VIRTUAL_PORTRAIT")
    gid = group.get("assetGroupId") or group["data"]["assetGroupId"]
    uris = []
    for p in image_paths:
        aid = upload(p, gid)
        uris.append(aid)
    for aid in uris:
        wait_active(aid)
    return [f"asset://{aid}" for aid in uris]


# RealFace: real-person verified images. Requires the human to scan an H5
# link / QR within 120s. Scripts cannot complete verification automatically.
def create_real_face_group(name: str) -> tuple[str, str]:
    """Create a RealFace group. Returns (group_id, h5_verification_link).

    Print the link; the real person must open it on a phone within 120s.
    After verification, upload images via upload(file, group_id).
    """
    body = create_group(name, kind="REAL_FACE")
    gid = body.get("assetGroupId") or body["data"]["assetGroupId"]
    h5 = body.get("h5Link") or body.get("data", {}).get("h5Link") or ""
    return gid, h5
