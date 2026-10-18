#!/usr/bin/env python3
"""Agent-friendly ElevenLabs BGM/SFX generator (Python standard library + optional ffmpeg)."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.elevenlabs.io'
RATES = {'music': 12.5, 'sfx': 10.0}  # Observations, not guaranteed prices.


def parser():
    p = argparse.ArgumentParser(description='ElevenLabs game audio generation')
    sp = p.add_subparsers(dest='command', required=True)
    for mode in ('music', 'sfx'):
        x = sp.add_parser(mode)
        x.add_argument('--prompt', required=True)
        x.add_argument('--seconds', type=float, required=True)
        x.add_argument('--output', required=True, help='Destination filename (.mp3, .ogg or .wav)')
        x.add_argument('--dry-run', action='store_true')
        x.add_argument('--yes', action='store_true', help='Skip interactive confirmation ONLY after explicit user authorization')
        x.add_argument('--max-estimated-credits', type=float, help='Reject jobs above this estimated credit budget')
        x.add_argument('--output-format', default='auto', help='API codec format; default auto MP3')
        x.add_argument('--ffmpeg', default='ffmpeg', help='Path to ffmpeg executable for conversion/analysis')
        x.add_argument('--no-analysis', action='store_true')
        if mode == 'music':
            x.add_argument('--model', default='music_v2_5', choices=['music_v1','music_v2','music_v2_5'])
            x.add_argument('--allow-vocals', action='store_true')
        else:
            x.add_argument('--model', default='eleven_text_to_sound_v2', choices=['eleven_text_to_sound_v2'])
            x.add_argument('--loop', action='store_true')
            x.add_argument('--prompt-influence', type=float, default=0.3)
    return p


def prepare(a):
    if not a.prompt.strip():
        raise ValueError('Empty prompt')
    if a.command == 'music':
        if not 3 <= a.seconds <= 600:
            raise ValueError('Music duration must be 3–600 seconds')
        if len(a.prompt) > 4100:
            raise ValueError('Music prompt must be <= 4100 characters')
        endpoint = '/v1/music'
        payload = {'prompt': a.prompt, 'music_length_ms': int(round(a.seconds * 1000)),
                   'model_id': a.model, 'force_instrumental': not a.allow_vocals}
    else:
        if not 0.5 <= a.seconds <= 30:
            raise ValueError('SFX duration must be 0.5–30 seconds')
        if not 0 <= a.prompt_influence <= 1:
            raise ValueError('prompt influence must be in range 0–1')
        endpoint = '/v1/sound-generation'
        payload = {'text': a.prompt, 'duration_seconds': a.seconds, 'loop': a.loop,
                   'model_id': a.model, 'prompt_influence': a.prompt_influence}
    out = Path(a.output).expanduser().resolve()
    if out.suffix.lower() not in ('.mp3','.ogg','.wav'):
        raise ValueError('Output must end with .mp3, .ogg or .wav')
    if out.exists():
        raise ValueError('Refusing to overwrite existing output: ' + str(out))
    if a.output_format != 'auto' and not a.output_format.startswith('mp3_'):
        raise ValueError('This version supports only auto or mp3_* API formats; use ffmpeg for WAV/OGG')
    estimate = a.seconds * RATES[a.command]
    if a.max_estimated_credits is not None and estimate > a.max_estimated_credits:
        raise ValueError(f'Budget guard: estimated {estimate:g} exceeds limit {a.max_estimated_credits:g}')
    return endpoint, payload, out, estimate


def ffmpeg_probe(a, path):
    if a.no_analysis or not shutil.which(a.ffmpeg):
        return {'status': 'skipped', 'reason': 'ffmpeg missing or disabled'}
    # volumedetect works on decoded PCM and reports max/mean dBFS.
    cmd = [a.ffmpeg, '-hide_banner', '-nostdin', '-i', str(path), '-af', 'volumedetect', '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    import re
    log = result.stderr
    mean = re.search(r'mean_volume:\s*(-?[\d.]+) dB', log)
    maximum = re.search(r'max_volume:\s*(-?[\d.]+) dB', log)
    info = {'status': 'ok' if result.returncode == 0 else 'analysis_failed',
            'mean_dbfs': float(mean.group(1)) if mean else None,
            'max_dbfs': float(maximum.group(1)) if maximum else None}
    info['possibly_silent'] = info['max_dbfs'] is not None and info['max_dbfs'] < -35
    if result.returncode != 0:
        info['error'] = log[-500:]
    return info


def generate(a):
    endpoint, payload, out, estimate = prepare(a)
    print(json.dumps({'mode': a.command, 'model': a.model, 'seconds': a.seconds,
                      'estimated_credits': estimate, 'estimate_basis': 'user observations; not an API quote',
                      'output': str(out), 'dry_run': a.dry_run}, ensure_ascii=False, indent=2))
    if a.dry_run:
        print('DRY RUN: no API request and no charges.')
        return 0
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not key:
        raise ValueError('Set ELEVENLABS_API_KEY in the environment')
    if not a.yes:
        if not sys.stdin.isatty():
            raise ValueError('Noninteractive generation requires --yes (only with prior user authorization)')
        if input('Paid generation request. Type YES to continue: ').strip() != 'YES':
            print('Cancelled without an API request.')
            return 0
    query = '' if a.output_format == 'auto' else '?' + urllib.parse.urlencode({'output_format': a.output_format})
    req = urllib.request.Request(API + endpoint + query,
        data=json.dumps(payload).encode('utf-8'), method='POST',
        headers={'xi-api-key': key, 'Content-Type':'application/json', 'Accept':'audio/mpeg'})
    # No automatic retries: an ambiguous network error could mean charged generation.
    try:
        with urllib.request.urlopen(req, timeout=900) as response:
            headers = dict(response.headers.items())
            content_type = response.headers.get('Content-Type', '')
            if 'audio' not in content_type and 'octet-stream' not in content_type:
                raise RuntimeError('Unexpected response content type: ' + content_type)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                temp_path = Path(tmp.name)
                shutil.copyfileobj(response, tmp)
    except urllib.error.HTTPError as err:
        detail = err.read(1500).decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {err.code}: {detail}') from err
    try:
        if temp_path.stat().st_size == 0:
            raise RuntimeError('Empty response audio')
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == '.mp3':
            shutil.move(str(temp_path), str(out))
        else:
            if not shutil.which(a.ffmpeg):
                raise RuntimeError('ffmpeg is required for WAV/OGG output')
            cmd = [a.ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(temp_path)]
            cmd += ['-c:a','libvorbis','-q:a','5'] if out.suffix.lower() == '.ogg' else ['-c:a','pcm_s16le']
            cmd += [str(out)]
            subprocess.run(cmd, check=True, timeout=180)
        quality = ffmpeg_probe(a, out)
        cost_raw = next((v for k,v in headers.items() if k.lower() == 'character-cost'), None)
        observed = None
        try:
            observed = int(cost_raw) if cost_raw is not None else None
        except ValueError:
            pass
        meta = {'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'type':a.command,
                'model':a.model, 'prompt':a.prompt, 'duration_requested_seconds':a.seconds,
                'output':str(out), 'estimated_credits':estimate, 'observed_character_cost':observed,
                'billing_note':'character-cost is a response header; verify account dashboard',
                'song_id':next((v for k,v in headers.items() if k.lower() == 'song-id'), None),
                'output_bytes':out.stat().st_size, 'analysis':quality,
                'quality_status':'review_required' if quality.get('possibly_silent') else 'listen_required'}
        meta_path = out.with_suffix(out.suffix + '.json')
        meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2), encoding='utf-8')
        print(json.dumps({'saved': str(out), 'metadata':str(meta_path), 'actual_character_cost':observed,
                          'quality':quality}, ensure_ascii=False, indent=2))
        if quality.get('possibly_silent'):
            print('WARNING: low peak volume; listen before use. No automatic regeneration.', file=sys.stderr)
        return 0
    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        sys.exit(generate(parser().parse_args()))
    except (ValueError, RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(1)
