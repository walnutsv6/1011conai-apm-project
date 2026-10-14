# Tetris Specification Interview Question Bank

Use these prompts as a menu. Ask the most relevant questions first; do not dump every item at once.

## 1. Ruleset

- Guideline SRS 準拠を目指しますか、それとも TGM/ARS・Sega・Atari 風などのレガシーモードを作りますか。
- 複数モードを切り替え可能にしますか。する場合、最初に実装する優先モードはどれですか。
- 180 度回転は必要ですか。必要な場合、どのタイトル風のキックを採用しますか。

## 2. Field and Pieces

- Matrix は現行ガイドライン通り 10x40、可視 10x20 でよいですか。
- ピース色は SRS 公式色、Sega/TGM 伝統色、独自配色のどれにしますか。
- スポーン位置や上部バッファの扱いを厳密に再現しますか、それとも遊びやすさ優先で調整しますか。

## 3. Rotation

- SRS の 5 テスト wall kick を厳密に実装しますか。
- TGM/ARS の場合、Sega 底揃え、右から左への 3 段階 kick、中央列ルール、I kick なしを採用しますか。
- TGM3 風に I/T の floor kick や I wall kick を追加しますか。
- Sega 風の場合、wall kick なし・天井あり・flat-side up を採用しますか。
- Atari 風の場合、CCW のみ・右壁で左 1 マス kick のみを採用しますか。

## 4. Randomizer and Queue

- Guideline の 7-bag にしますか。Next キューは 6 個表示でよいですか。
- TGM 風の場合、4-history N-tries にしますか。初期履歴と tries 数は TGM1、TAP/Ti、独自のどれにしますか。
- Ti 風 35-bag まで再現しますか。

## 5. Controls and Handling

- キーボード操作は矢印、Space、Z/X、Shift/C、Esc/P の標準案でよいですか。
- ゲームパッド対応は初版に含めますか。
- DAS、ARR、ARE、Lock Delay は仕様書の値を採用しますか、それとも設定画面で調整可能にしますか。
- IRS/IHS や Sonic Drop は必要ですか。

## 6. Drops, Locking, and Gravity

- Hard Drop は即ロック、Soft Drop は非ロックでよいですか。
- Guideline の Move Reset と 15 回上限を使いますか。
- TGM 風の場合は Step Reset と Sonic Drop/Sonic Lock のどれを採用しますか。
- Gravity は Tetris Worlds 式、固定レベル表、20G を含む arcade-style のどれにしますか。

## 7. Modes

- 最初に実装するモードは Marathon、Sprint 40 Lines、Ultra 2 Minutes のどれですか。
- TGM 風なら Master/Grade 系、Atari 風なら B-type を入れますか。
- 無限モード、練習モード、設定画面、リプレイ、ランキングは必要ですか。

## 8. Scoring and Detection

- T-Spin は 3-Corner 方式で Mini 判定まで実装しますか。
- Back-to-Back、Combo、Perfect Clear、Soft/Hard Drop 点を入れますか。
- TGM 風の grade system や TGM1 スコア式は必要ですか。

## 9. UX and Presentation

- Ghost Piece はデフォルト ON でよいですか。オフ設定は必要ですか。
- Pause、3 カウントダウン、Game Over 表示、ライン消去演出、効果音を初版に含めますか。
- UI はプレイフィールド、Hold、Next、Score、Level、Lines、Timer を表示すれば足りますか。
- モバイルやタッチ操作に対応しますか。

## 10. Implementation Scope

- まず完成させる最小プレイ可能版の範囲はどこまでですか。
- 厳密再現より実装速度を優先してよい箇所はありますか。
- テストしたい仕様はどれですか。例: SRS kick、7-bag、lock delay、T-Spin 判定、game over 条件。

## Recommended First Round

Ask these first when starting from the provided project-root Markdown specs:

1. ルールセットは Guideline SRS 準拠を基本にしますか、それとも TGM/ARS・Sega・Atari 風も最初から入れますか。
2. 初版で作るゲームモードは Marathon、Sprint、Ultra、TGM Master 風、B-type のどれですか。
3. 実装対象はブラウザ/React/Canvas など、どの環境を想定していますか。
4. Hold、Ghost、Next 6 個、Hard Drop、Soft Drop はガイドライン通り入れてよいですか。
5. T-Spin、Back-to-Back、Combo、Perfect Clear まで初版スコアに含めますか。
6. DAS/ARR/Lock Delay などの操作感は仕様書の推奨値固定でよいですか、設定可能にしますか。
7. レトロ/TGM 要素を入れる場合、どの回転・ランダマイザ・ドロップ仕様を優先しますか。
