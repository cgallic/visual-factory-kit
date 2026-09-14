import json
import sys
from pathlib import Path

import pytest
from PIL import Image

TEST_PARENT = Path(__file__).resolve().parents[1]
VISUAL_FACTORY = TEST_PARENT if (TEST_PARENT / "render.py").exists() else TEST_PARENT / "visual_factory"
sys.path.insert(0, str(VISUAL_FACTORY))

import asset_index  # noqa: E402
import render  # noqa: E402


def write_pack(tmp_path: Path, key: str = "firm-main") -> Path:
    pack = tmp_path / key
    (pack / "assets").mkdir(parents=True)
    (pack / "fonts").mkdir()
    Image.new("RGBA", (40, 40), (255, 0, 0, 255)).save(pack / "assets" / "logo.png")
    Image.new("RGBA", (80, 120), (0, 0, 255, 255)).save(pack / "assets" / "attorney.png")
    (pack / "fonts" / "Firm-Regular.ttf").write_bytes(b"declared-font")
    (pack / "tokens.css").write_text(":root { --brand-primary: #112233; }", encoding="utf-8")
    brand = {
        "schema_version": "1.0", "brand_variant_key": key, "brand_name": "Example Firm",
        "site": {"kind": "attorney_site", "key": "main", "client_key": "example-firm"},
        "palette": {"primary": {"name": "navy", "value": "#112233"}, "secondary": {"name": "white", "value": "#ffffff"}},
        "tokens": {"css_file": "tokens.css", "values": {"radius": 4}},
        "typography": {"families": [{"key": "body", "family": "Firm Sans", "role": "body", "fallbacks": ["sans-serif"],
                                             "asset_files": [{"path": "fonts/Firm-Regular.ttf", "weight": 400, "style": "normal", "format": "truetype", "license": {"name": "Client supplied"}}]}]},
        "logos": [{"id": "logo-primary", "path": "assets/logo.png", "role": "primary", "mode": "full_color", "orientation": "horizontal", "approved": True, "source_id": "figma-logo"}],
        "imagery": [{"id": "attorney-jane", "path": "assets/attorney.png", "type": "attorney_portrait", "role": "lead_attorney", "approved": True, "usage": ["social_square"], "source_id": "drive-photo"}],
        "templates": {"allowed": ["linkedin_square"]},
        "sources": [{"id": "figma-logo", "provider": "figma", "source_url": "https://www.figma.com/file/example", "retrieved_at": "2026-09-01T00:00:00Z"}],
    }
    (pack / "brand.json").write_text(json.dumps(brand), encoding="utf-8")
    return pack


def valid_request(key: str = "firm-main") -> dict:
    return {
        "request_id": "req-1", "client": "Example Firm", "brand_variant_key": key, "content_id": "content-1",
        "formats": ["linkedin_square"], "message": {"headline": "A useful legal headline"},
        "proof": [{"claim": "Verified", "source_path": "source.md"}],
        "output": {"alt_text": "Example attorney branded visual", "destination_dir": "outputs"},
    }


def test_request_requires_explicit_brand_variant_key():
    request = valid_request()
    del request["brand_variant_key"]
    with pytest.raises(ValueError, match="brand_variant_key"):
        render.validate("visual-request.schema.json", request)


def test_variant_mismatch_never_falls_back(tmp_path):
    pack = write_pack(tmp_path)
    with pytest.raises(ValueError, match="cross-surface fallback is forbidden"):
        render.load_brand_variant(pack, "podcast-main")


def test_declared_fonts_are_loaded_and_hashed(tmp_path):
    pack = write_pack(tmp_path)
    brand, legacy = render.load_brand_variant(pack, "firm-main")
    assert legacy is False
    css = render.load_font_css(pack, brand)
    assert "font-family: 'Firm Sans'" in css
    assert (pack / "fonts" / "Firm-Regular.ttf").resolve().as_uri() in css
    assets = render.declared_font_assets(pack, brand)
    assert render.sha256_file(assets[0]["resolved_path"])


def test_typed_index_preserves_attorney_and_logo_roles(tmp_path):
    pack = write_pack(tmp_path)
    assets = asset_index.scan_assets(pack)
    assert {(item["type"], item["role"]) for item in assets} == {("logo", "primary"), ("attorney_portrait", "lead_attorney")}
    chosen = asset_index.choose_visual_asset(None, "linkedin_square", pack, "attorney_portrait", "lead_attorney")
    assert chosen["asset_id"] == "attorney-jane"


def test_logo_selection_is_exact_and_never_guesses_another_role(tmp_path):
    pack = write_pack(tmp_path)
    brand, _ = render.load_brand_variant(pack, "firm-main")
    assert render.selected_logo(brand, {"logo_id": "logo-primary"})["id"] == "logo-primary"
    with pytest.raises(ValueError, match="No approved logo matches exact selection"):
        render.selected_logo(brand, {"logo_role": "podcast"})


def test_provenance_binds_variant_catalog_fonts_and_assets(tmp_path):
    pack = write_pack(tmp_path)
    brand, legacy = render.load_brand_variant(pack, "firm-main")
    request = valid_request()
    image = asset_index.choose_visual_asset(None, "linkedin_square", pack, "attorney_portrait", "lead_attorney")
    provenance = render.build_provenance(request, "linkedin_square", tmp_path / "out.png", image, pack, brand, legacy)
    render.validate("provenance.schema.json", provenance)
    assert provenance["brand_variant"]["key"] == "firm-main"
    assert provenance["brand_variant"]["catalog_sha256"] == render.sha256_file(pack / "brand.json")
    assert provenance["font_assets"][0]["sha256"] == render.sha256_file(pack / "fonts" / "Firm-Regular.ttf")
    assert {item["kind"] for item in provenance["asset_hashes"]} == {"brand_visual_asset", "brand_tokens", "logo"}
    assert next(item for item in provenance["asset_hashes"] if item["kind"] == "logo")["asset_id"] == "logo-primary"


def test_legacy_scan_does_not_call_every_png_a_mascot(tmp_path):
    pack = tmp_path / "legacy"
    (pack / "assets").mkdir(parents=True)
    Image.new("RGB", (10, 10)).save(pack / "assets" / "courthouse-photo.png")
    Image.new("RGB", (10, 10)).save(pack / "assets" / "the-answer.png")
    (pack / "brand.json").write_text(json.dumps({"name": "Legacy", "asset_dir": "assets"}), encoding="utf-8")
    types = {item["asset_id"]: item["type"] for item in asset_index.scan_assets(pack)}
    assert types["other-courthouse_photo"] == "other"
    assert types["mascot_pose-the_answer"] == "mascot_pose"
