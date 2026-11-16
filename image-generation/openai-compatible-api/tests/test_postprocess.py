import importlib.util
import json
from pathlib import Path

from PIL import Image
import pytest

SCRIPT = Path(__file__).parents[1] / ".apm/skills/openai-compatible-imagegen/scripts/postprocess.py"
spec = importlib.util.spec_from_file_location("postprocess", SCRIPT)
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

MAGENTA = (255, 0, 255)


def sprite_on(bg, size=(64, 64), box=(16, 16, 48, 48), fill=(30, 120, 200), hole=None):
    img = Image.new("RGB", size, bg)
    img.paste(fill, box)
    if hole:
        img.paste(bg, hole)  # background-coloured detail enclosed by the sprite
    return img


def test_remove_bg_keys_border_but_keeps_enclosed_detail():
    img = sprite_on(MAGENTA, hole=(28, 28, 36, 36))
    out, bg = pp.remove_background(img)
    assert bg == MAGENTA
    a = out.getchannel("A")
    assert a.getpixel((0, 0)) == 0
    assert a.getpixel((63, 63)) == 0
    assert a.getpixel((20, 20)) == 255
    assert a.getpixel((32, 32)) == 255  # enclosed, not connected to the border


def test_remove_bg_global_keys_enclosed_detail_too():
    img = sprite_on(MAGENTA, hole=(28, 28, 36, 36))
    out, _ = pp.remove_background(img, connected=False)
    assert out.getchannel("A").getpixel((32, 32)) == 0


def test_remove_bg_cli_passes_through_transparent_input(tmp_path, capsys):
    src = tmp_path / "t.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(src)
    assert pp.main(["remove-bg", "--input", str(src), "--output", str(tmp_path / "o.png")]) == 0
    assert "already has transparency" in capsys.readouterr().out


def test_trim_bbox_and_padding():
    img = Image.new("RGBA", (50, 40), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (10, 5, 20, 25))
    out, box = pp.trim_image(img, padding=2)
    assert box == (10, 5, 20, 25)
    assert out.size == (14, 24)
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((2, 2))[3] == 255


def test_trim_fully_transparent_fails():
    with pytest.raises(pp.PostError):
        pp.trim_image(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))


def gradient_sprite():
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    for x in range(16, 112):
        for y in range(16, 112):
            img.putpixel((x, y), (x * 2, y * 2, 128, 255))
    return img


def opaque_colors(img):
    return {p[:3] for p in pp.pixels(img) if p[3] > 0}


def test_pixelate_size_alpha_and_color_limit():
    out = pp.pixelate(gradient_sprite(), (32, 32), colors=8)
    assert out.size == (32, 32)
    assert set(pp.pixels(out.getchannel("A"))) <= {0, 255}
    assert 1 < len(opaque_colors(out)) <= 8
    assert out.getpixel((0, 0)) == (0, 0, 0, 0)


def test_pixelate_fixed_palette():
    palette = [(0, 0, 0), (255, 255, 255), (200, 40, 40)]
    out = pp.pixelate(gradient_sprite(), (16, 16), palette=palette)
    assert opaque_colors(out) <= set(palette)


def test_load_palette_hex_and_gpl(tmp_path):
    assert pp.load_palette("#000000, #FFFFFF") == [(0, 0, 0), (255, 255, 255)]
    gpl = tmp_path / "p.gpl"
    gpl.write_text("GIMP Palette\nName: t\n#\n  0   0   0 black\n255 128   0 orange\n", encoding="utf-8")
    assert pp.load_palette(str(gpl)) == [(0, 0, 0), (255, 128, 0)]


def test_pixelate_cli_writes_preview(tmp_path):
    src = tmp_path / "s.png"
    gradient_sprite().save(src)
    assert pp.main(["pixelate", "--input", str(src), "--output", str(tmp_path / "p.png"),
                    "--scale-factor", "4", "--colors", "16", "--preview-scale", "4"]) == 0
    assert Image.open(tmp_path / "p.png").size == (32, 32)
    assert Image.open(tmp_path / "p@4x.png").size == (128, 128)


