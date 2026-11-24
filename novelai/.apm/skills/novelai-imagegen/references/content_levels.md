# 表現レベルの詳細

記録ファイル: `<agent dir>/novelai-content-level.json`（スキルの配置先フォルダ。Claude Code は `.claude/`、Codex は `.agents/`）。`novelai-content-level` スキルのヒアリングで、`content_level.py set` により作成する。
判定ロジック: `novelai-imagegen/scripts/content_level.py`（ランナーが generate / edit / tool / estimate の前に必ず呼ぶ）。

記録がないプロジェクトはレベル2（現行・CERO基準）、オプションはすべて許可として動作する。

登場キャラクターが全員18歳以上で、見た目の印象も成人であることは、すべてのレベル・オプションに共通する前提であり、設定で変わらない。

## オプション（レベルにかかわらず確認）

| キー | 内容 | 許可しない場合 |
| --- | --- | --- |
| `fluids` | 愛液、白い液体が身体や服にかかっている表現 | 愛液・白い液体のタグを使わない |
| `nude_contact` | 全裸（レベル1ではトップレス）の女性キャラクターへの抱擁・キス・愛撫・頭をなでる等のスキンシップ | 露出した女性キャラクターが登場する複数人の画像では、キャラクター同士を接触させない（並んで立つ等、接触のない構図にする） |

オプションはガイドラインの許容範囲を絞るためのもので、許可しても次は含めない: 股間への接触（本人が隠す場合を除く）、双方が全裸または双方が下半身を露出した状態での抱擁（下記のレベル3のオプションを除く）、許容範囲を超える愛撫、性行為。

## オプション（レベル3のみ）

レベル3で `nude_contact` を許可した場合にだけ確認する。記録がない場合・レベル1〜2では常に `false`。

| キー | 内容 | 前提 | 許可しない場合 |
| --- | --- | --- | --- |
| `nude_embrace` | 男性の主観視点（POV）での双方全裸の抱擁。女性キャラクター1人のみを描き、男性は腕・手まで（胴体・性器は描かない）。挿入は示唆も含めて描かない | `nude_contact` | 双方全裸の抱擁を含めない |
| `embrace_ejaculation` | 上記の抱擁の中での無意識的な自然射精の示唆と、抱擁後に股間・内腿（下着等の上を含む）へ精液が付着した状態。射精の瞬間・性器、性行為による射精、性器の内側から溢れる表現は含めない | `nude_embrace`、`fluids` | 接触のある画像に精液を含めない |

条件の詳細はガイドラインの「主観視点での全裸の抱擁・射精の示唆（オプション）」を正とする。

## 作れる画像の範囲

| 画像の種類 | レベル1 | レベル2 | レベル3 |
| --- | --- | --- | --- |
| 着衣・水着・下着 | 可 | 可 | 可 |
| トップレス（乳房・乳首の露出、下着は着用） | 可 | 可 | 可 |
| パンティーの脱衣途中・脱衣後、ボトムレス、ヌード | **不可** | 可（性器・陰毛は描かない） | 可 |
| 股間を隠さない構図での陰毛・性器の描写（単独女性） | 不可 | 不可 | **可**（公開前にモザイク修正） |
| 複数キャラクター画像での性器・陰毛 | 不可 | 不可 | 不可 |
| 男性単体の陰茎の露出（強い修正が前提） | 不可（股間の露出に当たる） | 複数キャラクターガイドラインに従う | 複数キャラクターガイドラインに従う |
| 愛液・白い液体 | `fluids` が true の場合のみ | 同左 | 同左 |
| 露出した女性キャラクターへの抱擁・スキンシップ（股間は除く） | `nude_contact` が true の場合のみ（トップレスまで） | `nude_contact` が true の場合のみ | 同左 |
| 主観視点での双方全裸の抱擁（女性1人のみ描写） | 不可 | 不可 | `nude_embrace` が true の場合のみ |
| 抱擁中の射精の示唆・抱擁後の股間・内腿への精液の付着 | 不可 | 不可 | `embrace_ejaculation` が true の場合のみ |
| 性行為（挿入の示唆を含む）、自慰を想起させる動作、強要、排泄、膣内射精を想起させる表現 | 不可 | 不可 | 不可 |

