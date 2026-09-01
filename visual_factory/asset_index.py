from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent
DEFAULT_BRAND_DIR = REPO_DIR / "brand-packs" / "example"
DEFAULT_INDEX_PATH = DEFAULT_BRAND_DIR / "asset-index.json"

POSE_ALIASES = {
    "the_answer": ["answer", "hero", "phone"], "the_briefing": ["briefing", "report", "summary"],
    "the_catch": ["catch", "missed", "lead"], "the_lean": ["lean", "casual", "explainer"],
    "the_handoff": ["handoff", "cta", "onboarding"], "the_wave": ["wave", "welcome"],
    "celebration": ["celebration", "win"], "thinking": ["thinking", "analysis"],
    "error_oops": ["error", "oops", "diagnostic"], "waiting": ["waiting", "loading"],
    "after_hours": ["after-hours", "after_hours"], "pointing": ["pointing", "direct"], "og_wide": ["og", "wide"],
}
SUPPORTED_ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_pose(filename: str) -> str:
    stem = re.sub(r"^\d+-", "", Path(filename).stem.lower()).replace("-v2", "")
    return stem.replace("-", "_")


def infer_use_cases(pose: str) -> list[str]:
    uses = {"social", "blog_hero", "og_card"}
    if pose in {"the_answer", "the_briefing", "og_wide", "after_hours"}: uses.update({"linkedin_article_hero", "blog_header"})
    if pose in {"the_catch", "pointing", "the_handoff"}: uses.update({"youtube_thumbnail", "carousel"})
    if pose in {"the_lean", "thinking"}: uses.update({"linkedin_square", "explainer"})
    return sorted(uses)


def infer_emotion(pose: str) -> str:
    if pose in {"the_answer", "the_briefing", "the_lean", "og_wide"}: return "calm_confidence"
    if pose in {"the_catch", "after_hours"}: return "prepared_response"
    if pose in {"the_handoff", "pointing"}: return "direct_invitation"
    if pose == "thinking": return "analysis"
    if pose == "celebration": return "quiet_win"
    return "steady"


def load_brand(brand_dir: Path = DEFAULT_BRAND_DIR) -> dict[str, Any]:
    brand_json = brand_dir / "brand.json"
    if not brand_json.exists():
        raise FileNotFoundError(f"Brand pack is missing brand.json: {brand_json}")
    return json.loads(brand_json.read_text(encoding="utf-8"))


def brand_asset_dir(brand_dir: Path = DEFAULT_BRAND_DIR) -> Path:
    return brand_dir / load_brand(brand_dir).get("asset_dir", "assets")


def _dimensions(path: Path) -> dict[str, int]:
    if path.suffix.lower() == ".svg": return {}
    try:
        with Image.open(path) as image: return {"width": image.width, "height": image.height}
    except (OSError, ValueError): return {}


