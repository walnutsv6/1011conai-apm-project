"""Extract NovelAI PNG generation metadata without NovelAI API or SDK."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

MAGIC = b"stealth_pngcomp"
TEXT_KEYS = ("Title", "Description", "Software", "Source", "Generation time", "Comment")


def _alpha_bytes(image: Image.Image) -> bytes:
    alpha = image.convert("RGBA").getchannel("A").tobytes()
    width, height = image.size
    bit_index = 0

    def read(count: int) -> bytes:
        nonlocal bit_index
        if bit_index + count * 8 > width * height:
            raise ValueError("alpha metadata exceeds image capacity")
        result = bytearray(count)
        for byte_index in range(count):
            value = 0
            for _ in range(8):
                x, y = divmod(bit_index, height)
                value = (value << 1) | (alpha[y * width + x] & 1)
                bit_index += 1
            result[byte_index] = value
        return bytes(result)

    if read(len(MAGIC)) != MAGIC:
        raise ValueError("no stealth_pngcomp header")
    bit_length = int.from_bytes(read(4), "big")
    if bit_length % 8:
        raise ValueError("invalid alpha metadata length")
    return read(bit_length // 8)


def extract(path: Path) -> tuple[str, dict]:
    with Image.open(path) as image:
        if image.format != "PNG":
            raise ValueError("only PNG images are supported")
        try:
            data = json.loads(gzip.decompress(_alpha_bytes(image)).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("metadata is not a JSON object")
            method = "alpha-stealth_pngcomp"
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
            data = {key: image.info[key] for key in TEXT_KEYS if key in image.info}
            if isinstance(data.get("Comment"), str):
                try:
                    data["Comment"] = json.loads(data["Comment"])
                except json.JSONDecodeError:
                    pass
            comment = data.get("Comment")
            is_novelai = (
                "novelai" in str(data.get("Software", "")).lower()
                or data.get("Title") == "AI generated image"
                or isinstance(comment, dict)
                and "prompt" in comment
                and "steps" in comment
            )
            if not is_novelai:
                raise ValueError("no NovelAI alpha or PNG text metadata found") from None
            method = "png-text"
        if isinstance(data.get("Comment"), str):
            try:
                data["Comment"] = json.loads(data["Comment"])
            except json.JSONDecodeError:
                pass
        return method, data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="PNG image or directory")
    parser.add_argument("--recursive", action="store_true", help="scan subdirectories")
    parser.add_argument("--out-dir", type=Path, help="JSON output directory")
    parser.add_argument("--overwrite", action="store_true", help="replace existing JSON")
    args = parser.parse_args()

    source = args.input.resolve()
    if source.is_file():
        files = [source]
        if args.recursive:
            parser.error("--recursive applies to a directory")
    elif source.is_dir():
        files = sorted(source.rglob("*.png") if args.recursive else source.glob("*.png"))
        if not args.out_dir:
            parser.error("--out-dir is required for a directory input")
    else:
        parser.error(f"input not found: {source}")
    if not files:
        parser.error("no PNG images found")

    failures = 0
    for image_path in files:
        if args.out_dir:
            rel = image_path.relative_to(source) if source.is_dir() else Path(image_path.name)
            target = args.out_dir.resolve() / rel.with_suffix(".metadata.json")
        else:
            target = image_path.with_suffix(".metadata.json")
        if target.exists() and not args.overwrite:
            print(f"SKIP (exists): {target}", file=sys.stderr)
            failures += 1
            continue
        try:
            method, metadata = extract(image_path)
            result = {
                "source_image": str(image_path),
                "source_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "extraction_method": method,
                "metadata": metadata,
            }
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"OK: {target}")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"FAIL: {image_path}: {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
