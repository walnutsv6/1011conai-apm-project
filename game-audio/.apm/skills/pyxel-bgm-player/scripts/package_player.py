"""Build a ROM-free pyxapp and a distribution ZIP containing only two files."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pyxel

SKILL = Path(__file__).resolve().parents[1]


def read_manifest(resource):
    with zipfile.ZipFile(resource) as archive:
        embedded = 'gb_audio.json' in archive.namelist()
        if embedded:
            manifest = json.loads(archive.read('gb_audio.json'))
        else:
            manifest = json.loads(resource.with_suffix('.json').read_text(encoding='utf-8'))
    if manifest.get('format_version') != 1 or 'clips' not in manifest:
        raise ValueError(f'Unsupported audio metadata: {resource}')
    return manifest, embedded


def build(project, output, name, player=None, runtime=None, title=None):
    project, output = Path(project).resolve(), Path(output).resolve()
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', name):
        raise ValueError('App name must use letters, numbers, hyphens or underscores')
    catalog = json.loads((project / 'catalog.json').read_text(encoding='utf-8'))
    if not catalog.get('tracks'):
        raise ValueError('The catalog must contain tracks')
    sources = []
    for entry in catalog['tracks']:
        path = (project / entry['resource']).resolve()
        if not path.is_relative_to(project) or path.suffix.lower() != '.pyxres':
            raise ValueError(f'Resource must be a pyxres inside the project: {path}')
        manifest, embedded = read_manifest(path)
        if entry['name'] not in manifest['clips']:
            raise ValueError(f'Clip {entry["name"]} missing from {path}')
        sources.append((entry, path, embedded))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bgm_package_', dir=output) as temporary:
        stage_root = Path(temporary).resolve()
        assert stage_root.is_relative_to(output)
        stage = stage_root / name
        (stage / 'audio').mkdir(parents=True)
        shutil.copy2(Path(player).resolve() if player else SKILL / 'assets/player.py', stage / 'player.py')
        shutil.copy2(Path(runtime).resolve() if runtime else SKILL / 'assets/audio_runtime.py', stage / 'audio_runtime.py')
        packaged = dict(player_title=title or catalog.get('player_title', 'Pyxel BGM Player'), tracks=[])
        expected = {f'{name}/player.py', f'{name}/audio_runtime.py', f'{name}/catalog.json',
                    f'{name}/{pyxel.APP_STARTUP_SCRIPT_FILE}'}
        for index, (entry, path, embedded) in enumerate(sources):
            relative = f'audio/{index:04d}.pyxres'
            destination = stage / relative
            shutil.copy2(path, destination)
            expected.add(f'{name}/{relative}')
            if not embedded:
                shutil.copy2(path.with_suffix('.json'), destination.with_suffix('.json'))
                expected.add(f'{name}/audio/{index:04d}.json')
            display_name = entry.get('display_name') or entry.get('command_hex') or entry['name']
            packaged['tracks'].append(dict(name=entry['name'], resource=relative, display_name=display_name))
        (stage / 'catalog.json').write_text(json.dumps(packaged, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', '-m', 'pyxel', 'package',
                                 str(stage), str(stage / 'player.py')],
                                cwd=stage_root, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        generated = stage_root / f'{name}.pyxapp'
        with zipfile.ZipFile(generated) as archive:
            if archive.testzip() is not None:
                raise ValueError('Corrupted pyxapp')
            assert set(archive.namelist()) == expected
            assert archive.read(f'{name}/{pyxel.APP_STARTUP_SCRIPT_FILE}').decode('utf-8').strip() == 'player.py'
            assert json.loads(archive.read(f'{name}/catalog.json')) == packaged
        app = output / f'{name}.pyxapp'
        shutil.copy2(generated, app)
    instructions = (
        'BGM player / 再生方法\n\n'
        f'PythonとPyxel {pyxel.VERSION}が必要です。ROMは不要です。\n'
        f'このフォルダーで実行: pyxel play {name}.pyxapp\n'
        f'別の呼び出し方: python -m pyxel play {name}.pyxapp\n\n'
        '起動直後は停止しています。AまたはSpaceで再生してください。\n'
        '選曲: 矢印キー / ゲームパッドの十字キー\n'
        '再生・一時停止・再開: Space / A\n'
        '先頭へ戻す: R / B\n'
        '終了: Esc / START\n\n'
        '停止中・一時停止中の選曲とリスタートは無音を維持します。\n'
        '再生中の選曲は新しい曲を先頭から再生します。\n'
    )
    distribution = output / f'{name}_player.zip'
    with zipfile.ZipFile(distribution, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(app, app.name)
        archive.writestr('PLAY.txt', instructions)
    with zipfile.ZipFile(distribution) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {app.name, 'PLAY.txt'}
        assert archive.read(app.name) == app.read_bytes()
    return app, distribution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--title')
    parser.add_argument('--player', type=Path, help='Optional adapted player.py')
    parser.add_argument('--runtime', type=Path, help='Optional adapted audio_runtime.py')
    args = parser.parse_args()
    app, distribution = build(args.project, args.output, args.name, args.player, args.runtime, args.title)
    print(f'Pyxel {pyxel.VERSION}: {app}')
    print(f'Distribution ZIP (2 files): {distribution}')


if __name__ == '__main__':
    main()
