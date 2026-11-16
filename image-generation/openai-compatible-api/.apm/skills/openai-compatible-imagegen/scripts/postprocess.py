# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10"]
# ///
"""Local post-processing for generated 2D game assets (Pillow only, no API calls).

  remove-bg    key out a flat background colour (border-connected by default)
  trim         crop to the opaque bounding box, with optional padding
  pixelate     downscale to a pixel-art grid, binarise alpha, limit/lock the palette
  sheet-pack   pack frames into a grid sprite sheet + TexturePacker "JSON Hash" atlas
  sheet-slice  cut a grid sprite sheet into individual frames

Run with `uv run postprocess.py ...` or `python postprocess.py ...` when Pillow is installed.
Existing outputs are never overwritten unless --force is given.
"""
import argparse
import glob
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops


class PostError(RuntimeError):
    pass


# ---------------------------------------------------------------- helpers

def ensure_writable(paths, force):
    clashes = [str(p) for p in paths if Path(p).exists()]
    if clashes and not force:
        raise PostError('Refusing to overwrite (use --force): ' + ', '.join(clashes))


def save_png(img, path):
    path = Path(path)
    if path.suffix.lower() != '.png':
        raise PostError(f'Output must be .png: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def load_rgba(path):
    path = Path(path)
    if not path.is_file():
        raise PostError(f'Input not found: {path}')
    with Image.open(path) as im:
        return im.convert('RGBA')


def parse_hex(color):
    m = re.fullmatch(r'#?([0-9a-fA-F]{6})', color.strip())
    if not m:
        raise PostError(f'Invalid colour {color!r}; expected #RRGGBB')
    v = m.group(1)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def parse_size(text):
    m = re.fullmatch(r'(\d+)[xX](\d+)', text.strip())
    if not m or int(m.group(1)) <= 0 or int(m.group(2)) <= 0:
        raise PostError(f'Invalid size {text!r}; expected WxH')
    return int(m.group(1)), int(m.group(2))


def border_pixels(img):
    w, h = img.size
    px = img.load()
    coords = {(x, y) for x in range(w) for y in (0, h - 1)} | {(x, y) for y in range(h) for x in (0, w - 1)}
    return coords, [px[c] for c in coords]


def median_color(pixels):
    n = len(pixels)
    return tuple(sorted(p[i] for p in pixels)[n // 2] for i in range(3))


def pixels(img):
    """Flat pixel list; get_flattened_data replaces getdata from Pillow 12.1."""
    getter = getattr(img, 'get_flattened_data', None) or img.getdata
    return list(getter())


def has_transparency(img, threshold=128):
    lo, _ = img.getchannel('A').getextrema()
    return lo < threshold


# ---------------------------------------------------------------- remove-bg

def remove_background(img, color=None, tolerance=28, soft=22, connected=True):
    """Return an RGBA copy with the flat background keyed out (soft edge).

    Distance is the per-channel absolute difference summed (clamped to 255). Pixels within
    `tolerance` become transparent, then alpha ramps to opaque over `soft`. With `connected`,
    only background-coloured pixels reachable from the image border are keyed, so interior
    details of the same colour (eye whites on a white background) survive.
    """
    if tolerance < 0 or soft < 1 or tolerance + soft > 255:
        raise PostError('Need tolerance >= 0, soft >= 1 and tolerance + soft <= 255')
    img = img.convert('RGBA')
    rgb = img.convert('RGB')
    coords, border = border_pixels(rgb)
    bg = color or median_color(border)
    diff = ImageChops.difference(rgb, Image.new('RGB', rgb.size, bg))
    r, g, b = diff.split()
    dist = ImageChops.add(ImageChops.add(r, g), b)  # clamps at 255
    ramp = [0 if v <= tolerance else min(255, round((v - tolerance) * 255 / soft)) for v in range(256)]
    key_alpha = dist.point(ramp)
    if connected:
        w, h = rgb.size
        keyable = bytearray(key_alpha.tobytes())  # < 255 means "background-ish"
        reached = bytearray(w * h)
        queue = deque(y * w + x for x, y in coords if keyable[y * w + x] < 255)
        for i in queue:
            reached[i] = 1
        while queue:
            i = queue.popleft()
            x, y = i % w, i // w
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if ok and not reached[j] and keyable[j] < 255:
                    reached[j] = 1
                    queue.append(j)
        out = bytes(keyable[i] if reached[i] else 255 for i in range(w * h))
        key_alpha = Image.frombytes('L', rgb.size, out)
    alpha = ImageChops.multiply(img.getchannel('A'), key_alpha)
    result = img.copy()
    result.putalpha(alpha)
    return result, bg


def cmd_remove_bg(args):
    ensure_writable([args.output], args.force)
    img = load_rgba(args.input)
    if has_transparency(img) and not args.rekey:
        save_png(img, args.output)
        print(f'NOTE: {args.input} already has transparency; copied unchanged (use --rekey to key anyway)')
        return 0
    color = None if args.color == 'auto' else parse_hex(args.color)
    result, bg = remove_background(img, color, args.tolerance, args.soft, not args.global_key)
    save_png(result, args.output)
    print(f"Saved: {args.output} (background #{''.join(f'{c:02x}' for c in bg)})")
    return 0


# ---------------------------------------------------------------- trim

def trim_image(img, padding=0, threshold=1):
    mask = img.getchannel('A').point(lambda a: 255 if a >= threshold else 0)
    box = mask.getbbox()
    if box is None:
        raise PostError('Image is fully transparent; nothing to trim to')
    cropped = img.crop(box)
    if padding:
        canvas = Image.new('RGBA', (cropped.width + 2 * padding, cropped.height + 2 * padding), (0, 0, 0, 0))
        canvas.paste(cropped, (padding, padding))
        cropped = canvas
    return cropped, box


def cmd_trim(args):
    ensure_writable([args.output], args.force)
    result, box = trim_image(load_rgba(args.input), args.padding, args.alpha_threshold)
    save_png(result, args.output)
    print(f'Saved: {args.output} (crop box {box}, size {result.size[0]}x{result.size[1]})')
    return 0


# ---------------------------------------------------------------- pixelate

def load_palette(spec):
    path = Path(spec)
    colors = []
    if path.suffix.lower() == '.gpl' and path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            parts = line.split()
            if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
                colors.append(tuple(int(p) for p in parts[:3]))
    elif path.suffix.lower() in ('.png', '.gif', '.bmp') and path.is_file():
        with Image.open(path) as im:
            found = im.convert('RGB').getcolors(maxcolors=257)
        if not found:
            raise PostError('Palette image has more than 256 colours')
        colors = [c for _, c in sorted(found, key=lambda t: -t[0])]
    else:
        colors = [parse_hex(c) for c in re.split(r'[,\s]+', spec.strip()) if c]
    if not 1 <= len(colors) <= 256:
        raise PostError('Palette must contain 1-256 colours')
    return colors


def palette_image(colors):
    flat = [v for c in colors for v in c]
    flat += list(colors[0]) * (256 - len(colors))  # pad with a real entry, never implicit black
    pal = Image.new('P', (1, 1))
    pal.putpalette(flat)
    return pal


def pixelate(img, size, resample='box', colors=None, palette=None, alpha_threshold=128):
    method = {'box': Image.Resampling.BOX, 'nearest': Image.Resampling.NEAREST}[resample]
    small = img.convert('RGBA').resize(size, method)
    alpha = small.getchannel('A')
    if alpha_threshold >= 0:
        alpha = alpha.point(lambda a: 255 if a >= alpha_threshold else 0)
    rgb = small.convert('RGB')
    if colors or palette:
        if palette is None:
            opaque = [p for p, a in zip(pixels(rgb), pixels(alpha)) if a > 0] or pixels(rgb)
            strip = Image.new('RGB', (len(opaque), 1))
            strip.putdata(opaque)
            found = strip.getcolors(maxcolors=colors)
            if found:  # already within budget: keep exact colours
                palette = [c for _, c in found]
            else:
                q = strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
                raw = q.getpalette()[:3 * colors]
                palette = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
        rgb = rgb.quantize(palette=palette_image(palette), dither=Image.Dither.NONE).convert('RGB')
    out = rgb.convert('RGBA')
    out.putalpha(alpha)
    if alpha_threshold >= 0:  # zero RGB under transparent pixels so engines don't bleed colour
        clear = Image.new('RGBA', out.size, (0, 0, 0, 0))
        out = Image.composite(out, clear, alpha)
    return out


def cmd_pixelate(args):
    img = load_rgba(args.input)
    w, h = img.size
    if args.scale_factor:
        size = (max(1, round(w / args.scale_factor)), max(1, round(h / args.scale_factor)))
    elif args.width or args.height:
        tw = args.width or max(1, round(w * args.height / h))
        th = args.height or max(1, round(h * args.width / w))
        size = (tw, th)
    else:
        raise PostError('Give --width and/or --height, or --scale-factor')
    if args.colors is not None and not 2 <= args.colors <= 256:
        raise PostError('--colors must be 2-256')
    out_path = Path(args.output)
    preview = out_path.with_name(f'{out_path.stem}@{args.preview_scale}x.png') if args.preview_scale else None
    ensure_writable([out_path] + ([preview] if preview else []), args.force)
    palette = load_palette(args.palette) if args.palette else None
    result = pixelate(img, size, args.resample, args.colors, palette, args.alpha_threshold)
    save_png(result, out_path)
    print(f'Saved: {out_path} ({size[0]}x{size[1]})')
    if preview:
        save_png(result.resize((size[0] * args.preview_scale, size[1] * args.preview_scale), Image.Resampling.NEAREST), preview)
        print(f'Saved preview: {preview}')
    return 0


# ---------------------------------------------------------------- sprite sheets

def expand_inputs(items):
    paths = []
    for item in items:
        if any(ch in item for ch in '*?['):
            hits = sorted(glob.glob(item))
            if not hits:
                raise PostError(f'No files match {item!r}')
            paths += hits
        else:
            paths.append(item)
    return [Path(p) for p in paths]


def pack_sheet(images, columns=None, cell=None, padding=0, align='center'):
    """images: [(name, RGBA Image)] -> (sheet, atlas dict). margin and spacing both equal padding."""
    if not images:
        raise PostError('No input frames')
    cw = cell[0] if cell else max(im.width for _, im in images)
    ch = cell[1] if cell else max(im.height for _, im in images)
    too_big = [n for n, im in images if im.width > cw or im.height > ch]
    if too_big:
        raise PostError(f'Frames larger than the {cw}x{ch} cell: ' + ', '.join(too_big))
    cols = columns or math.ceil(math.sqrt(len(images)))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new('RGBA', (padding + cols * (cw + padding), padding + rows * (ch + padding)), (0, 0, 0, 0))
    frames = {}
    for i, (name, im) in enumerate(images):
        x = padding + (i % cols) * (cw + padding)
        y = padding + (i // cols) * (ch + padding)
        ox = (cw - im.width) // 2
        oy = (ch - im.height) // 2 if align == 'center' else ch - im.height
        sheet.paste(im, (x + ox, y + oy))
        frames[name] = {'frame': {'x': x, 'y': y, 'w': cw, 'h': ch}, 'rotated': False, 'trimmed': False,
                        'spriteSourceSize': {'x': 0, 'y': 0, 'w': cw, 'h': ch},
                        'sourceSize': {'w': cw, 'h': ch}}
    meta = {'app': 'openai-compatible-imagegen postprocess', 'version': '1.0', 'format': 'RGBA8888',
            'size': {'w': sheet.width, 'h': sheet.height}, 'scale': '1',
            'grid': {'columns': cols, 'rows': rows, 'frameWidth': cw, 'frameHeight': ch,
                     'margin': padding, 'spacing': padding}}
    return sheet, {'frames': frames, 'meta': meta}


def cmd_sheet_pack(args):
    out = Path(args.output)
    atlas_path = Path(args.atlas) if args.atlas else out.with_suffix('.json')
    ensure_writable([out, atlas_path], args.force)
    paths = expand_inputs(args.inputs)
    names = [p.name for p in paths]
    if len(set(names)) != len(names):
        raise PostError('Input file names must be unique (they become atlas frame names)')
    images = [(p.name, load_rgba(p)) for p in paths]
    sheet, atlas = pack_sheet(images, args.columns, parse_size(args.cell) if args.cell != 'auto' else None,
                              args.padding, args.align)
    atlas['meta']['image'] = out.name
    save_png(sheet, out)
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    atlas_path.write_text(json.dumps(atlas, indent=2) + '\n', encoding='utf-8')
    g = atlas['meta']['grid']
    print(f"Saved: {out} ({sheet.width}x{sheet.height}, {len(images)} frames, {g['columns']}x{g['rows']} grid "
          f"of {g['frameWidth']}x{g['frameHeight']})\nAtlas: {atlas_path}")
    return 0


def slice_sheet(sheet, rows=None, cols=None, cell=None, padding=0, skip_empty=False):
    if cell:
        cw, ch = cell
        cols = (sheet.width - padding) // (cw + padding)
        rows = (sheet.height - padding) // (ch + padding)
    elif rows and cols:
        cw = (sheet.width - padding) // cols - padding
        ch = (sheet.height - padding) // rows - padding
    else:
        raise PostError('Give --rows and --cols, or --cell WxH')
    if cw <= 0 or ch <= 0 or rows <= 0 or cols <= 0:
        raise PostError('Grid does not fit the sheet')
    frames = []
    for r in range(rows):
        for c in range(cols):
            x, y = padding + c * (cw + padding), padding + r * (ch + padding)
            frame = sheet.crop((x, y, x + cw, y + ch))
            if skip_empty and frame.getchannel('A').getbbox() is None:
                continue
            frames.append(((r, c), frame))
    return frames, (cw, ch)


def cmd_sheet_slice(args):
    sheet = load_rgba(args.input)
    frames, (cw, ch) = slice_sheet(sheet, args.rows, args.cols, parse_size(args.cell) if args.cell else None,
                                   args.padding, args.skip_empty)
    out_dir = Path(args.output_dir)
    targets = [out_dir / f'{args.prefix}_{i:03d}.png' for i in range(len(frames))]
    ensure_writable(targets, args.force)
    for target, (_, frame) in zip(targets, frames):
        save_png(frame, target)
    print(f'Saved {len(targets)} frames of {cw}x{ch} to {out_dir}')
    return 0


# ---------------------------------------------------------------- cli

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('remove-bg', help='key out a flat background colour')
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--color', default='auto', help='#RRGGBB or auto (median of border pixels)')
    p.add_argument('--tolerance', type=int, default=28, help='summed RGB distance treated as background')
    p.add_argument('--soft', type=int, default=22, help='width of the soft alpha edge')
    p.add_argument('--global', dest='global_key', action='store_true',
                   help='key every matching pixel, not only those connected to the border')
    p.add_argument('--rekey', action='store_true', help='key even if the input already has transparency')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_remove_bg)

    p = sub.add_parser('trim', help='crop to the opaque bounding box')
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--padding', type=int, default=0)
    p.add_argument('--alpha-threshold', type=int, default=1)
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_trim)

    p = sub.add_parser('pixelate', help='downscale to a pixel-art grid')
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--width', type=int)
    p.add_argument('--height', type=int)
    p.add_argument('--scale-factor', type=float, help='divide both sides by this (e.g. 16: 1024 -> 64)')
    p.add_argument('--resample', choices=['box', 'nearest'], default='box')
    p.add_argument('--colors', type=int, help='limit to N colours (median cut, no dithering)')
    p.add_argument('--palette', help='fixed palette: "#000000,#ffffff,..." or a .gpl / .png file')
    p.add_argument('--alpha-threshold', type=int, default=128, help='binarise alpha at this value; -1 keeps soft alpha')
    p.add_argument('--preview-scale', type=int, help='also write <name>@Kx.png enlarged with nearest neighbour')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_pixelate)

    p = sub.add_parser('sheet-pack', help='pack frames into a grid sheet + JSON atlas')
    p.add_argument('--inputs', nargs='+', required=True, help='files or glob patterns, in frame order')
    p.add_argument('--output', required=True)
    p.add_argument('--atlas', help='atlas JSON path (default: <output>.json next to the sheet)')
    p.add_argument('--columns', type=int)
    p.add_argument('--cell', default='auto', help='WxH or auto (largest frame)')
    p.add_argument('--padding', type=int, default=0, help='margin and spacing in pixels')
    p.add_argument('--align', choices=['center', 'bottom'], default='center',
                   help='placement inside the cell; bottom keeps feet on a common baseline')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_sheet_pack)

    p = sub.add_parser('sheet-slice', help='cut a grid sheet into frames')
    p.add_argument('--input', required=True)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--prefix', default='frame')
    p.add_argument('--rows', type=int)
    p.add_argument('--cols', type=int)
    p.add_argument('--cell', help='WxH frame size (alternative to --rows/--cols)')
    p.add_argument('--padding', type=int, default=0, help='margin and spacing used when the sheet was packed')
    p.add_argument('--skip-empty', action='store_true', help='drop fully transparent frames')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_sheet_slice)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (PostError, OSError, ValueError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