def frames(n=5):
    out = []
    for i in range(n):
        im = Image.new("RGBA", (10 + i, 12), (0, 0, 0, 0))
        im.paste((i * 40, 10, 10, 255), (0, 0, im.width, im.height))
        out.append((f"f{i}.png", im))
    return out


def test_sheet_pack_geometry_and_atlas():
    sheet, atlas = pp.pack_sheet(frames(), columns=3, padding=2, align="bottom")
    assert sheet.size == (2 + 3 * (14 + 2), 2 + 2 * (12 + 2))
    f4 = atlas["frames"]["f4.png"]["frame"]
    assert f4 == {"x": 2 + 1 * 16, "y": 2 + 1 * 14, "w": 14, "h": 12}
    assert atlas["meta"]["grid"] == {"columns": 3, "rows": 2, "frameWidth": 14, "frameHeight": 12,
                                     "margin": 2, "spacing": 2}
    # first frame (10 wide) is centred horizontally in its 14-wide cell
    assert sheet.getpixel((2 + 1, 2))[3] == 0
    assert sheet.getpixel((2 + 2, 2))[3] == 255


def test_sheet_pack_rejects_oversized_frames():
    with pytest.raises(pp.PostError):
        pp.pack_sheet(frames(), cell=(8, 8))


def test_pack_then_slice_round_trip(tmp_path):
    src = frames(6)
    for name, im in src:
        im.save(tmp_path / name)
    sheet_path = tmp_path / "out/sheet.png"
    assert pp.main(["sheet-pack", "--inputs", str(tmp_path / "f*.png"), "--output", str(sheet_path),
                    "--columns", "3", "--padding", "1", "--cell", "16x12"]) == 0
    atlas = json.loads((tmp_path / "out/sheet.json").read_text(encoding="utf-8"))
    assert atlas["meta"]["image"] == "sheet.png"
    assert list(atlas["frames"]) == [n for n, _ in src]
    assert pp.main(["sheet-slice", "--input", str(sheet_path), "--output-dir", str(tmp_path / "sliced"),
                    "--cell", "16x12", "--padding", "1"]) == 0
    sliced = sorted((tmp_path / "sliced").glob("frame_*.png"))
    assert len(sliced) == 6
    for (name, original), path in zip(src, sliced):
        frame = Image.open(path).convert("RGBA")
        box = atlas["frames"][name]["frame"]
        assert frame.size == (box["w"], box["h"])
        trimmed, _ = pp.trim_image(frame)
        assert trimmed.tobytes() == original.tobytes()
    # rows/cols addressing yields the same frames
    assert pp.main(["sheet-slice", "--input", str(sheet_path), "--output-dir", str(tmp_path / "rc"),
                    "--rows", "2", "--cols", "3", "--padding", "1"]) == 0
    assert [Image.open(p).tobytes() for p in sorted((tmp_path / "rc").glob("*.png"))] == \
           [Image.open(p).tobytes() for p in sliced]


def test_slice_skip_empty_and_no_overwrite(tmp_path, capsys):
    sheet = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    sheet.paste((255, 255, 255, 255), (0, 0, 10, 10))
    src = tmp_path / "s.png"
    sheet.save(src)
    assert pp.main(["sheet-slice", "--input", str(src), "--output-dir", str(tmp_path / "o"),
                    "--rows", "1", "--cols", "2", "--skip-empty"]) == 0
    assert len(list((tmp_path / "o").glob("*.png"))) == 1
    assert pp.main(["sheet-slice", "--input", str(src), "--output-dir", str(tmp_path / "o"),
                    "--rows", "1", "--cols", "2"]) == 1
    assert "overwrite" in capsys.readouterr().err
