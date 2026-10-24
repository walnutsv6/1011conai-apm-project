# Game presets

Defaults to propose, not to impose. Machine-readable versions are in `presets/<id>.json`; copy the values into the spec explicitly. The user decides the stage count every time; facing and crotch are always asked.

All presets: sprites in `transparent` mode only (the game composites the background), `exposed_expression: "blush"` (so a `win` face stays readable from topless on), transitions use the `shy` expression, one-shots = icon (cropped), title (clothed, landscape, bg), reward (nude, user-run, private scene).

| | 野球拳 `yakyuken` | 脱衣麻雀 `mahjong` | クイズ `quiz` | 汎用 `generic` |
| --- | --- | --- | --- | --- |
| Rule | 1 loss = 1 main stage | character loses a hand = 1 main stage | player answers right = 1 main stage | any "advance" event |
| Main stages | 5 (5-7) | 5 (4-6) | 6 (4-10) | 5 (3-10) |
| Framing | portrait 832x1216, cowboy shot | square 1024x1024, cowboy shot (upper body alone hides the topless/nude difference) | portrait, cowboy shot | portrait, cowboy shot |
| Expressions | normal, win (happy smile), lose (pout), shy; optional draw (surprised) | normal (calm), riichi (serious), agari (smug), houjuu (shocked), shy | normal, asking (teasing), correct (pout), wrong (smug), shy | normal, win, lose, shy |
| Special poses | rock / scissors / paper, **all** stages, expression "determined, smile" | cut-ins riichi / tsumo / ron, landscape 1216x832, upper body close-up, **to underwear** | ask (card, pointing) / maru (circle) / batsu (x arms), **to underwear** | none |
| Events | player_win (advance, lose), player_lose (win), draw, call (random hand), idle, after_strip | player_agari (advance, houjuu), char_agari (+cut-in), char_riichi (+cut-in), idle, after_strip | question (+ask), player_correct (advance, +batsu), player_wrong (+maru), idle, after_strip | advance, char_win, idle, after_strip |
| Notes | covered nude: one hand covers, the other shows the janken hand; check arm conflicts in the pilot | bg mode only in a private room, never a parlour | maru / batsu tags are unstable; check in the pilot; no studio with an audience | |

## Default ladder template (all presets)

`dressed` (clothed) -> `outer_tr` (transition) -> `outeroff` (partial) -> `under_tr` (transition) -> `lingerie` (underwear) -> `bra_tr` (transition, facing asked) -> `topless` (facing asked) -> `panty_tr` (transition, topless class, facing asked) -> `nude` (crotch both, facing asked). The quiz template has one more main pair (`top_tr` / `topoff`, `skirt_tr`). Rebuild it from the confirmed worn items: one garment per main step, so a layered outfit usually needs one more main stage than the template.

## Cell counts (one character, transparent only, nude `both`)

Formula per method: main cells = sum over main stages of `len(expression_set) x variants`; transition cells = one per transition x variants; special cells = poses x scoped stages x variants (seed only); one-shots: title 1 + reward 2.

- yakyuken, 5 mains + 4 transitions, 4 expressions: sprites 24, transitions 4, janken 18, one-shots 3 -> seed **49** (user-run 24).
- mixed (sprites inpaint; transitions, janken, one-shots seed), meru pilot ladder 6 mains + 5 transitions, 4 expressions: sprites 24, transitions 5, janken 18, one-shots 2 -> **49** (user-run 16).
- Showing the user these numbers before building is required: user-run counts grow fastest with expressions x exposed stages and with special poses on all stages.
