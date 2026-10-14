# 検証と配布

## 操作の確認

ネイティブPyxelで、起動直後の4チャンネルが無音であることと、A/Spaceまで `pyxel.play()` の呼び出しがないことを確認する。以下をキーボードとゲームパッドの両方で試す。

| 状態と操作 | 期待結果 |
| --- | --- |
| 停止中に選曲、B/R | 無音を維持、位置は先頭 |
| 停止中にA/Space | 選択曲を先頭から再生 |
| 再生中に選曲 | 新しい曲を先頭から再生 |
| 再生中にA/Space | 位置を保存して無音にする |
| 一時停止中に待機 | 位置が進まない |
| 一時停止中に選曲 | 新しい曲の先頭で無音を維持 |
| 一時停止中にA/Space | 現在の選択曲と保存位置で再開 |
| 一時停止中にB/R | 先頭へ戻すが無音を維持 |
| 再生中にB/R | 現在の曲を先頭から再生し直す |
| 有限曲の終了後にA/Space | 先頭から再生 |
| START/Esc | 音を止めて終了 |

方向キーの上下左右、一覧端での選曲、同じ操作のキー/パッド同時入力、A/Spaceの押しっぱなしも確認する。冒頭境界の前後、複数チャンネルの異なる境界、ループ中からの再開、末尾の無音チャンネル、有限ジングルの終了を含める。入力注入でゲームパッド定数の動作を検証した場合はその旨を記録し、実機ゲームパッドで検証したとは表現しない。

共通ひな型のROM不要自己検証:

```powershell
.\.venv\Scripts\python.exe <skill-directory>/scripts/self_test.py
```

## pyxappとZIP

公式の `pyxel package APP_DIR STARTUP_SCRIPT_FILE` を使う。対象プロジェクト全体をパッケージ化せず、再生用ソース、catalog、対象曲のpyxresと必要な音色メタデータだけを専用のステージへコピーする。内蔵メタデータがあるpyxresは同名JSONを省略できる。起動スクリプトの指定と同梱リソースの相対パスが、展開後の配置でも成立することを確認する。

```powershell
.\.venv\Scripts\python.exe <skill-directory>/scripts/package_player.py --project ./player-project --output ./dist --name example-bgm
```

このスクリプトは `player-project/catalog.json` とその対象音声を使い、スキル付属のひな型を既定で同梱する。プロジェクトで調整済みの再生用ソースを使う場合は `--player ./player-project/player.py --runtime ./player-project/audio_runtime.py` を指定する。追加モジュールやフォントが必要なアプリでは、必要なファイルだけを同梱するようプロジェクト側のパッケージ処理へ適応する。

出力は `example-bgm.pyxapp` と `example-bgm_player.zip`。配布ZIP内は次の2ファイル。

```text
example-bgm.pyxapp
PLAY.txt
```

Python/Pyxelを準備した環境で `pyxel play example-bgm.pyxapp` または `python -m pyxel play example-bgm.pyxapp` を実行する。pyxappはアプリと音声のパッケージで、Python/Pyxelのランタイムを含むexeではない。

最終ZIPのCRCと内部の必要ファイルを検査する。別フォルダーへ配布物だけをコピーし、Pyxelの `play` 処理を通して起動・選曲・再生を確認する。開発フォルダーのROM・抽出器・外部の曲ファイルに依存せず、起動直後は無音であることを確認する。

CLIの出力先や起動マーカーの形式はインストールされたPyxelの実装で確認する。確認済みの2.9.9では、出力pyxappはpackageコマンドの作業ディレクトリーに作られる。[Pyxel公式ユーザーガイド](https://kitao.github.io/pyxel/web/user-guide/) と対象環境の `pyxel.cli` を参照する。