def _record_path(brand_dir: Path, path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else brand_dir / path


def _declared_assets(brand_dir: Path, brand: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for logo in brand.get("logos", []):
        path = _record_path(brand_dir, logo["path"])
        assets.append({"asset_id": logo["id"], "type": "logo", "path": repo_relative(path), "role": logo["role"],
                       "mode": logo["mode"], "orientation": logo["orientation"], "pose": "", "emotion": "",
                       "use_cases": logo.get("usage", ["all"]), "dimensions": _dimensions(path),
                       "approved": logo.get("approved", True), "source_id": logo.get("source_id", ""),
                       "source_notes": "Typed logo declared by the selected brand variant"})
    for image in brand.get("imagery", []):
        path = _record_path(brand_dir, image["path"])
        assets.append({"asset_id": image["id"], "type": image["type"], "path": repo_relative(path), "role": image["role"],
                       "pose": image.get("pose", ""), "emotion": image.get("emotion", ""),
                       "use_cases": image.get("usage", ["all"]), "dimensions": _dimensions(path),
                       "approved": image.get("approved", True), "source_id": image.get("source_id", ""),
                       "alt_text": image.get("alt_text", ""), "source_notes": "Typed imagery declared by the selected brand variant"})
    return assets


def _infer_legacy_type(file: Path, pose: str) -> str:
    stem = file.stem.lower()
    if any(token in stem for token in ("logo", "logomark", "wordmark", "icon")): return "logo"
    if any(token in stem for token in ("headshot", "portrait", "attorney", "lawyer")): return "headshot"
    if any(token in stem for token in ("podcast", "episode", "cover-art")): return "podcast_artwork"
    if any(token in stem for token in ("ebook", "book-cover")): return "ebook_cover"
    if pose in POSE_ALIASES or any(token in stem for token in ("mascot", "character", "kai-")): return "mascot_pose"
    return "other"


def scan_assets(brand_dir: Path = DEFAULT_BRAND_DIR) -> list[dict[str, Any]]:
    brand = load_brand(brand_dir)
    declared = _declared_assets(brand_dir, brand)
    if declared: return declared
    asset_dir = brand_asset_dir(brand_dir)
    if not asset_dir.exists(): return []
    assets = []
    for file in sorted(p for p in asset_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_ASSET_SUFFIXES):
        pose = normalize_pose(file.name)
        asset_type = _infer_legacy_type(file, pose)
        assets.append({"asset_id": f"{asset_type}-{pose}", "type": asset_type, "path": repo_relative(file),
                       "role": "legacy_unspecified", "pose": pose if asset_type == "mascot_pose" else "",
                       "emotion": infer_emotion(pose) if asset_type == "mascot_pose" else "",
                       "use_cases": infer_use_cases(pose) if asset_type == "mascot_pose" else ["all"],
                       "dimensions": _dimensions(file), "approved": True, "source_id": "", "source_notes": "legacy_inferred"})
    return assets


def write_index(brand_dir: Path = DEFAULT_BRAND_DIR, path: Path | None = None) -> dict[str, Any]:
    path = path or brand_dir / "asset-index.json"
    brand = load_brand(brand_dir)
    manifest = {"brand": brand.get("brand_name", brand.get("name", brand_dir.name)),
                "brand_variant_key": brand.get("brand_variant_key"), "asset_root": repo_relative(brand_asset_dir(brand_dir)),
                "generated_by": "visual_factory.asset_index@0.2.0", "assets": scan_assets(brand_dir)}
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_or_scan(brand_dir: Path = DEFAULT_BRAND_DIR, path: Path | None = None) -> dict[str, Any]:
    path = path or brand_dir / "asset-index.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else write_index(brand_dir, path)


def find_assets(pose: str | None = None, use: str | None = None, brand_dir: Path = DEFAULT_BRAND_DIR, *,
                asset_type: str | None = None, role: str | None = None) -> list[dict[str, Any]]:
    pose_query = pose.lower().replace("-", "_") if pose else None
    use_query = use.lower().replace("-", "_") if use else None
    matches = []
    for asset in load_or_scan(brand_dir).get("assets", []):
        if not asset.get("approved", False) or (asset_type and asset.get("type") != asset_type) or (role and asset.get("role") != role): continue
        aliases = POSE_ALIASES.get(asset.get("pose", ""), [])
        pose_match = not pose_query or pose_query == asset.get("pose") or pose_query in aliases or pose_query in asset.get("asset_id", "")
        uses = [item.lower().replace("-", "_") for item in asset.get("use_cases", [])]
        if pose_match and (not use_query or use_query in uses or "all" in uses): matches.append(asset)
    return matches


def choose_visual_asset(preferred_pose: str | None, template: str, brand_dir: Path = DEFAULT_BRAND_DIR,
                        asset_type: str | None = None, role: str | None = None) -> dict[str, Any]:
    if asset_type or role:
        matches = find_assets(use=template, brand_dir=brand_dir, asset_type=asset_type, role=role) or find_assets(brand_dir=brand_dir, asset_type=asset_type, role=role)
        if matches: return matches[0]
        raise FileNotFoundError(f"No approved asset matches type={asset_type!r}, role={role!r} in {brand_dir}")
    for query in (preferred_pose, template, "the_answer"):
        if query:
            matches = find_assets(query, template, brand_dir, asset_type="mascot_pose") or find_assets(query, brand_dir=brand_dir, asset_type="mascot_pose")
            if matches: return matches[0]
    for fallback_type in ("attorney_portrait", "headshot", "podcast_artwork", "ebook_cover", "photography", "illustration", "other"):
        matches = find_assets(use=template, brand_dir=brand_dir, asset_type=fallback_type) or find_assets(brand_dir=brand_dir, asset_type=fallback_type)
        if matches: return matches[0]
    raise FileNotFoundError(f"No approved imagery found in {brand_dir}")


def choose_mascot(preferred_pose: str | None, template: str, brand_dir: Path = DEFAULT_BRAND_DIR) -> dict[str, Any]:
    return choose_visual_asset(preferred_pose, template, brand_dir, asset_type="mascot_pose")


def proof_stub(claim: str) -> dict[str, Any]:
    return {"proof_id": re.sub(r"[^a-z0-9]+", "-", claim.lower()).strip("-")[:64], "claim": claim,
            "source_type": "manual", "source_path": "Add a verified source_path before publishing.", "verified_by": "pending", "risk": "medium"}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan and query typed brand assets.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser("scan"); scan_parser.add_argument("--brand", type=Path, default=DEFAULT_BRAND_DIR); scan_parser.add_argument("--out", type=Path, default=None)
    find_parser = subparsers.add_parser("find"); find_parser.add_argument("--brand", type=Path, default=DEFAULT_BRAND_DIR); find_parser.add_argument("--pose"); find_parser.add_argument("--use"); find_parser.add_argument("--type", dest="asset_type"); find_parser.add_argument("--role")
    proof_parser = subparsers.add_parser("proof"); proof_parser.add_argument("--claim", required=True)
    args = parser.parse_args(argv)
    if args.command == "scan": data = write_index(args.brand, args.out)
    elif args.command == "find": data = find_assets(args.pose, args.use, args.brand, asset_type=args.asset_type, role=args.role)
    else: data = proof_stub(args.claim)
    print(json.dumps(data, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
