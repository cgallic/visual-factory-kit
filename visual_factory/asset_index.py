from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent
DEFAULT_BRAND_DIR = REPO_DIR / "brand-packs" / "example"
DEFAULT_INDEX_PATH = DEFAULT_BRAND_DIR / "asset-index.json"


POSE_ALIASES = {
    "the_answer": ["answer", "hero", "phone"],
    "the_briefing": ["briefing", "report", "summary"],
    "the_catch": ["catch", "missed", "lead"],
    "the_lean": ["lean", "casual", "explainer"],
    "the_handoff": ["handoff", "cta", "onboarding"],
    "the_wave": ["wave", "welcome"],
    "celebration": ["celebration", "win"],
    "thinking": ["thinking", "analysis"],
    "error_oops": ["error", "oops", "diagnostic"],
    "waiting": ["waiting", "loading"],
    "after_hours": ["after-hours", "after_hours"],
    "pointing": ["pointing", "direct"],
    "og_wide": ["og", "wide"],
}


@dataclass
class VisualAsset:
    asset_id: str
    type: str
    path: str
    pose: str
    emotion: str
    use_cases: list[str]
    dimensions: dict[str, int]
    approved: bool
    source_notes: str


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_pose(filename: str) -> str:
    stem = Path(filename).stem.lower()
    stem = re.sub(r"^\d+-", "", stem)
    stem = stem.replace("-v2", "")
    stem = stem.replace("-", "_")
    return stem


def infer_use_cases(pose: str) -> list[str]:
    use_cases = {"social", "blog_hero", "og_card"}
    if pose in {"the_answer", "the_briefing", "og_wide", "after_hours"}:
        use_cases.update({"linkedin_article_hero", "blog_header"})
    if pose in {"the_catch", "pointing", "the_handoff"}:
        use_cases.update({"youtube_thumbnail", "carousel"})
    if pose in {"the_lean", "thinking"}:
        use_cases.update({"linkedin_square", "explainer"})
    return sorted(use_cases)


def infer_emotion(pose: str) -> str:
    if pose in {"the_answer", "the_briefing", "the_lean", "og_wide"}:
        return "calm_confidence"
    if pose in {"the_catch", "after_hours"}:
        return "prepared_response"
    if pose in {"the_handoff", "pointing"}:
        return "direct_invitation"
    if pose == "thinking":
        return "analysis"
    if pose == "celebration":
        return "quiet_win"
    return "steady"


def load_brand(brand_dir: Path = DEFAULT_BRAND_DIR) -> dict:
    brand_json = brand_dir / "brand.json"
    if not brand_json.exists():
        raise FileNotFoundError(f"Brand pack is missing brand.json: {brand_json}")
    return json.loads(brand_json.read_text(encoding="utf-8"))


def brand_asset_dir(brand_dir: Path = DEFAULT_BRAND_DIR) -> Path:
    brand = load_brand(brand_dir)
    return brand_dir / brand.get("asset_dir", "assets")


def scan_assets(brand_dir: Path = DEFAULT_BRAND_DIR) -> list[VisualAsset]:
    assets: list[VisualAsset] = []
    asset_dir = brand_asset_dir(brand_dir)
    if not asset_dir.exists():
        return assets

    for file in sorted(asset_dir.glob("*.png")):
        pose = normalize_pose(file.name)
        with Image.open(file) as image:
            width, height = image.size
        asset = VisualAsset(
            asset_id=f"kai-pose-{pose}",
            type="mascot_pose",
            path=repo_relative(file),
            pose=pose,
            emotion=infer_emotion(pose),
            use_cases=infer_use_cases(pose),
            dimensions={"width": width, "height": height},
            approved=True,
            source_notes="Approved transparent brand visual asset",
        )
        assets.append(asset)

    return assets


def write_index(brand_dir: Path = DEFAULT_BRAND_DIR, path: Path | None = None) -> dict:
    path = path or brand_dir / "asset-index.json"
    manifest = {
        "brand": load_brand(brand_dir).get("name", brand_dir.name),
        "asset_root": repo_relative(brand_asset_dir(brand_dir)),
        "generated_by": "kai_asset_index.py",
        "assets": [asdict(asset) for asset in scan_assets(brand_dir)],
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_or_scan(brand_dir: Path = DEFAULT_BRAND_DIR, path: Path | None = None) -> dict:
    path = path or brand_dir / "asset-index.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return write_index(brand_dir, path)


def find_assets(pose: str | None = None, use: str | None = None, brand_dir: Path = DEFAULT_BRAND_DIR) -> list[dict]:
    pose_query = pose.lower().replace("-", "_") if pose else None
    use_query = use.lower().replace("-", "_") if use else None
    assets = load_or_scan(brand_dir).get("assets", [])
    matches = []
    for asset in assets:
        if asset.get("type") != "mascot_pose":
            continue
        aliases = POSE_ALIASES.get(asset.get("pose", ""), [])
        pose_match = (
            not pose_query
            or pose_query == asset.get("pose")
            or pose_query in aliases
            or pose_query in asset.get("asset_id", "")
        )
        use_match = (
            not use_query
            or use_query in [item.lower().replace("-", "_") for item in asset.get("use_cases", [])]
            or "all" in asset.get("use_cases", [])
        )
        if pose_match and use_match:
            matches.append(asset)
    return matches


def choose_mascot(preferred_pose: str | None, template: str, brand_dir: Path = DEFAULT_BRAND_DIR) -> dict:
    for query in [preferred_pose, template, "the_answer"]:
        if not query:
            continue
        matches = find_assets(pose=query, use=template, brand_dir=brand_dir) or find_assets(pose=query, brand_dir=brand_dir)
        if matches:
            return matches[0]
    matches = find_assets(brand_dir=brand_dir)
    if not matches:
        raise FileNotFoundError(f"No approved transparent PNGs found in {brand_asset_dir(brand_dir)}")
    return matches[0]


def proof_stub(claim: str) -> dict:
    return {
        "proof_id": re.sub(r"[^a-z0-9]+", "-", claim.lower()).strip("-")[:64],
        "claim": claim,
        "source_type": "manual",
        "source_path": "Add a verified source_path before publishing.",
        "verified_by": "pending",
        "risk": "medium",
    }


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan and query approved transparent brand visual assets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Build the local visual asset index.")
    scan_parser.add_argument("--brand", type=Path, default=DEFAULT_BRAND_DIR)
    scan_parser.add_argument("--out", type=Path, default=None)

    find_parser = subparsers.add_parser("find", help="Find approved mascot assets.")
    find_parser.add_argument("--brand", type=Path, default=DEFAULT_BRAND_DIR)
    find_parser.add_argument("--pose", default=None)
    find_parser.add_argument("--use", default=None)

    proof_parser = subparsers.add_parser("proof", help="Create a proof-record stub for a claim.")
    proof_parser.add_argument("--claim", required=True)

    args = parser.parse_args(argv)
    if args.command == "scan":
        print_json(write_index(args.brand, args.out))
    elif args.command == "find":
        print_json(find_assets(args.pose, args.use, args.brand))
    elif args.command == "proof":
        print_json(proof_stub(args.claim))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