## プロンプト規則（ランナーが検査するもの）

| 規則 | レベル1 | レベル2 | レベル3（単独女性） | レベル3（複数人） |
| --- | --- | --- | --- | --- |
| positive の `nude`, `completely nude`, `naked`, `bottomless`, `no panties`, `pulling down panties`, `panty pull`, `* panties around thighs` 等 | 拒否 | 可 | 可 | 可 |
| positive の `pubic hair`, `pussy`, `uncensored` 等 | 拒否 | 拒否 | 可 | 拒否 |
| 露出表現があるときの negative の `uncensored` | 必須 | 必須 | 不要 | 必須 |
| 股間の露出があるときの negative の `pussy` と `pubic hair` | — | 必須 | 不要 | 必須 |
| `pussy juice`, `cum`, `white liquid` 等 | `fluids` 次第 | `fluids` 次第 | `fluids` 次第 | `fluids` 次第 |
| 複数人（`1boy`, `2girls` 等）または `pov`＋接触タグ、＋露出タグ＋接触タグ（`hug`, `kiss`, `embrace`, `breast grab`, `caress` 等） | `nude_contact` 次第 | `nude_contact` 次第 | `nude_contact` 次第 | `nude_contact` 次第 |
| 複数人または `pov`＋接触タグ、＋露出タグ＋精液タグ（`cum`, `cum on *`, `semen`, `bukkake`, `facial`） | 拒否 | 拒否 | `embrace_ejaculation` が true で、`pov`（`1boy` 等なし）の場合のみ可（付着部位は検査しない） | 拒否 |
| 女性キャラクター（`1girl`, `hetero` 等）または `pov`＋接触タグ、＋露出タグ＋`penis`, `testicles` 等 | 拒否 | 拒否 | 拒否 | 拒否 |
| 性行為・`spread pussy`・`fingering`・`masturbation`・`cumdrip`・`cum in pussy`・`thigh sex`・`sumata`・`grinding`・`ejaculation` 等 | 拒否 | 拒否 | 拒否 | 拒否 |
| 露出表現と同時の `loli`, `child`, `* school student` 等 | 拒否 | 拒否 | 拒否（`schoolgirl` も拒否） | 拒否（同左） |

`pov` に接触タグが付いた画像は、相手が描かれていなくても複数人として扱う（性器・陰毛の描写は不可、negative の `uncensored` と性器・陰毛の除外が必須）。ただし、レベル3で `nude_embrace` が true のプロジェクトでは、`1boy` 等のない `pov` の画像を単独女性と同じ扱いにし、性器・陰毛の描写を許可する。男性側が全裸であること、精液の付着部位はタグで判定・検査しないため、`nude_embrace`・`embrace_ejaculation` の範囲は生成後の目視確認で担保する（`cumdrip` 等の禁止タグは拒否する）。

男性キャラクター（`1boy`, `male focus` 等）を含むプロンプトでは、複数キャラクターガイドラインのとおり陰茎の描写に `uncensored` を使えるため、positive の `uncensored` と negative の `uncensored` 必須は検査しない。女性の性器・陰毛のタグは引き続き検査する。

検査はタグ単位の安全網である。タグを書き換えて回避しない。生成結果の保証にはならないため、生成後の目視確認は従来どおり行う。

## レベル3で変わるプロンプトの組み方（単独女性）

