import gzip
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image, PngImagePlugin
import pytest


SCRIPT = Path(__file__).parents[1] / ".apm/skills/novelai-metadata/scripts/extract_metadata.py"
spec = importlib.util.spec_from_file_location("extract_metadata", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _stealth_image(path: Path, metadata):
    payload = gzip.compress(json.dumps(metadata).encode("utf-8"))
    encoded = b"stealth_pngcomp" + (len(payload) * 8).to_bytes(4, "big") + payload
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    for bit_index in range(len(encoded) * 8):
        x, y = divmod(bit_index, image.height)
        bit = (encoded[bit_index // 8] >> (7 - bit_index % 8)) & 1
        image.putpixel((x, y), (0, 0, 0, 254 | bit))
    image.save(path)


def test_stealth_metadata_uses_column_major_alpha_bits(tmp_path):
    path = tmp_path / "stealth.png"
    _stealth_image(path, {"Comment": json.dumps({"prompt": "cat", "steps": 28})})

    method, data = module.extract(path)

    assert method == "alpha-stealth_pngcomp"
    assert data["Comment"] == {"prompt": "cat", "steps": 28}


def test_png_text_fallback_requires_novelai_evidence(tmp_path):
    novelai = tmp_path / "novelai.png"
    text = PngImagePlugin.PngInfo()
    text.add_text("Software", "NovelAI")
    text.add_text("Comment", json.dumps({"prompt": "dog", "steps": 30}))
    Image.new("RGB", (8, 8)).save(novelai, pnginfo=text)

    assert module.extract(novelai) == (
        "png-text",
        {"Software": "NovelAI", "Comment": {"prompt": "dog", "steps": 30}},
    )

    unrelated = tmp_path / "unrelated.png"
    other_text = PngImagePlugin.PngInfo()
    other_text.add_text("Title", "Holiday photo")
    Image.new("RGB", (8, 8)).save(unrelated, pnginfo=other_text)

    with pytest.raises(ValueError, match="no NovelAI"):
        module.extract(unrelated)


def test_non_object_stealth_payload_is_rejected(tmp_path):
    path = tmp_path / "invalid.png"
    _stealth_image(path, ["not an object"])

    with pytest.raises(ValueError, match="no NovelAI"):
        module.extract(path)


def test_cli_writes_json_and_preserves_existing_output(tmp_path, monkeypatch):
    path = tmp_path / "image.png"
    _stealth_image(path, {"Comment": json.dumps({"prompt": "cat", "steps": 28})})
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), str(path)])

    assert module.main() == 0
    target = tmp_path / "image.metadata.json"
    saved = target.read_text(encoding="utf-8")
    data = json.loads(saved)
    assert data["metadata"]["Comment"]["prompt"] == "cat"
    assert len(data["source_sha256"]) == 64

    assert module.main() == 1
    assert target.read_text(encoding="utf-8") == saved
