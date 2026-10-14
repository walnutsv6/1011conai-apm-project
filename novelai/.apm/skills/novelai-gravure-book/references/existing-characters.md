# Existing characters in a gravure book

Only **adult** existing characters, and only as **original characters inspired by them**, never a reproduction.

1. **Check the canon age** (from knowledge; use a web search when unsure). Record `canon_age` and the source in `character.source`.
   - Adult: continue.
   - Minor, or age unconfirmed: do not use the character tag in a book that contains underwear/swimsuit gravure, topless or nude cuts, and do not paper over it with an "adult version" note (the result may still look like a minor). Offer an original adult character instead. A book with no such content has no tag restriction, but this skill builds gravure books, so use the original.
   - Adult by canon but looks like a minor in the generated images: discard those images with their prompts; do not make the book.
2. **Real people are out of scope** (actors, idols, models, cosplayer photos). Virtual avatars (VTubers etc.) are treated as characters.
3. **Inspired, not reproduced.** In the spec:
   ```json
   "source": {"name": "<character name>", "tag": "<danbooru-style character tag>", "canon_age": 24, "canon_adult": true, "tag_weight": 0.8}
   ```
   `build_requests.py` aborts unless `canon_adult` is true (and `canon_age >= 18` when given). The tag goes first in `appearance` as `0.8::tag::`; use 0.6-0.9. Add adult body/face tags, and choose the outfits yourself (swimsuits, lingerie and so on are original designs). Reference images can be turned into appearance tags with `novelai-character-extract` (no character-name tags there).
4. Fixed hair/eye colour tags still belong in `appearance` with a bangs tag; add the opposite colours to `character.negative` if the tag drifts.
5. Do not claim a prompt is free of copyright or trademark issues. Publishing is the human's responsibility (check the franchise's secondary-creation guidelines and the distribution platform's rules).