- 股間を隠さない構図（構図2）で性器・陰毛を描写する画像は、negative から `uncensored` と性器・陰毛の除外指定を外し、positive に `uncensored` を入れる。陰毛を描く場合は `pubic hair` も入れる。
- 陰毛だけを描き性器を描かない画像は、positive に `pubic hair`、negative に性器の除外指定（`pussy` 等）を残す。
- `mosaic censoring` 等の修正指定はプロンプトに入れない。修正は生成後に行う。
- negative に `spread pussy`、`loli`、`child`、`multiple girls` を入れておくと、意図しない描写・人数の混入を抑えやすい（このプロジェクトの既存リクエストの構成）。
- 生成後に性器が描写されている画像は、モザイク修正が必要な画像として記録する。

## 派生スキルでの扱い

派生スキル（`novelai-variations`、`novelai-strip-sequence`、`novelai-gravure-book`、`novelai-gameassets` パッケージの `novelai-strip-game`）は、`novelai-imagegen` の SKILL.md を先に読む構成になっている。各スキルの「genital detail / pubic hair を描かない」「`exposed_negative` に `uncensored` と性器・陰毛の除外を入れる」という記述は、レベル2の規則である。プロジェクトのレベルに応じて次のように読み替える。

| 派生スキルの要素 | レベル1 | レベル2 | レベル3 |
| --- | --- | --- | --- |
| strip-sequence のステージ / gravure-book のカット区分 | `topless` までを提案する。`bottomless`・`nude`・パンティーを下ろすステージは提案せず、依頼されたらレベルの範囲外であることを伝える | 従来どおり | 従来どおり |
| `crotch: open` の内容 | —（使わない） | 股間は見えるが性器・陰毛は描かない | 性器・陰毛の描写を含めてよい。陰毛のみ／性器も描写するかをユーザーに確認する |
| `defaults.exposed_negative` | `uncensored` を含める | `uncensored` と性器・陰毛の除外を含める | `crotch: open` で描写する場合は `uncensored` と描写するものの除外を外し、ステージ／カットのタグに `uncensored`、`pubic hair` を入れる。`covered` は従来どおり |
| 愛液・白い液体のタグ | `fluids` が true の場合のみ | 同左 | 同左 |
| 複数人のステージ／カット・衣装候補での接触 | 露出した女性がいる場合は `nude_contact` が true の場合のみ | 同左 | 同左 |
| 主観視点の双方全裸の抱擁・射精の示唆のステージ／カット | 提案しない | 提案しない | `nude_embrace`・`embrace_ejaculation` が true の場合のみ提案できる。着衣・下着を含む画像セットの一部として組む |
| variations の衣装候補 | 下着・トップレスまで | 従来どおり | 従来どおり |

どのレベルでも、トップレス・ボトムレス・ヌードのリクエストは生成せず、リクエストJSONとユーザー実行スクリプトの作成までとする。スクリプトを渡す前に `python3 <skills dir>/novelai-imagegen/scripts/content_level.py check --project-root <project root> <リクエストのフォルダ>` を実行し、違反がないことを確認する。

## 自主規制レーティングの目安

ガイドラインの「自主規制レーティング基準」に従う。レベルごとの上限は次のとおり。

- レベル1: 乳房の描写を含むため「15歳未満禁止」。愛液・白い液体を含む画像は「18歳未満禁止」。
- レベル2: ヌード・股間の露出、または愛液・白い液体を含む場合は「18歳未満禁止」。
- レベル3: 性器・陰毛の描写を含むため「18歳未満禁止」（EOCSのレーティングを前提とする）。`nude_embrace`・`embrace_ejaculation` による画像も「18歳未満禁止」。

## 参考

- レベル1の参考例: スーパーリアル麻雀LOVE2〜7！ for PC（15歳以上推奨。下着・トップレスを含むが、パンティーの脱衣は含まない）。
- レベル2: CERO倫理規定を参考にした現行ガイドライン。
- レベル3: EOCS（一般社団法人コンピュータソフトウェア倫理機構）の「18歳未満禁止」の基準。実際に審査を受けることは設定の条件にしない。
