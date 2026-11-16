#!/usr/bin/env python3
"""OpenAI-compatible Images API client for game assets. No third-party Python dependencies.

Subcommands:
  check     show the resolved endpoint and whether the API key env var is set (never its value)
  generate  POST {base}/images/generations
  edit      POST {base}/images/edits (multipart; reference images and optional mask)

The API key is read only from an environment variable (default OPENAI_API_KEY, override with
--api-key-env or "api_key_env" in the config file). There is intentionally no option or config
field that accepts the key value itself. generate/edit are dry runs unless --execute is given.

Endpoint settings can live in a JSON config file: --config PATH, else $IMAGEGEN_CONFIG, else
./imagegen.config.json if present. Precedence: command line > config file > env vars > defaults.
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = 'https://api.openai.com/v1'
DEFAULT_MODEL = 'gpt-image-1'
DEFAULT_KEY_ENV = 'OPENAI_API_KEY'
DEFAULT_BASE_URL_ENV = 'OPENAI_BASE_URL'
MODEL_ENV = 'IMAGEGEN_MODEL'
CONFIG_ENV = 'IMAGEGEN_CONFIG'
CONFIG_NAME = 'imagegen.config.json'
CONFIG_FIELDS = {'base_url': str, 'model': str, 'api_key_env': str, 'base_url_env': str,
                 'no_auth': bool, 'params': dict}
RESERVED_PARAMS = {'model', 'prompt', 'n', 'image', 'image[]', 'mask'}
SECRET_KEYS = frozenset({'api_key', 'apikey', 'x_api_key', 'authorization', 'proxy_authorization', 'cookie',
                         'password', 'secret', 'client_secret', 'token', 'access_token', 'refresh_token', 'bearer'})
FORMAT_SUFFIXES = {'png': ('.png',), 'webp': ('.webp',), 'jpeg': ('.jpg', '.jpeg')}
SOFT_MAX_N = 4
HARD_MAX_N = 10
ERROR_LIMIT = 2048
USER_AGENT = 'openai-compatible-imagegen-skill/0.1'


class SkillError(RuntimeError):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def mask_secret(text, secret):
    text = str(text)
    if secret:
        text = text.replace(secret, '***')
    return text


def is_secret_key(name):
    # Exact names only: usage fields such as input_tokens / total_tokens must survive.
    return str(name).lower().replace('-', '_') in SECRET_KEYS


def sanitize(value):
    """Drop any mapping key that names a credential, recursively."""
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if not is_secret_key(k)}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


# ---------------------------------------------------------------- config

def find_secret_keys(value, prefix=''):
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if is_secret_key(k):
                found.append(prefix + str(k))
            found += find_secret_keys(v, f'{prefix}{k}.')
    elif isinstance(value, list):
        for v in value:
            found += find_secret_keys(v, prefix)
    return found


def load_config_file(path_arg):
    """Return (config dict, path or None). Keys starting with '_' or '$' are comments."""
    if path_arg:
        path, explicit = Path(path_arg), True
    elif os.environ.get(CONFIG_ENV):
        path, explicit = Path(os.environ[CONFIG_ENV]), True
    else:
        path, explicit = Path.cwd() / CONFIG_NAME, False
    if not path.is_file():
        if explicit:
            raise SkillError(f'Config file not found: {path}')
        return {}, None
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise SkillError(f'Config file {path} is not valid JSON: {exc}') from None
    if not isinstance(data, dict):
        raise SkillError(f'Config file {path} must contain a JSON object')
    secrets = find_secret_keys(data)
    if secrets:
        raise SkillError(f'Config file {path} contains credential fields ({", ".join(secrets)}). '
                         'Never store API keys in files: remove them and set "api_key_env" to the '
                         'NAME of the environment variable that holds the key.')
    data = {k: v for k, v in data.items() if not str(k).startswith(('_', '$'))}
    unknown = sorted(set(data) - set(CONFIG_FIELDS))
    if unknown:
        raise SkillError(f'Unknown field(s) in {path}: {", ".join(unknown)} '
                         f'(allowed: {", ".join(CONFIG_FIELDS)})')
    for name, kind in CONFIG_FIELDS.items():
        if name in data and not isinstance(data[name], kind):
            raise SkillError(f'Config field "{name}" in {path} must be a {kind.__name__}')
    for name in ('api_key_env', 'base_url_env'):
        if name in data and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', data[name]):
            raise SkillError(f'Config field "{name}" must be an environment variable NAME, not a value')
    reserved = sorted(RESERVED_PARAMS & set(data.get('params', {})))
    if reserved:
        raise SkillError(f'Config "params" must not set {", ".join(reserved)} (use "model" at the top level)')
    return data, path


def pick(*candidates):
    """First non-empty (value, source) pair."""
    for value, source in candidates:
        if value not in (None, ''):
            return value, source
    raise AssertionError('no default supplied')


def resolve_config(args):
    conf, conf_path = load_config_file(getattr(args, 'config', None))
    sources = {}
    base_url_env, _ = pick((args.base_url_env, 'cli'), (conf.get('base_url_env'), 'config'),
                           (DEFAULT_BASE_URL_ENV, 'default'))
    base_url, sources['base_url'] = pick(
        (args.base_url, '--base-url'), (conf.get('base_url'), 'config'),
        (os.environ.get(base_url_env), f'env {base_url_env}'), (DEFAULT_BASE_URL, 'default'))
    base_url = base_url.strip().rstrip('/')
    parts = urlsplit(base_url)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        raise SkillError(f'Invalid base URL: {base_url!r} (expected http(s)://host[:port]/v1)')
    if parts.username or parts.password:
        raise SkillError('Do not embed credentials in the base URL; use the API key env var instead')
    model, sources['model'] = pick(
        (getattr(args, 'model', None), '--model'), (conf.get('model'), 'config'),
        (os.environ.get(MODEL_ENV), f'env {MODEL_ENV}'), (DEFAULT_MODEL, 'default'))
    key_env, sources['api_key_env'] = pick((args.api_key_env, '--api-key-env'),
                                           (conf.get('api_key_env'), 'config'), (DEFAULT_KEY_ENV, 'default'))
    no_auth = bool(args.no_auth or conf.get('no_auth'))
    key = None if no_auth else (os.environ.get(key_env) or None)
    return {'base_url': base_url, 'host': parts.netloc, 'key_env': key_env, 'key': key,
            'no_auth': no_auth, 'model': model, 'params': conf.get('params', {}),
            'config_path': str(conf_path) if conf_path else None, 'sources': sources,
            'base_url_env': base_url_env}


def auth_summary(cfg):
    if cfg['no_auth']:
        return 'none (no_auth)'
    return f"env {cfg['key_env']} ({'set' if cfg['key'] else 'NOT SET'})"


_resolved_key = None  # remembered so main() can mask it in any error text


def require_key(cfg):
    if cfg['no_auth']:
        return None
    if not cfg['key']:
        raise SkillError(f"{cfg['key_env']} is not set. Set it in the environment of the agent process "
                         '(or choose another variable with --api-key-env / "api_key_env" in the config, '
                         'or use no_auth for a local server).')
    global _resolved_key
    _resolved_key = cfg['key']
    return cfg['key']


# ---------------------------------------------------------------- http

def encode_multipart(fields, files):
    """fields: [(name, str)], files: [(name, Path)] -> (body, content_type)."""
    boundary = '----imagegen' + uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts += [f'--{boundary}\r\n'.encode(),
                  f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                  str(value).encode('utf-8'), b'\r\n']
    for name, path in files:
        ctype = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        parts += [f'--{boundary}\r\n'.encode(),
                  f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'.encode(),
                  f'Content-Type: {ctype}\r\n\r\n'.encode(),
                  path.read_bytes(), b'\r\n']
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), 'multipart/form-data; boundary=' + boundary


def http(method, url, key, *, body=None, content_type=None, timeout=300):
    headers = {'Accept': 'application/json', 'User-Agent': USER_AGENT}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    if content_type:
        headers['Content-Type'] = content_type
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.headers.get('Content-Type', ''), response.read()
    except HTTPError as exc:
        message = exc.read(ERROR_LIMIT).decode('utf-8', errors='replace')
        raise SkillError(mask_secret(f'HTTP {exc.code}: {message}', key)) from None
    except URLError as exc:
        raise SkillError(mask_secret(f'Network error: {exc.reason}', key)) from None


def download(url, timeout):
    """Fetch a result URL. The API key is never sent to it (it may be a third-party CDN)."""
    if urlsplit(url).scheme not in ('http', 'https'):
        raise SkillError(f'Refusing to download non-http(s) result URL: {url[:120]!r}')
    status, ctype, body = http('GET', url, None, timeout=timeout)
    if status != 200 or not body:
        raise SkillError(f'Result download failed: HTTP {status}')
    return body


# ---------------------------------------------------------------- request building

def read_prompt(args):
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding='utf-8')
    else:
        prompt = args.prompt or ''
    prompt = prompt.strip()
    if not prompt:
        raise SkillError('Prompt must not be empty (--prompt or --prompt-file)')
    return prompt


def output_format(args):
    suffix = Path(args.output).suffix.lower()
    for fmt, suffixes in FORMAT_SUFFIXES.items():
        if suffix in suffixes:
            return fmt
    raise SkillError('--output must end with .png, .webp, .jpg or .jpeg')


def output_paths(output, count):
    output = Path(output)
    if count == 1:
        return [output]
    return [output.with_name(f'{output.stem}-{i}{output.suffix}') for i in range(1, count + 1)]


def sidecar(path):
    return path.with_name(path.name + '.json')


def build_params(args, cfg, prompt, fmt):
    if not 1 <= args.n <= HARD_MAX_N:
        raise SkillError(f'--n must be between 1 and {HARD_MAX_N}')
    if args.n > SOFT_MAX_N and not args.allow_many:
        raise SkillError(f'--n above {SOFT_MAX_N} requires --allow-many (each image is billed)')
    params = {'model': cfg['model'], 'prompt': prompt, 'n': args.n}
    # Only explicitly requested optional params are sent; compatible servers reject unknown ones.
    # Order: config "params" < command-line options < --extra-json.
    params.update(cfg.get('params', {}))
    for name in ('size', 'quality', 'background', 'output_format', 'response_format', 'seed'):
        value = getattr(args, name, None)
        if value is not None:
            params[name] = value
    if args.extra_json:
        try:
            extra = json.loads(args.extra_json)
        except json.JSONDecodeError as exc:
            raise SkillError(f'--extra-json is not valid JSON: {exc}') from None
        if not isinstance(extra, dict):
            raise SkillError('--extra-json must be a JSON object')
        if find_secret_keys(extra):
            raise SkillError('--extra-json must not contain credentials')
        params.update(extra)
    if params.get('background') == 'transparent' and fmt == 'jpeg':
        raise SkillError('Transparent background needs .png or .webp output')
    out_fmt = params.get('output_format')
    if out_fmt is not None and fmt != out_fmt:
        raise SkillError(f'--output extension does not match output_format {out_fmt!r}')
    size = params.get('size')
    if size is not None and not re.fullmatch(r'\d+x\d+|auto', str(size)):
        raise SkillError('size must look like 1024x1024 or auto')
    return params


def check_input(path_str, allow_external):
    path = Path(path_str)
    if not path.is_file():
        raise SkillError(f'Input image not found: {path}')
    if not allow_external:
        cwd = Path.cwd().resolve()
        if cwd != path.resolve() and cwd not in path.resolve().parents:
            raise SkillError(f'Input outside the project: {path} (copy it in, or pass --allow-external-inputs)')
    return path


def image_kind(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if data[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    return None


# ---------------------------------------------------------------- commands

def cmd_check(args):
    cfg = resolve_config(args)
    info = {'config_file': cfg['config_path'] or f'none ({CONFIG_NAME} not found in current directory)',
            'base_url': cfg['base_url'], 'auth': auth_summary(cfg), 'model': cfg['model'],
            'default_params': cfg['params'], 'sources': cfg['sources']}
    if args.live:
        key = require_key(cfg)
        status, _, body = http('GET', cfg['base_url'] + '/models', key, timeout=args.http_timeout)
        info['models_status'] = status
        try:
            ids = [m.get('id') for m in json.loads(body).get('data', [])]
            info['models'] = ids[:100]
        except (ValueError, AttributeError):
            info['models'] = None
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def run_images(args, endpoint):
    cfg = resolve_config(args)
    prompt = read_prompt(args)
    fmt = output_format(args)
    params = build_params(args, cfg, prompt, fmt)
    inputs, mask = [], None
    if endpoint == 'edits':
        if not args.image:
            raise SkillError('edit needs at least one --image')
        inputs = [check_input(p, args.allow_external_inputs) for p in args.image]
        if args.mask:
            mask = check_input(args.mask, args.allow_external_inputs)
    outputs = output_paths(args.output, args.n)
    clashes = [str(p) for o in outputs for p in (o, sidecar(o)) if p.exists()]
    if clashes:
        raise SkillError('Refusing to overwrite existing files: ' + ', '.join(clashes))

    url = f"{cfg['base_url']}/images/{endpoint}"
    preview = {'config_file': cfg['config_path'], 'endpoint': url, 'auth': auth_summary(cfg), 'params': params,
               'inputs': [str(p) for p in inputs], 'mask': str(mask) if mask else None,
               'outputs': [str(p) for p in outputs],
               'billing_note': 'Images are billed by the provider per image/token; no price is estimated here.'}
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if not args.execute:
        print('DRY RUN: no API request was made. Re-run with --execute after the user approves this request.')
        return 0
    key = require_key(cfg)

    if endpoint == 'edits':
        field = args.image_field or ('image' if len(inputs) == 1 else 'image[]')
        fields = [(k, json.dumps(v) if isinstance(v, (dict, list, bool)) else v) for k, v in params.items()]
        files = [(field, p) for p in inputs] + ([('mask', mask)] if mask else [])
        body, ctype = encode_multipart(fields, files)
    else:
        body, ctype = json.dumps(params).encode('utf-8'), 'application/json'
    status, _, raw = http('POST', url, key, body=body, content_type=ctype, timeout=args.http_timeout)

    try:
        response = json.loads(raw)
        items = response['data']
        if not isinstance(items, list) or not items:
            raise ValueError('empty data')
    except (ValueError, KeyError, TypeError) as exc:
        dump = sidecar(outputs[0]).with_name(outputs[0].name + '.response.txt')
        dump.parent.mkdir(parents=True, exist_ok=True)
        dump.write_bytes(raw[:1_000_000])
        raise SkillError(f'Unexpected response (HTTP {status}, {exc}); raw body saved to {dump}') from None
    return save_results(args, cfg, endpoint, params, inputs, mask, response, items, outputs)


def save_results(args, cfg, endpoint, params, inputs, mask, response, items, outputs):
    if len(items) > len(outputs):  # server returned more than requested; keep given names, append more
        base = Path(args.output)
        outputs = outputs + [base.with_name(f'{base.stem}-{i}{base.suffix}')
                             for i in range(len(outputs) + 1, len(items) + 1)]
    common = {'tool': USER_AGENT, 'endpoint': f'/images/{endpoint}', 'base_url_host': cfg['host'],
              'config_file': cfg['config_path'],
              'params': dict(params), 'inputs': [str(p) for p in inputs],
              'mask': str(mask) if mask else None, 'response_created': response.get('created'),
              'usage': response.get('usage'), 'completed_at': stamp()}
    for key in ('background', 'output_format', 'quality', 'size'):
        if key in response:
            common['response_' + key] = response[key]
    saved = []
    for index, (item, out) in enumerate(zip(items, outputs), 1):
        if out.exists():
            print(f'WARNING: {out} appeared during the request; skipping', file=sys.stderr)
            continue
        if item.get('b64_json'):
            data = base64.b64decode(item['b64_json'])
        elif item.get('url'):
            data = download(item['url'], args.http_timeout)
        else:
            print(f'WARNING: result {index} has neither b64_json nor url; skipping', file=sys.stderr)
            continue
        kind = image_kind(data)
        expected = output_format(args)
        if kind and kind != expected:
            print(f'WARNING: server returned {kind} data but output is {out.suffix}; saved as-is', file=sys.stderr)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        meta = dict(common, index=index, output=str(out), bytes=len(data), detected_format=kind,
                    revised_prompt=item.get('revised_prompt'))
        write_json(sidecar(out), sanitize(meta))
        saved.append(str(out))
        print('Saved: ' + str(out))
    if not saved:
        raise SkillError('No images were saved from the response')
    return 0


# ---------------------------------------------------------------- cli

def add_common(p):
    p.add_argument('--config', help=f'JSON config file (default: ${CONFIG_ENV}, else ./{CONFIG_NAME} if present)')
    p.add_argument('--base-url', help=f'API base URL including /v1 (default: config, ${DEFAULT_BASE_URL_ENV}, {DEFAULT_BASE_URL})')
    p.add_argument('--base-url-env', help=f'env var holding the base URL (default {DEFAULT_BASE_URL_ENV})')
    p.add_argument('--api-key-env', help=f'env var holding the API key (default: config, {DEFAULT_KEY_ENV}); the value itself is never accepted')
    p.add_argument('--no-auth', action='store_true', help='send no Authorization header (local servers)')
    p.add_argument('--http-timeout', type=float, default=300)


def add_image_args(p):
    add_common(p)
    p.add_argument('--model', help=f'model id (default: config, ${MODEL_ENV}, {DEFAULT_MODEL})')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prompt')
    g.add_argument('--prompt-file')
    p.add_argument('--output', required=True, help='output image path; n>1 adds -1, -2 ... suffixes')
    p.add_argument('--n', type=int, default=1)
    p.add_argument('--allow-many', action='store_true', help=f'allow --n above {SOFT_MAX_N}')
    p.add_argument('--size', help='e.g. 1024x1024, 1024x1536, 1536x1024, auto')
    p.add_argument('--quality', help='provider-specific, e.g. low|medium|high|auto (gpt-image) or standard|hd')
    p.add_argument('--background', choices=['transparent', 'opaque', 'auto'])
    p.add_argument('--output-format', choices=list(FORMAT_SUFFIXES), help='sent to the API only when given')
    p.add_argument('--response-format', choices=['b64_json', 'url'], help='only for servers that accept it (gpt-image rejects it)')
    p.add_argument('--seed', type=int, help='only for servers that support a seed')
    p.add_argument('--extra-json', help='JSON object of provider-specific params merged into the request')
    p.add_argument('--execute', action='store_true', help='actually call the API (billed)')


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('check', help='show resolved endpoint/auth; --live lists models')
    add_common(p)
    p.add_argument('--model')
    p.add_argument('--live', action='store_true', help='GET /models to test the connection')
    p.set_defaults(func=cmd_check)
    p = sub.add_parser('generate', help='text-to-image')
    add_image_args(p)
    p.set_defaults(func=lambda a: run_images(a, 'generations'))
    p = sub.add_parser('edit', help='image edit / reference-guided generation')
    add_image_args(p)
    p.add_argument('--image', action='append', help='input image (repeatable)')
    p.add_argument('--mask', help='PNG mask; transparent pixels mark the area to change')
    p.add_argument('--image-field', help='multipart field name override (default image, or image[] for several)')
    p.add_argument('--allow-external-inputs', action='store_true')
    p.set_defaults(func=lambda a: run_images(a, 'edits'))
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (SkillError, OSError, ValueError) as exc:
        text = mask_secret(exc, _resolved_key)
        text = mask_secret(text, os.environ.get(getattr(args, 'api_key_env', None) or DEFAULT_KEY_ENV))
        print('ERROR: ' + text, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
