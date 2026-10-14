# レジスタ記録からリソースへの変換

## 入力JSON

ゲーム固有の解析器が次の形式を書き出す。数値はJSONの整数。以下はROMの楽曲ではなく、テスト用の矩形波。

```json
{
  "format_version": 1,
  "tracks": [
    {
      "name": "test-pulse",
      "frames": 30,
      "register_writes": [[0, 17, 128], [0, 18, 242], [0, 19, 0], [0, 20, 132], [30, 18, 0]],
      "channel_loops": {}
    }
  ]
}
```

- `name`: リソース内で一意な曲/SE名。ゲームでの意味や優先順位は呼び出し側で決める。
- `frames`: 記録区間の長さ。正の整数。`frames` と同じフレームの停止転送も記録できる。
- `register_writes`: `[frame, register, value]` の列。時刻は昇順、同フレームの順序はドライバーの転送順。`register` は `$10～$26 / $30～$3F` または `$FF10～$FF26 / $FF30～$FF3F`。値は0～255。
- `channel_loops`: 任意。例 `{"0": [192, 2304], "1": [0, 2112]}`。0～3はGBチャンネル、値は `[冒頭の終了/ループ開始フレーム, ループ終了フレーム]`。未指定チャンネルは有限再生。区間は `0 <= start < end <= frames`。
- `frame_rate`: 文書全体で任意。既定値は `4194304 / 70224`。音楽ドライバーがタイマー割り込みなど別周期ならその周期を設定する。転送間隔が不定なら、アダプターで一定の細かな時間単位へ正しく換算する。
- `source_rom_sha256`: 任意。入力ROMのSHA-256。ROM本体をJSONに入れない。

各トラックは音源状態0から開始する。開始前の設定へ依存する場合は、初期レジスタ値・波形RAM・トリガーをフレーム0へ追加する。SEがゲームの前の音源状態へ依存するなら、その依存をアダプターで扱う。

## CLI

プロジェクトのPython環境から、スキルフォルダー内のスクリプトへ絶対パスを指定して実行する。Windowsでもシェルをまたがず実行できる。

```powershell
.\.venv\Scripts\python.exe <skill-directory>/scripts/trace_to_pyxres.py --input audio-traces.json --output assets/audio.pyxres
```

`--sound-base` と `--music-base` で割り当ての開始位置、`--gain` で独自音色の利得を変えられる。変換はウィンドウを開かずに行う。出力は独立した音声用リソースで、画像・背景の既存リソースを上書きするためには使わない。バンク数が足りない場合は、トラックの分割/統合や必要な音のみの抽出をプロジェクト側で判断する。

`--speed` は元トレースを基準とする正の有限倍率（既定1.0）。例えば `--speed 1.7` は、元の制御をモデル化してから音符・音量・音色列を同じ位置から選び、列長を約1/1.7にする。音高・独自波形は変えず、元JSONも書き換えない。再変換は常に元トレースから行い、倍率を累積させない。[GBCの時間基準とテンポ補正](gbc-tempo.md) で適用条件と検証方法を確認する。

## 出力

標準の `pyxel_resource.toml` に加え、ZIPメンバー `gb_audio.json` に独自 `Tone`、各SOUNDの音色列、4チャンネルの対応、冒頭/ループ情報、抽出元を保存する。同名の `.json` にも同じ内容を書き出す。

波形RAMの値から独自音色を自動で登録するため、音色番号はゲーム/トレースごとに変わる。固定の番号を呼び出し側で推測しない。各チャンネルの音符・音量・音色は120Hzでサンプリングされる。矩形波の4つのデューティ比、短周期/長周期ノイズ、波形RAMから取り出した各波形を保持する。

Pyxel標準エディタは独自 `Tone` を表示・保存しないため、SOUNDには標準音色のプレビューを保存する。実行時に埋め込み定義を復元する。エディタがZIPの追加メンバーを削除した場合は同名 `.json` がバックアップ。試聴時とゲーム内で音色が異なる点を説明する。

速度補正のメタデータは `playback_speed`、`source_frame_rate`、`playback_frame_rate` と各クリップの `source_intro_ticks`、`playback_ticks` に保存する。`frame_rate`・`frames` は元トレースの時間基準のまま、`intro_ticks` は補正後の実際の列長。`playback_frame_rate = source_frame_rate * playback_speed` は長さ表示のための換算値で、実際のAPU更新周波数を測定した値ではない。再生境界・ループ尺は実際のSOUNDの長さから求める。

## 実行時

`pyxel_audio_runtime.py` をゲームへコピーするか、同等の処理を組み込む。このファイルはROM・解析用コードへ依存しない。

```python
import pyxel
from pyxel_audio_runtime import load_audio, channel_plan

pyxel.init(160, 144)
audio = load_audio(pyxel, "assets/audio.pyxres")
plan = channel_plan(pyxel, audio, "test-pulse", 0, elapsed=0.0)
if plan:
    pyxel.play(0, plan["sounds"], sec=plan["sec"], loop=plan["loop"])
```

`channel_plan` は有限曲の終了後や空チャンネルでは `None`。冒頭の間は全区間を非ループで再生し、冒頭終了後はループ用SOUNDだけを繰り返す計画を返す。呼び出し側は曲変更・SE終了時・冒頭境界で計画を再計算する。毎フレーム `pyxel.play` を呼んで音を再トリガーしない。

ゲーム側は、現在の曲・経過時間・各チャンネルの所有者・SEの終了フレームを保持する。BGMの経過時間はSE中も進め、ポーズ中は停止するなど、原作の規則に合わせる。末尾の空チャンネルは読み込み側が4チャンネルへ補完する。
