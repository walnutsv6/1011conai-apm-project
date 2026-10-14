# Book structure (inspiration, not defaults)

## Cover
Not exposed (`clothed` / `partial` / `swimsuit` / `underwear`). The one image the agent generates, so choose the strongest, most representative look; `cowboy` or `upper`, looking at viewer, in a private scene.

## Chapter ladder examples (pick, reorder, drop, add)

| chapter | scene (private) | class | cuts |
| --- | --- | --- | --- |
| Daily life | hotel suite window, bedroom in morning light | clothed | 3-4: full, sitting, closeup, walking |
| Resort | private pool / villa terrace with nobody around / bathroom | swimsuit | 3-4: stretch, sitting at the edge, lying, wet hair |
| Lingerie | bedroom, dressing room | underwear | 3-4: standing, sitting on the bed, back view |
| Undressing (`strip`) | bedroom | partial -> underwear -> topless | 4-8 ordered steps; each cut gives its own `outfit` |
| Topless | bedroom | topless | 2-4 |
| Nude | bedroom, bath | nude (`crotch`: both) | 3-6 incl. lying and back view |

A book may contain only some of these. After a non-exposed cover, every body chapter may be exposed.

## Cut design
- Vary pose and `shot` between cuts of a chapter; keep outfit and scene fixed (`cuts`) so differences are attributable.
- `strip` chapters: no step removes two garments; separate the gesture, the half-removed state and the removed state when the user wants fine steps.
- Landscape cuts (`lying`) take a whole page in the viewer; portrait cuts pair up two per spread.
- Ask `facing` per exposed cut. Nude cuts: `covered` (hand/pillow/sheet as a small prop) and `open` (no genital detail, no pubic hair). A knee-hug nude is only an on-request variation.
- Poses that need hands (covering) conflict with arm-raised poses; flag it when proposing.

## Photobook flavour tags (add to `defaults.style` or a pose)
`soft focus`, `bokeh`, `depth of field`, `film grain`, `warm lighting`, `window light`, `backlighting`, `shiny skin`, `wet skin`, `from below`, `from above`, `dutch angle`, `looking back`, `hand in hair`, `lying on side`. Keep them small and few per cut so the character stays consistent.
