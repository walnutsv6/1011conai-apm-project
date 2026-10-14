# 入力と組み込み

## 曲目情報

プレイヤーフォルダーには `player.py`、`audio_runtime.py`、`catalog.json`、既存の音声リソースを置く。catalogは次の最小形式で、音声の再抽出は不要。

```json
{
  "player_title": "Example BGM Player",
  "tracks": [
    {"name": "bgm_10", "resource": "resources/bgm_10.pyxres", "display_name": "10  BGM"}
  ]
}
```

`resource` はcatalogからの相対パス、`name` は音声の `clips` のキー。`player_title` と `display_name` は任意。ひな型はPyxel標準フォントを使うため、表示名は英数字にするか、対象プロジェクトで日本語フォントを組み込む。曲ID・正式な曲名・元ROM名を推測で補わない。

`gb-audio-to-pyxres` の既存catalogは `name` と `resource` を持つためそのまま読める。対象ゲームのタイトルと表示名を追加してよい。テンポ補正は音声リソースに既に反映された値を維持する。

## 音声メタデータ

ひな型は `.pyxres` のZIPメンバー `gb_audio.json` を読み、なければ同名 `.json` を読む。`format_version=1`、`tone_base`、独自 `tones`、各SOUNDの `sound_tones`、`clips[name]` 内の `music`、4チャンネルの `channels`、`loops`、`intro_ticks`、文書の `tick_rate` を使用する。普通のエディター製リソースなど別の形式を使う場合は、入力形式に対応したロード・再生計画へ適応する。

独自音色を復元し、Pyxelが末尾の空チャンネルを省略しても4チャンネルへ補完する。原トレースのフレーム数やカタログの概算秒数から再生境界を決めず、冒頭の `intro_ticks / tick_rate` とネイティブSOUNDの `total_sec()` を使う。各チャンネルの独立した周期を維持する。

一時停止時は現在位置を保存して全チャンネルを停止する。再開時は保存位置に対して各チャンネルの `channel_plan()` を再計算し、冒頭の途中なら冒頭の残りを、ループ中ならその周期内の位置を再生する。選曲とリスタートでは位置を0へ戻すが、再生状態を維持する。
