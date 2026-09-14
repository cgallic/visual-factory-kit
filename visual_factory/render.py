from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape
from jsonschema import Draft202012Validator
from PIL import Image
from playwright.sync_api import sync_playwright

from asset_index import DEFAULT_BRAND_DIR, REPO_DIR, choose_visual_asset, load_brand


RENDERER_VERSION = "visual_factory_renderer@0.2.0"
VISUALS_DIR = Path(__file__).resolve().parent
SCHEMA_DIR = VISUALS_DIR / "schemas"
TEMPLATE_DIR = VISUALS_DIR / "templates"
FONT_DIR = VISUALS_DIR / "fonts"
PLATFORM_SIZE_MATRIX = VISUALS_DIR / "platform-size-matrix.json"

PLATFORM_SPECS = json.loads(PLATFORM_SIZE_MATRIX.read_text(encoding="utf-8"))
TEMPLATE_SIZES = {
    name: (spec["width"], spec["height"])
    for name, spec in PLATFORM_SPECS.items()
}

REQUIRED_TEMPLATE_ASSETS = {
    "attorney_profile_landscape": {"attorney_portrait"},
    "attorney_ebook_landscape": {"attorney_portrait", "ebook_cover"},
}

BANNED_PUBLIC_TERMS = [
    "ai assistant",
    "voice bot",
    "agent",
    "never miss a call",
    "game-changer",
    "seamless",
]

MOBILE_PREVIEW_WIDTH = 360
MOBILE_READABILITY_MINIMUMS = {
    "headline": 16,
    "subhead": 7,
    "proof": 7,
    "phone": 8,
    "cta": 8,
    "local-note": 5,
    "pin-tag": 5,
    "interface-headline": 5,
    "interface-body": 4,
    "interface-proof": 4,
    "diagram-headline": 8,
    "diagram-label": 4,
    "diagram-proof": 4,
    "timeline-headline": 7,
    "timeline-proof": 4,
}

FONT_FILES = {
    "Kai Display": [
        (700, "LibreFranklin-Bold.ttf"),
        (800, "LibreFranklin-ExtraBold.ttf"),
        (900, "LibreFranklin-Black.ttf"),
    ],
    "Kai Body": [
        (400, "AtkinsonHyperlegible-Regular.ttf"),
        (700, "AtkinsonHyperlegible-Bold.ttf"),
    ],
    "Kai Mono": [
        (500, "IBMPlexMono-Medium.ttf"),
        (700, "IBMPlexMono-Bold.ttf"),
    ],
}


