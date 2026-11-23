---
name: novelai-content-level
description: Ask the user which sexual-content level a project allows for NovelAI images (level 1 breasts only / level 2 groin exposure without genitals, current CERO-based / level 3 genitals and pubic hair, EOCS-based) plus two options asked at every level (fluids; hugging/skinship with an exposed female character), record the decision in <agent dir>/novelai-content-level.json, and explain what it changes in novelai-imagegen and its sub-skills (novelai-variations, novelai-strip-sequence, novelai-gravure-book, novelai-strip-game). Requires novelai-imagegen. Use when the user asks to set, change, or check the project's content level / 表現レベル / 性的描写の許可範囲, when starting topless/nude work in a project with no recorded level, or when a runner request fails with CONTENT_LEVEL_VIOLATION and the user wants a different level.
---

# NovelAI 表現レベルのヒアリング

プロジェクトごとに、性的描写をどのレベルまで許可するかをユーザーに確認し、`<agent dir>/novelai-content-level.json`（スキルの配置先フォルダ。Claude Code は `.claude/`、Codex は `.agents/`）に記録する。記録と判定のスクリプトは `novelai-imagegen` に含まれるため、`novelai-imagegen` も導入しておく。以下のコマンドのパスはこのスキルのフォルダからの相対パスで、`<project root>` は利用プロジェクトのルートである。`novelai-imagegen` と派生スキルはこの記録を読んでプロンプトを組み、ランナー（`novelai_image.py`）は記録を超えるリクエストを `CONTENT_LEVEL_VIOLATION` で拒否する。

レベルとは別に、次の2つをオプションとしてレベルにかかわらず確認する。

| オプション | キー | 内容 |
| --- | --- | --- |
| 愛液・白い液体 | `fluids` | 愛液、白い液体が身体や服にかかっている表現 |
| 露出した女性キャラクターへのスキンシップ | `nude_contact` | 全裸（レベル1ではトップレス）の女性キャラクターへの抱擁・キス・愛撫等のスキンシップ。股間への接触は、オプションにかかわらず含めない |

オプションは、ガイドラインで許容されている範囲をさらに絞るためのものであり、ガイドラインの「含めない」を許可するものではない（例: 双方が全裸の抱擁、股間への接触、性行為は、許可しても含めない）。

登場キャラクターが全員18歳以上で、見た目の印象も成人であることは、レベルにかかわらず常に適用する前提である。ヒアリングで確認する項目ではなく、確認の結果によって緩めることもない。

レベルは許可する上限を決めるだけで、ガイドラインの他の基準（成人であること・成人に見えること、自主的な行動、性行為を描かない、画像セットの一部として制作、背景、公開前の人間による確認）は、どのレベルでも緩めない。トップレス・ヌード画像を生成せずプロンプトとユーザー実行スクリプトまでにとどめる運用（パッケージの Instruction `sexual-content`）も、レベルにかかわらず変わらない。

## レベル

| レベル | ID | 許可する上限 | 想定する基準 |
| --- | --- | --- | --- |
| 1 | `topless` | 乳房の露出まで。股間の露出・パンティーの脱衣は不可 | 15歳以上推奨〜15歳未満禁止相当の作品 |
| 2 | `cero` | 股間の露出まで。性器・陰毛の描写は不可 | 現行ガイドライン・CERO基準（記録がない場合の既定値） |
| 3 | `eocs` | 股間の露出、および単独女性キャラクターの性器・陰毛の描写 | EOCS基準（18歳未満禁止相当） |

各レベルのプロンプト規則、派生スキルでの扱い、自主規制レーティングは [../novelai-imagegen/references/content_levels.md](../novelai-imagegen/references/content_levels.md) にまとめてある。ヒアリング前に読む。

## 手順

1. 現状を確認する。

   ```bash
   python3 ../novelai-imagegen/scripts/content_level.py show --project-root <project root>
   ```

   `source: "config"` なら記録済みのレベルを伝え、変更するかを確認する。`source: "default"` なら未設定（レベル2として動作中）であることを伝える。

2. `AskUserQuestion` で、次の質問を1回の呼び出しにまとめて聞く。どの質問にも推奨は付けない（作品の企画と配布先で決まるため、AIが推奨を決めない）。作品名は聞かない（既存作品を下敷きとしない新規プロジェクトもあるため）。

   - **レベル**: 選択肢は上表の3つ。各選択肢の説明に、許可する上限と自主規制レーティングを書く。
   - **愛液・白い液体**（`fluids`）: 許可する／許可しない。許可すると、その表現を含む画像は着衣・下着の画像も含めて自主規制レーティングが「18歳未満禁止」になることを説明に書く。
   - **露出した女性キャラクターへのスキンシップ**（`nude_contact`）: 許可する／許可しない。説明に「全裸（レベル1ではトップレス）の女性キャラクターへの抱擁・キス・愛撫等。股間への接触、双方が全裸の抱擁、性行為は許可しても含めない」と書く。

3. レベル3が選ばれた場合だけ、次の前提を**両方**満たすかを確認する。満たさない、または不明な場合はレベル3を記録せず、レベル2以下を選び直してもらう。EOCSの審査を実際に受けることは条件にしない。

   - 性器が描写された画像は、公開・配布の前にモザイク修正を施す（生成は無修正で行う）。
   - 公開・配布前の確認は、AIではなく人間（公開・配布の責任者）が行う。

4. 決定を記録する。

   ```bash
   python3 ../novelai-imagegen/scripts/content_level.py set --project-root <project root> \
     --level <1|2|3> --fluids <yes|no> --nude-contact <yes|no> [--confirm-eocs] [--notes "<補足>"]
   ```

   `--fluids` と `--nude-contact` は必須で、ヒアリングの回答をそのまま渡す。`--confirm-eocs` は手順3でユーザーが前提を両方確認した場合にだけ付ける。付けずにレベル3を指定するとスクリプトは記録を拒否する。

5. 既存のリクエストを確認する。レベルを下げた場合は特に、既存のリクエストJSONが新しいレベルを超えていないかを確認する。

   ```bash
   python3 ../novelai-imagegen/scripts/content_level.py check --project-root <project root> <project root>/user-run-scripts <project root>/output
   ```

   違反があれば一覧を示す。既存のリクエスト・画像は削除・書き換えしない。作り直す場合は、派生スキルのリテイク手順（新しいフォルダに書き出す）に従う。オプションを「許可しない」に変えた場合も同様に確認する。

6. 結果を報告する。記録したレベルとオプション、ファイルのパス、このプロジェクトで今後作れる画像の範囲（[../novelai-imagegen/references/content_levels.md](../novelai-imagegen/references/content_levels.md) の該当行）、自主規制レーティング、`check` の結果を伝える。

## 注意

- レベルとオプションの決定はユーザーが行う。AIが依頼内容から推測してレベルを上げたり、オプションを許可に変えたり、記録を書き換えたりしない。依頼がレベルを超える場合は、レベルの範囲に収めた案を示すか、このスキルでレベルを見直すかをユーザーに選んでもらう。
- `novelai-content-level.json` はプロジェクトの設定ファイルとして手で編集しない。変更はこのスキルで行う。
- この記録は制作上の基準であり、審査機関による正式なレーティングや法令上の適法性を示すものではない。
- ランナーのチェックはタグ単位の安全網で、結果を保証しない。生成後の目視確認（年齢印象、性器・陰毛の描写の有無など）は従来どおり必要である。
