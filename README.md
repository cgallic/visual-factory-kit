# Visual Factory Kit

Deterministic HTML/CSS image factory for social posts, ads, thumbnails, OG cards, Google Business Profile posts, Pinterest pins, carousels, Stories, and Reels.

This repo renders platform-sized PNGs from a JSON request and a brand pack. It is designed for teams that want repeatable branded image production without one-off AI image generation.

## What It Does

- Renders PNGs for 40+ platform formats.
- Uses deterministic HTML templates and local fonts.
- Supports swappable brand packs with tokens, icon, and transparent visual assets.
- Writes provenance sidecar JSON for every PNG.
- Writes a QA report for dimensions, text overflow, mobile readability, alt text, proof source, provenance, and banned public terms.

## Quick Start

Install dependencies:

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

Render the example:

```powershell
python visual_factory\render.py render --request examples\sample-request.json --brand brand-packs\example
```

Outputs write to:

```powershell
examples\outputs
```

Check the generated `*-qa-report.json`. Use the PNGs only when `"passed": true`.

## Brand Packs

A brand pack is a folder with:

```text
brand-packs/example/
├── brand.json
├── tokens.css
└── assets/
    ├── icon.png
    └── mascot.png
```

Create a new brand pack by copying `brand-packs/example`, replacing the assets, and editing `brand.json` and `tokens.css`.

Use transparent PNGs directly. Do not wrap logos or mascots in template-side circles unless the brand explicitly calls for that.

## Request Files

Start from:

```powershell
examples\sample-request.json
```

Edit:

- `client`
- `content_id`
- `formats`
- `message.headline`
- `message.subhead`
- `message.proof_label`
- `message.cta`
- `message.phone_number`
- `proof[0].source_path`
- `output.alt_text`
- `output.destination_dir`

Available format keys live in:

```powershell
visual_factory\platform-size-matrix.json
```

## Notes

This public kit intentionally does not include private client art, customer data, or proprietary brand files.
