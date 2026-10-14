# 個人開発用 APM ハーネスパッケージ

[@microsoft/apm](https://github.com/microsoft/apm) で配布する、個人開発向けのエージェント設定パッケージのひな型です。指示、実装エージェント、スキルをひとつのパッケージとして管理できます。

## パッケージの内容

| 種類 | ファイル | 役割 |
| --- | --- | --- |
| Instruction | `.apm/instructions/development.instructions.md` | リポジトリの調査、最小限の変更、テストを基本とする開発方針 |
| Agent | `.apm/agents/implementation-reviewer.agent.md` | 変更差分の正確性とテスト観点を確認 |
| Skill | `.apm/skills/issue-implementation/SKILL.md` | Issue の理解から実装・検証までの手順 |

## 使い方

1. `apm.yml` の `name`、`description` を自分のパッケージに合わせて変更します。
2. `.apm/` 以下の指示・エージェント・スキルを開発スタイルに合わせて編集し、不要なものは削除します。
3. リポジトリを公開した後、利用するプロジェクトでインストールします。

```bash
apm install <owner>/<repository>
```

インストール後は、利用プロジェクトで `apm install` を実行して設定を反映します。パッケージを更新した場合は、利用プロジェクトで依存関係を更新してから再インストールしてください。

## カスタマイズのポイント

- Instruction の `applyTo` は適用対象のファイルに合わせて調整してください。
- 共通の開発方針は instruction、特定の作業手順は skill、専用の役割は agent に記述します。
- 利用者やプロジェクト固有の規約を追加し、ひな型の汎用的な指示と置き換えてください。
