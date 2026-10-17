---
name: novelai-metadata
description: Extract NovelAI generation metadata from existing PNG images into JSON for reusing an established character or auditing past generations. Use for metadata inspection or export; do not use for image generation or editing.
---

# NovelAI image metadata

Read generation settings from an existing NovelAI PNG locally. This skill does not call NovelAI's API, use `novelai-sdk`, or depend on any image-generation skill. It requires Python 3 and Pillow.

## Workflow

1. Confirm the image path and requested JSON destination. Use the project's `.venv` when available; otherwise use a Python environment with Pillow (`python -m pip install pillow` in that environment if needed).
2. Run `scripts/extract_metadata.py` on the image or a directory. The script first reads NovelAI's compressed metadata from the alpha-channel least significant bits (`stealth_pngcomp`), then falls back to PNG text fields. It reads pixels without modifying the source image.
3. Check the output JSON for `metadata.Comment.prompt`, `metadata.Comment.uc`, model, seed, steps, dimensions, guidance, sampler, and reference-related fields before treating it as a reusable generation record. Report missing fields rather than inventing them. A saved image may omit external reference images or other inputs even when it records their settings.
4. Keep generated JSON next to the chosen image or in the user-requested location. Do not overwrite an existing JSON unless the user requested replacement and `--overwrite` is supplied. Do not launch generation or send the image to a network service.

## Commands

Single image, JSON beside it:

```powershell
.venv/Scripts/python.exe .agents/skills/novelai-metadata/scripts/extract_metadata.py "path/to/image.png"
```

Batch into a separate directory:

```powershell
.venv/Scripts/python.exe .agents/skills/novelai-metadata/scripts/extract_metadata.py "output/selected/racers/azure" --recursive --out-dir "output/metadata/azure"
```

The single-image default creates `<image-stem>.metadata.json`. Batch output preserves paths relative to the input directory. Each JSON includes the extraction method, source SHA-256, and unmodified NovelAI metadata. The script exits nonzero and does not create a JSON for images with no extractable metadata.

NovelAI's [official metadata repository](https://github.com/NovelAI/novelai-image-metadata) documents the alpha-channel format. Ordinary PNG chunk inspection can miss it.