def repo_root() -> Path:
    return REPO_DIR


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root()).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def validate(schema_name: str, data: dict[str, Any]) -> None:
    schema = load_json(SCHEMA_DIR / schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda error: error.path)
    if errors:
        message = "\n".join(f"- {'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors)
        raise ValueError(f"{schema_name} validation failed:\n{message}")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "kai-visual"


def as_file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return repo_root() / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_brand_variant(brand_dir: Path, requested_key: str) -> tuple[dict[str, Any], bool]:
    brand = load_brand(brand_dir)
    declared_key = brand.get("brand_variant_key")
    if declared_key:
        validate("brand-pack.schema.json", brand)
        if requested_key != declared_key:
            raise ValueError(
                f"Requested brand variant {requested_key!r} does not match pack {declared_key!r}; "
                "cross-surface fallback is forbidden"
            )
        return brand, False
    safe_legacy_keys = {"legacy", brand_dir.name.lower()}
    if requested_key not in safe_legacy_keys:
        raise ValueError(
            f"Legacy brand pack {brand_dir.name!r} has no brand_variant_key. "
            f"Use one of {sorted(safe_legacy_keys)!r} explicitly or migrate the pack."
        )
    return brand, True


def brand_file(brand_dir: Path, path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else brand_dir / path


def declared_font_assets(brand_dir: Path, brand: dict[str, Any]) -> list[dict[str, Any]]:
    declared = []
    for family in brand.get("typography", {}).get("families", []):
        for asset in family.get("asset_files", []):
            declared.append({"family": family["family"], **asset, "resolved_path": brand_file(brand_dir, asset["path"])})
    if declared:
        return declared
    # Compatibility is explicit at the variant-selection gate; these are the historical bundled fonts.
    return [
        {
            "family": family,
            "weight": weight,
            "style": "normal",
            "format": "truetype",
            "license": {"name": "See visual_factory/fonts/NOTICE.md"},
            "path": f"visual_factory/fonts/{filename}",
            "resolved_path": FONT_DIR / filename,
        }
        for family, files in FONT_FILES.items()
        for weight, filename in files
    ]


def load_font_css(brand_dir: Path, brand: dict[str, Any]) -> str:
    blocks = []
    for asset in declared_font_assets(brand_dir, brand):
        path = asset["resolved_path"]
        if not path.exists():
            raise FileNotFoundError(f"Declared brand font is missing: {path}")
        blocks.append(
            "\n".join(
                [
                    "@font-face {",
                    f"  font-family: '{asset['family']}';",
                    f"  font-style: {asset['style']};",
                    f"  font-weight: {asset['weight']};",
                    "  font-display: block;",
                    f"  src: url('{as_file_uri(path)}') format('{asset['format']}');",
                    "}",
                ]
            )
        )
    return "\n\n".join(blocks)


def public_text_chunks(request: dict[str, Any]) -> list[str]:
    message = request.get("message", {})
    chunks = [
        message.get("headline", ""),
        message.get("subhead", ""),
        message.get("supporting_copy", ""),
        message.get("proof_label", ""),
        message.get("cta", ""),
        request.get("output", {}).get("alt_text", ""),
    ]
    chunks.extend(proof.get("claim", "") for proof in request.get("proof", []))
    return [chunk for chunk in chunks if chunk]


def find_banned_terms(request: dict[str, Any]) -> list[str]:
    text = " ".join(public_text_chunks(request)).lower()
    return sorted({term for term in BANNED_PUBLIC_TERMS if term in text})


def proof_display(request: dict[str, Any]) -> dict[str, str]:
    proof_items = request.get("proof", [])
    proof = proof_items[0] if proof_items else {}
    message = request.get("message", {})
    return {
        "claim": message.get("proof_label") or proof.get("claim", ""),
        "source_path": proof.get("source_path", ""),
        "source_type": proof.get("source_type", "manual"),
    }


def brand_path(brand_dir: Path, path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else brand_dir / path


def selected_logo(brand: dict[str, Any], direction: dict[str, Any] | None = None) -> dict[str, Any] | None:
    logos = [logo for logo in brand.get("logos", []) if logo.get("approved", True)]
    direction = direction or {}
    selectors = {"id": direction.get("logo_id"), "role": direction.get("logo_role"),
                 "mode": direction.get("logo_mode"), "orientation": direction.get("logo_orientation")}
    requested = {key: value for key, value in selectors.items() if value}
    if requested:
        match = next((logo for logo in logos if all(logo.get(key) == value for key, value in requested.items())), None)
        if not match:
            raise ValueError(f"No approved logo matches exact selection {requested!r} in the selected brand variant")
        return match
    for role in ("icon", "logomark", "primary", "wordmark"):
        match = next((logo for logo in logos if logo.get("role") == role), None)
        if match:
            return match
    return logos[0] if logos else None


def tokens_file(brand_dir: Path, brand: dict[str, Any]) -> Path:
    path_text = brand.get("tokens", {}).get("css_file") or brand.get("tokens_css", "tokens.css")
    return brand_path(brand_dir, path_text)


def resolve_template_asset_uris(template_name: str, template_data: dict[str, Any], brand_dir: Path) -> dict[str, str]:
    assets = template_data.get("assets", {})
    if not isinstance(assets, dict):
        raise ValueError("template_data.assets must be an object of named brand-pack paths")
    missing = sorted(name for name in REQUIRED_TEMPLATE_ASSETS.get(template_name, set()) if not assets.get(name))
    if missing:
        raise ValueError(f"{template_name} requires template_data.assets: {', '.join(missing)}")
    brand_root = brand_dir.resolve()
    resolved = {}
    for name, path_text in assets.items():
        if not isinstance(name, str) or not isinstance(path_text, str) or not path_text.strip():
            raise ValueError("template_data.assets keys and values must be non-empty strings")
        asset_path = brand_path(brand_dir, path_text).resolve()
        try:
            asset_path.relative_to(brand_root)
        except ValueError as exc:
            raise ValueError(f"template asset must stay inside the brand pack: {name}") from exc
        if not asset_path.is_file():
            raise FileNotFoundError(f"template asset not found: {name} -> {asset_path}")
        resolved[name] = as_file_uri(asset_path)
    return resolved


def template_context(
    request: dict[str, Any],
    template_name: str,
    mascot_asset: dict[str, Any],
    brand_dir: Path,
    brand: dict[str, Any],
) -> dict[str, Any]:
    width, height = TEMPLATE_SIZES[template_name]
    message = request["message"]
    template_data = request.get("template_data", {})
    if not isinstance(template_data, dict):
        raise ValueError("template_data must be an object")
    proof = proof_display(request)
    mascot_path = resolve_path(mascot_asset["path"])
    subhead = message.get("subhead") or message.get("supporting_copy") or ""
    cta = message.get("cta") or "Just call Kai."
    phone_number = message.get("phone_number") or brand.get("phone_number", "")
    phone_label = message.get("phone_label") or brand.get("phone_label", "")
    logo = selected_logo(brand, request.get("visual_direction", {}))
    icon_path = brand_path(brand_dir, logo["path"] if logo else brand.get("icon", "assets/icon.png"))
    tokens_path = tokens_file(brand_dir, brand)
    return {
        "width": width,
        "height": height,
        "scale_landscape": min(width / 1200, height / 630),
        "scale_square": width / 1080,
        "scale_portrait": min(width / 1080, height / 1350),
        "scale_vertical": min(width / 1080, height / 1920),
        "template_name": template_name,
        "client": request.get("client", brand.get("name", "")),
        "brand_name": brand.get("name", request.get("client", "")),
        "content_id": request.get("content_id", ""),
        "topic": request.get("topic", ""),
        "headline": message["headline"],
        "subhead": subhead,
        "proof_label": proof["claim"],
        "proof_source": proof["source_path"],
        "proof_source_type": proof["source_type"],
        "cta": cta,
        "phone_number": phone_number,
        "phone_label": phone_label,
        "alt_text": request["output"]["alt_text"],
        "mascot_pose": mascot_asset.get("pose", ""),
        "visual_asset_type": mascot_asset.get("type", "other"),
        "visual_asset_role": mascot_asset.get("role", ""),
        "mascot_path": mascot_asset["path"],
        "mascot_uri": as_file_uri(mascot_path),
        "brand_icon_uri": as_file_uri(icon_path),
        "brand_lockup_uri": as_file_uri(icon_path),
        "tokens_css": tokens_path.read_text(encoding="utf-8"),
        "font_css": load_font_css(brand_dir, brand),
        "shared_css": (TEMPLATE_DIR / "shared.css").read_text(encoding="utf-8"),
        "template_data": template_data,
        "template_asset_uris": resolve_template_asset_uris(template_name, template_data, brand_dir),
        "format_spec": PLATFORM_SPECS.get(template_name, {}),
    }


def render_html(context: dict[str, Any], template_name: str) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template_file = PLATFORM_SPECS.get(template_name, {}).get("template_file", template_name)
    template = env.get_template(f"{template_file}.html")
    return template.render(**context)


def browser_text_overflow(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll('[data-fit]')).map((el) => {
          const style = window.getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          const maxHeight = Number.parseFloat(style.maxHeight);
          const hasMaxHeight = Number.isFinite(maxHeight);
          const canvas = document.querySelector('.canvas').getBoundingClientRect();
          const realOverflowX = el.scrollWidth > el.clientWidth + 2;
          const realOverflowY = hasMaxHeight && el.scrollHeight > maxHeight + 2;
          const escapesCanvas = rect.left < canvas.left - 1 ||
                                rect.top < canvas.top - 1 ||
                                rect.right > canvas.right + 1 ||
                                rect.bottom > canvas.bottom + 1;
          return {
            label: el.getAttribute('data-fit'),
            text: el.textContent.trim(),
            overflowX: realOverflowX,
            overflowY: realOverflowY,
            escapesCanvas,
            clientWidth: el.clientWidth,
            clientHeight: el.clientHeight,
            scrollWidth: el.scrollWidth,
            scrollHeight: el.scrollHeight,
            maxHeight: hasMaxHeight ? maxHeight : null,
            fontSize: style.fontSize
          };
        }).filter((item) => item.overflowX || item.overflowY || item.escapesCanvas)
        """
    )


def browser_text_metrics(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll('[data-fit]')).map((el) => {
          const measured = el.getAttribute('data-fit') === 'phone'
            ? (el.querySelector('.number') || el)
            : el;
          const style = window.getComputedStyle(measured);
          const rect = el.getBoundingClientRect();
          const measuredRect = measured.getBoundingClientRect();
          const transformScale = measured.offsetWidth
            ? measuredRect.width / measured.offsetWidth
            : 1;
          const renderedFontSize = Number.parseFloat(style.fontSize) * transformScale;
          const rawFinalFontSize = Number.parseFloat(measured.getAttribute('data-final-font-size') || style.fontSize);
          return {
            label: el.getAttribute('data-fit'),
            text: el.textContent.trim(),
            fontSize: renderedFontSize,
            finalFontSize: rawFinalFontSize * transformScale,
            width: rect.width,
            height: rect.height
          };
        })
        """
    )


def fit_text_blocks(page) -> None:
    page.evaluate(
        """
        () => {
          const canvas = document.querySelector('.canvas').getBoundingClientRect();
          const fits = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            const maxHeight = Number.parseFloat(style.maxHeight);
            const hasMaxHeight = Number.isFinite(maxHeight);
            const overX = el.scrollWidth > el.clientWidth + 2;
            const overY = hasMaxHeight && el.scrollHeight > maxHeight + 2;
            const escapes = rect.left < canvas.left - 1 ||
                            rect.top < canvas.top - 1 ||
                            rect.right > canvas.right + 1 ||
                            rect.bottom > canvas.bottom + 1;
            return !(overX || overY || escapes);
          };

          for (const el of document.querySelectorAll('[data-fit]')) {
            const style = window.getComputedStyle(el);
            const minSize = Number.parseFloat(el.getAttribute('data-min-font-size') || '12');
            let size = Number.parseFloat(style.fontSize);
            let guard = 0;
            while (!fits(el) && size > minSize && guard < 60) {
              size -= 1;
              el.style.fontSize = `${size}px`;
              guard += 1;
            }
            el.setAttribute('data-final-font-size', `${size}px`);
          }
        }
        """
    )


def render_png(html: str, output_path: Path, width: int, height: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kai-visual-") as tmpdir:
        html_path = Path(tmpdir) / "render.html"
        html_path.write_text(html, encoding="utf-8")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            fit_text_blocks(page)
            overflow = browser_text_overflow(page)
            text_metrics = browser_text_metrics(page)
            page.screenshot(path=str(output_path), full_page=False, omit_background=False)
            browser.close()
    return overflow, text_metrics


def build_provenance(
    request: dict[str, Any],
    template_name: str,
    output_path: Path,
    mascot_asset: dict[str, Any],
    brand_dir: Path,
    brand: dict[str, Any],
    legacy_compatibility: bool,
) -> dict[str, Any]:
    width, height = TEMPLATE_SIZES[template_name]
    proof_items = request.get("proof", [])
    ingredients = [
        {
            "kind": "platform_size_matrix",
            "path": repo_relative(PLATFORM_SIZE_MATRIX),
            "source": "Platform export matrix",
        },
        {
            "kind": "brand_visual_asset",
            "path": mascot_asset["path"],
            "source": "approved transparent brand asset",
        },
        {
            "kind": "brand_tokens",
            "path": repo_relative(tokens_file(brand_dir, brand)),
            "source": "brand design tokens",
        },
        {
            "kind": "typography",
            "path": repo_relative(FONT_DIR),
            "source": "Bundled open-source visual font stack",
            "families": sorted({asset["family"] for asset in declared_font_assets(brand_dir, brand)}),
        },
    ]
    for source in brand.get("sources", []):
        ingredients.append({"kind": "brand_source", "source": source.get("provider", ""), "source_id": source.get("id", ""),
                            "source_path": source.get("source_url") or source.get("source_file", "")})
    for proof in proof_items:
        ingredients.append(
            {
                "kind": "proof",
                "claim": proof.get("claim", ""),
                "source_path": proof.get("source_path", ""),
                "source": proof.get("source_type", "manual"),
            }
        )

    catalog_path = brand_dir / "brand.json"
    font_assets = [
        {
            "family": asset["family"], "weight": asset["weight"], "style": asset["style"],
            "license": asset["license"]["name"], "path": repo_relative(asset["resolved_path"]),
            "sha256": sha256_file(asset["resolved_path"]),
        }
        for asset in declared_font_assets(brand_dir, brand)
    ]
    hash_candidates = [("brand_visual_asset", mascot_asset.get("asset_id", ""), resolve_path(mascot_asset["path"])),
                       ("brand_tokens", "tokens", tokens_file(brand_dir, brand))]
    logo = selected_logo(brand, request.get("visual_direction", {}))
    if logo:
        hash_candidates.append(("logo", logo["id"], brand_path(brand_dir, logo["path"])))
    else:
        hash_candidates.append(("logo", "legacy-icon", brand_path(brand_dir, brand.get("icon", "assets/icon.png"))))
    asset_hashes = []
    seen_paths = set()
    for kind, asset_id, path in hash_candidates:
        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        if not resolved.exists():
            raise FileNotFoundError(f"Declared provenance asset is missing: {resolved}")
        seen_paths.add(resolved)
        asset_hashes.append({"kind": kind, "asset_id": asset_id, "path": repo_relative(resolved), "sha256": sha256_file(resolved)})

    return {
        "asset_id": output_path.stem,
        "request_id": request["request_id"],
        "content_id": request.get("content_id", ""),
        "rendered_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "renderer": RENDERER_VERSION,
        "template": f"{template_name}@1.0.0",
        "brand_variant": {
            "key": request["brand_variant_key"],
            "site_kind": brand.get("site", {}).get("kind", "legacy"),
            "site_key": brand.get("site", {}).get("key", brand_dir.name),
            "catalog_path": repo_relative(catalog_path),
            "catalog_sha256": sha256_file(catalog_path),
            "legacy_compatibility": legacy_compatibility,
        },
        "font_assets": font_assets,
        "asset_hashes": asset_hashes,
        "dimensions": {"width": width, "height": height},
        "alt_text": request["output"]["alt_text"],
        "ingredients": ingredients,
        "ai_assistance": {
            "copy_assisted": True,
            "image_generated_new_for_this_asset": False,
            "notes": "Final image assembled from approved brand layers, deterministic HTML/CSS templates, and request proof fields.",
        },
        "approvals": {
            "brand": "pending",
            "claims": "verified" if request.get("compliance", {}).get("claims_verified") else "pending",
        },
    }


def qa_for_output(
    request: dict[str, Any],
    template_name: str,
    output_path: Path,
    provenance_path: Path,
    overflow: list[dict[str, Any]],
    text_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_width, expected_height = TEMPLATE_SIZES[template_name]
    with Image.open(output_path) as image:
        actual_width, actual_height = image.size
    proof_items = request.get("proof", [])
    proof_source_missing = [
        proof.get("claim", "")
        for proof in proof_items
        if not str(proof.get("source_path", "")).strip()
    ]
    preview_scale = MOBILE_PREVIEW_WIDTH / expected_width
    mobile_readability = []
    for metric in text_metrics:
        label = metric["label"]
        minimum = MOBILE_READABILITY_MINIMUMS.get(label, 6)
        effective_size = metric["finalFontSize"] * preview_scale
        mobile_readability.append(
            {
                "label": label,
                "font_size": round(metric["finalFontSize"], 2),
                "mobile_preview_font_size": round(effective_size, 2),
                "minimum_mobile_font_size": minimum,
                "passed": effective_size + 0.25 >= minimum,
            }
        )
    checks = {
        "dimensions_match": actual_width == expected_width and actual_height == expected_height,
        "text_overflow": len(overflow) == 0,
        "mobile_readability": all(item["passed"] for item in mobile_readability),
        "alt_text_present": bool(request.get("output", {}).get("alt_text", "").strip()),
        "proof_source_present": len(proof_source_missing) == 0,
        "provenance_sidecar_present": provenance_path.exists(),
        "banned_public_terms_absent": len(find_banned_terms(request)) == 0,
    }
    return {
        "template": template_name,
        "output_path": repo_relative(output_path),
        "expected_dimensions": {"width": expected_width, "height": expected_height},
        "actual_dimensions": {"width": actual_width, "height": actual_height},
        "checks": checks,
        "overflow": overflow,
        "text_metrics": text_metrics,
        "mobile_preview": {
            "preview_width": MOBILE_PREVIEW_WIDTH,
            "scale": round(preview_scale, 4),
            "readability": mobile_readability,
        },
        "missing_proof_sources": proof_source_missing,
        "banned_public_terms": find_banned_terms(request),
        "passed": all(checks.values()),
    }


def render_request(request_path: Path, brand_dir: Path = DEFAULT_BRAND_DIR) -> dict[str, Any]:
    request = load_json(request_path)
    validate("visual-request.schema.json", request)
    brand_dir = brand_dir.resolve()
    brand, legacy_compatibility = load_brand_variant(brand_dir, request["brand_variant_key"])
    allowed_templates = set(brand.get("templates", {}).get("allowed", []))
    if allowed_templates:
        disallowed = sorted(set(request["formats"]) - allowed_templates)
        if disallowed:
            raise ValueError(f"Templates not approved for brand variant {request['brand_variant_key']!r}: {disallowed}")

    destination_dir = resolve_path(request["output"]["destination_dir"])
    destination_dir.mkdir(parents=True, exist_ok=True)
    prefix = request["output"].get("filename_prefix") or slugify(request["content_id"])

    qa_results = []
    rendered_assets = []
    preferred_pose = request.get("visual_direction", {}).get("preferred_pose")
    preferred_asset_type = request.get("visual_direction", {}).get("asset_type")
    preferred_asset_role = request.get("visual_direction", {}).get("asset_role")

    for template_name in request["formats"]:
        mascot_asset = choose_visual_asset(preferred_pose, template_name, brand_dir, preferred_asset_type, preferred_asset_role)
        context = template_context(request, template_name, mascot_asset, brand_dir, brand)
        html = render_html(context, template_name)

        png_path = destination_dir / f"{prefix}-{template_name}.png"
        width, height = TEMPLATE_SIZES[template_name]
        overflow, text_metrics = render_png(html, png_path, width, height)

        provenance = build_provenance(request, template_name, png_path, mascot_asset, brand_dir, brand, legacy_compatibility)
        validate("provenance.schema.json", provenance)
        provenance_path = png_path.with_suffix(".provenance.json")
        write_json(provenance_path, provenance)

        qa = qa_for_output(request, template_name, png_path, provenance_path, overflow, text_metrics)
        qa_results.append(qa)
        rendered_assets.append(
            {
                "template": template_name,
                "png": repo_relative(png_path),
                "provenance": repo_relative(provenance_path),
                "passed_qa": qa["passed"],
            }
        )

    report = {
        "request_id": request["request_id"],
        "content_id": request.get("content_id", ""),
        "rendered_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "renderer": RENDERER_VERSION,
        "brand_variant_key": request["brand_variant_key"],
        "assets": rendered_assets,
        "qa": qa_results,
        "passed": all(item["passed"] for item in qa_results),
    }
    report_path = destination_dir / f"{prefix}-qa-report.json"
    write_json(report_path, report)
    report["qa_report_path"] = repo_relative(report_path)
    return report


def audit_asset(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
    provenance_path = path.with_suffix(".provenance.json")
    return {
        "asset": repo_relative(path),
        "dimensions": {"width": width, "height": height},
        "provenance_sidecar_present": provenance_path.exists(),
        "provenance_path": repo_relative(provenance_path),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render deterministic static visual templates.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="Render PNG assets from a visual request JSON.")
    render_parser.add_argument("--request", required=True, type=Path)
    render_parser.add_argument("--brand", type=Path, default=DEFAULT_BRAND_DIR)

    audit_parser = subparsers.add_parser("audit", help="Inspect an exported asset and sidecar presence.")
    audit_parser.add_argument("--asset", required=True, type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "render":
            print(json.dumps(render_request(args.request, args.brand), indent=2))
        elif args.command == "audit":
            print(json.dumps(audit_asset(args.asset), indent=2))
    except Exception as exc:
        print(f"visual_factory.render: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
