#!/usr/bin/env python3
"""Stable Audio 3.0 game BGM and SFX utility. No third-party Python dependencies."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import shutil
import subprocess
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API = 'https://api.stability.ai/v2beta/audio'
START_URL = API + '/stable-audio/text-to-audio'
RESULT_URL = API + '/results/'
CREDIT_ESTIMATE = 8  # API reference and observed charge (2026-10-15); may change.

MODE_DEFAULTS = {'music': 60.0, 'sfx': 3.0}

def mode_prompt(mode, prompt):
    prompt = prompt.strip()
    prefix = 'TrackType: Music' if mode == 'music' else 'TrackType: SFX'
    if re.search(r'(?i)\bTrackType\s*:', prompt):
        return prompt
    return prefix + '. ' + prompt



def stamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def api_call(url, key, *, fields=None, timeout=90):
    headers = {'Authorization': 'Bearer ' + key, 'Accept': 'audio/*', 'Stability-Client-ID': 'stable-audio-generation-skill'}
    body = None
    if fields is not None:
        import uuid
        boundary = '----stableaudio' + uuid.uuid4().hex
        headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
        parts = []
        for name, value in fields.items():
            parts.extend([('--' + boundary + '\r\n').encode(),
                          ('Content-Disposition: form-data; name="' + name + '"\r\n\r\n').encode(),
                          str(value).encode('utf-8'), b'\r\n'])
        parts.append(('--' + boundary + '--\r\n').encode())
        body = b''.join(parts)
    req = Request(url, data=body, headers=headers, method='POST' if fields is not None else 'GET')
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.headers.get('Content-Type', ''), response.read()
    except HTTPError as exc:
        message = exc.read(2048).decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {exc.code}: {message}') from exc
    except URLError as exc:
        raise RuntimeError(f'Network error: {exc.reason}') from exc


def validate_id(id_):
    if not re.fullmatch(r'[a-fA-F0-9]{64}', id_):
        raise ValueError('Invalid generation ID; expected 64 hex characters')


def collect(args):
    key = os.environ.get('STABILITY_API_KEY')
    if not key:
        raise RuntimeError('STABILITY_API_KEY is not set')
    meta_path = Path(args.metadata)
    if not meta_path.exists():
        raise RuntimeError(f'Metadata file not found: {meta_path}')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    if meta.get('status') == 'completed':
        print('Already completed: ' + meta['output']); return 0
    id_ = meta['generation_id']; validate_id(id_)
    out_path = Path(meta['output'])
    if out_path.exists():
        raise RuntimeError('Output path already exists; refusing overwrite')
    deadline = time.monotonic() + args.wait_seconds
    while True:
        status, ctype, body = api_call(RESULT_URL + id_, key, timeout=args.http_timeout)
        if status == 200:
            if not ctype.startswith('audio/') or not body:
                raise RuntimeError('Non-audio or empty result returned; refusing to write output')
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(body)
            meta['status'] = 'completed'; meta['completed_at'] = stamp(); meta['bytes'] = len(body)
            write_json(meta_path, meta)
            print('Saved: ' + str(out_path)); return 0
        if status != 202:
            raise RuntimeError(f'Unexpected HTTP {status}: {body[:300]!r}')
        meta['status'] = 'pending'; meta['last_polled_at'] = stamp(); write_json(meta_path, meta)
        if time.monotonic() + args.poll_interval > deadline:
            print('Still processing; resume with: python scripts/stable_audio.py collect --metadata ' + str(meta_path))
            return 2
        time.sleep(args.poll_interval)


def generate(args):
    if not args.prompt.strip():
        raise ValueError('Prompt must not be empty')
    duration = args.duration if args.duration is not None else MODE_DEFAULTS[args.mode]
    if not (1 <= duration <= 380):
        raise ValueError('Duration must be between 1 and 380 seconds')
    if not (0 <= args.seed <= 4294967294):
        raise ValueError('Seed out of range')
    output = Path(args.output)
    if output.suffix.lower() != '.' + args.format:
        raise ValueError('Output extension must match --format')
    meta_path = Path(args.metadata) if args.metadata else output.with_suffix(output.suffix + '.json')
    if output.exists() or meta_path.exists():
        raise RuntimeError('Output or metadata already exists; refusing overwrite')
    effective_prompt = mode_prompt(args.mode, args.prompt)
    preview = {'model': 'stable-audio-3', 'mode': args.mode, 'user_prompt': args.prompt, 'prompt': effective_prompt, 'duration_seconds': duration,
               'seed': args.seed, 'output_format': args.format, 'output': str(output),
               'pricing_reference_credits': CREDIT_ESTIMATE, 'pricing_reference_usd': round(CREDIT_ESTIMATE / 100, 2),
               'pricing_note': 'Indicative pricing only; actual billing and live pricing may differ.'}
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if not args.execute:
        print('DRY RUN: no API request was made. Add --execute --approve-credits 8 after checking the current price.')
        return 0
    if args.approve_credits is None or args.approve_credits < CREDIT_ESTIMATE:
        raise RuntimeError('Explicit spending approval required: --approve-credits 8 (or higher); check live pricing first')
    key = os.environ.get('STABILITY_API_KEY')
    if not key:
        raise RuntimeError('STABILITY_API_KEY is not set')
    fields = {'prompt': effective_prompt, 'duration': duration, 'seed': args.seed,
              'output_format': args.format, 'model': 'stable-audio-3'}
    status, ctype, body = api_call(START_URL, key, fields=fields, timeout=args.http_timeout)
    if status != 202:
        raise RuntimeError(f'Unexpected HTTP {status}: {body[:300]!r}')
    try:
        id_ = json.loads(body)['id']; validate_id(id_)
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError('Invalid generation response: ' + repr(body[:300])) from exc
    meta = dict(preview, generation_id=id_, status='pending', started_at=stamp())
    write_json(meta_path, meta)
    print('Job accepted: ' + id_ + '\nMetadata: ' + str(meta_path))
    if args.no_wait:
        return 0
    return collect(argparse.Namespace(metadata=str(meta_path), wait_seconds=args.wait_seconds,
                                      poll_interval=args.poll_interval, http_timeout=args.http_timeout))



def process_audio(args):
    src, dst = Path(args.input), Path(args.output)
    if not src.is_file():
        raise RuntimeError('Input audio does not exist')
    if src.resolve() == dst.resolve() or dst.exists():
        raise RuntimeError('Destination must be different from input and must not exist')
    if dst.suffix.lower() not in {'.ogg', '.wav', '.mp3'}:
        raise ValueError('Output must be .ogg, .wav, or .mp3')
    if args.fade_out < 0 or args.duration is not None and args.duration <= 0:
        raise ValueError('Invalid fade/duration value')
    if args.fade_out and not args.duration:
        raise ValueError('--fade-out also requires --duration; verify it matches actual audio length')
    if args.fade_out and args.fade_out >= args.duration:
        raise ValueError('Fade-out must be shorter than duration')
    if args.trim_silence and args.mode != 'sfx':
        raise ValueError('Silence trimming is restricted to SFX to preserve BGM rhythm')
    filters = []
    if args.trim_silence:
        # Reverse twice to remove trailing silence without truncating quiet middle sections.
        filters.append('silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB')
        filters.append('areverse')
        filters.append('silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB')
        filters.append('areverse')
    if args.normalize:
        filters.append('loudnorm=I=-16:TP=-1.5:LRA=11')
    if args.fade_out:
        filters.append(f'afade=t=out:st={args.duration-args.fade_out:g}:d={args.fade_out:g}')
    codec = {'.ogg': ['-c:a', 'libvorbis', '-q:a', '5'], '.wav': ['-c:a','pcm_s16le'], '.mp3': ['-c:a','libmp3lame','-q:a','3']}[dst.suffix.lower()]
    cmd = ['ffmpeg', '-nostdin', '-n', '-i', str(src), '-vn']
    if filters:
        cmd += ['-af', ','.join(filters)]
    cmd += codec + [str(dst)]
    print(json.dumps({'mode': args.mode, 'input': str(src), 'output': str(dst), 'filters': filters, 'command': cmd, 'execute': args.execute}, ensure_ascii=False, indent=2))
    if not args.execute:
        print('DRY RUN: no output audio was created.')
        return 0
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg not found on PATH; install FFmpeg to use process')
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError('FFmpeg failed: ' + result.stderr[-1500:])
    print('Saved processed audio: ' + str(dst))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    g = sub.add_parser('generate', help='Preview or submit text-to-audio generation')
    g.add_argument('--prompt', required=True)
    g.add_argument('--mode', choices=['music','sfx'], default='music', help='Music/BGM or sound effects; sets tag and default duration')
    g.add_argument('--duration', type=float, default=None, help='Defaults: music 60 sec, sfx 3 sec')
    g.add_argument('--seed', type=int, default=0)
    g.add_argument('--format', choices=['mp3', 'wav'], default='mp3')
    g.add_argument('--output', required=True)
    g.add_argument('--metadata')
    g.add_argument('--execute', action='store_true', help='Actually submit a billable request')
    g.add_argument('--approve-credits', type=int, help='Explicit per-generation credit authorization')
    g.add_argument('--no-wait', action='store_true')
    c = sub.add_parser('collect', help='Poll an existing job (does not submit new generation)')
    c.add_argument('--metadata', required=True)
    pp = sub.add_parser('process', help='Optional audio cleanup using local FFmpeg; no API charges')
    pp.add_argument('--input', required=True, help='Source audio; never modified')
    pp.add_argument('--output', required=True, help='New destination path (never overwritten)')
    pp.add_argument('--mode', choices=['music', 'sfx'], required=True)
    pp.add_argument('--trim-silence', action='store_true', help='SFX: remove leading and trailing silence')
    pp.add_argument('--normalize', action='store_true', help='Apply loudness normalization (EBU R128)')
    pp.add_argument('--fade-out', type=float, default=0.0, help='Seconds; requires --duration or probe')
    pp.add_argument('--duration', type=float, default=None, help='Optional clip duration (seconds) for fade calculation')
    pp.add_argument('--execute', action='store_true', help='Run FFmpeg; default dry-run')
    for p in (g, c):
        p.add_argument('--wait-seconds', type=int, default=300)
        p.add_argument('--poll-interval', type=int, default=10)
        p.add_argument('--http-timeout', type=int, default=90)
    args = parser.parse_args()
    if args.command in ('generate', 'collect') and (args.poll_interval <= 0 or args.wait_seconds <= 0):
        parser.error('Polling parameters must be positive')
    try:
        return generate(args) if args.command == 'generate' else collect(args) if args.command == 'collect' else process_audio(args)
    except (ValueError, RuntimeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
