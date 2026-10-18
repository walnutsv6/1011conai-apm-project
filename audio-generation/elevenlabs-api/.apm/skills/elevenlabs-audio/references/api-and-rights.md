# API references and usage constraints (checked 2026-10-18)
- Music POST `/v1/music`: https://elevenlabs.io/docs/api-reference/music/compose
- SFX POST `/v1/sound-generation`: https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert
- Music licensing: https://elevenlabs.io/music-terms
- Music defaults explicitly set to `music_v2_5`, instrumental true; duration 3–600 seconds. SFX model `eleven_text_to_sound_v2`, duration 0.5–30 seconds, optional loop/prompt_influence.
- Sound effect response includes `character-cost` header, observed equal to dashboard debit. Music may not return that header; track dashboard separately.
- Observed account rates: Music 10 s / 125 credits; SFX 2 s / 20, 5 s / 50, 1.5 s / 15. These are user measurements not contract terms.
- Music Terms media rights depend on plan and game revenue/studio categorization. Do not promise commercial rights or interpret pay-as-you-go as unrestricted; confirm plan rights before publishing.
- SFX and Music have different terms. Confirm separately when commercial shipping.
- No retries after transport/timeout errors since charges could occur without receiving a file.
