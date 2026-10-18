# 個人開発用 APM パッケージ集

[@microsoft/apm](https://github.com/microsoft/apm) で必要なカテゴリだけ導入できるパッケージ集です。リポジトリ直下の各カテゴリが独立したAPMパッケージです。

| パッケージ | 内容 |
| --- | --- |
| `audio-generation/elevenlabs-api` | ElevenLabs APIでゲーム用BGM・効果音を生成する `elevenlabs-audio` |
| `audio-generation/stable-audio-api` | Stable Audio 3.0 APIでゲーム用BGM・効果音を生成する `stable-audio-generation` |
| `development` | 共通の開発方針、実装レビュー担当、`issue-implementation` |
| `game-audio` | `gb-audio-to-pyxres`、`pyxel-bgm-player` |
| `novelai` | `novelai-imagegen`、`novelai-variations`、`novelai-strip-sequence`、`novelai-gravure-book` |
| `novelai-metadata` | 既存のNovelAI PNG画像から生成メタデータをJSONへ抽出する `novelai-metadata` |
| `tetris` | `tetris-spec-interviewer` |

各スキルの参照資料・スクリプト・サンプルは、スキルと一緒に配布されます。

## インストール

[APM公式の手順](https://microsoft.github.io/apm/quickstart/)でCLIを導入し、利用するプロジェクトで必要なパッケージを指定します。以下のGitHub経由の例は、この変更をコミットして公開した後に使えます。次はCodex向けの例です。

```bash
apm install walnutsv6/1011conai-apm-project/tetris --target codex
apm install walnutsv6/1011conai-apm-project/game-audio --target codex
apm install walnutsv6/1011conai-apm-project/novelai-metadata --target codex
apm install walnutsv6/1011conai-apm-project/audio-generation/stable-audio-api --target codex
```

カテゴリ内の1スキルだけが必要なら `--skill` で選べます。

```bash
apm install walnutsv6/1011conai-apm-project/game-audio --skill pyxel-bgm-player --target codex
apm install walnutsv6/1011conai-apm-project/novelai --skill novelai-imagegen --target codex
```

`novelai-variations`、`novelai-strip-sequence`、`novelai-gravure-book` は `novelai-imagegen` の手順とスクリプトを使います。これらを選ぶ場合は `novelai-imagegen` も導入してください。

`novelai-metadata` は画像生成用の `novelai` パッケージとは独立しています。抽出スクリプトの実行には Python 3 と Pillow が必要です。PNGのalphaチャネルに埋め込まれたメタデータを優先し、見つからない場合はNovelAI由来のPNGテキストを読み取ります。

`audio-generation` 配下の各パッケージは生成APIごとに独立しています。どちらもPython標準ライブラリのみで動作し、実際の生成にはそれぞれ `ELEVENLABS_API_KEY` / `STABILITY_API_KEY` 環境変数が必要です（OGG/WAV変換や音量確認にはFFmpegを使います）。生成は有料のため、スキルは必ずdry-runで見積もりを提示し、ユーザーの承認後にのみAPIを呼び出します。

NovelAIパッケージには、性的描写を含む画像の制作ガイドラインと、該当する依頼でそのガイドラインを参照するInstructionを含めています。ガイドラインは`novelai-imagegen`スキルの参照資料として配布されます。Codexの`AGENTS.md`へInstructionを反映する場合は、NovelAIパッケージを導入した利用プロジェクトで`apm compile --target codex`を実行します。

```bash
apm install walnutsv6/1011conai-apm-project/novelai --skill novelai-imagegen --skill novelai-variations --target codex
```

手元の未公開の変更を試す場合は、**このリポジトリの外**に利用プロジェクトを用意し、ローカルパスでカテゴリを指定します。例: `apm install /path/to/repo/tetris --target codex`。APMはスキルを `.agents/skills/` に配置します。

## 共通の開発方針

開発方針やレビュー担当が必要なときだけ `development` を追加します。

```bash
apm install walnutsv6/1011conai-apm-project/development --target codex
apm compile --target codex
```

全体に適用する指示は `development/.apm/instructions/` に置きます。対象を限定する指示にのみ `applyTo` を指定します。Claude Codeではインストール時に `.claude/rules/` へ配置されるため、重複を避ける目的で `CLAUDE.md` が生成されない場合があります。

APM v0.33.0でローカルパスから依存パッケージとして導入した検証では、指示ファイルが依存一覧に表示されても `apm compile` は `AGENTS.md` を生成しませんでした。その場合は、必要なパッケージの `.apm/instructions/*.instructions.md` を利用プロジェクトの `.apm/instructions/` にコピーし、再度 `apm compile --target codex` を実行してください。

パッケージを更新した場合は、利用プロジェクトで依存関係を更新してから再インストールしてください。
