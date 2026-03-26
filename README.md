# 🇯🇵 → 🇺🇸 Pokémon TCG Card Matcher

A simple client-side tool to find the English equivalent of a Japanese Pokémon TCG card.

**Live:** [dgallitelli.github.io/pokemon-tcg-jp-en-matcher](https://dgallitelli.github.io/pokemon-tcg-jp-en-matcher/)

## How It Works

1. Enter a Japanese set ID (e.g. `PMCG1`, `sv8`) and card number
2. The tool fetches the Japanese card from the [TCGdex API](https://tcgdex.dev/)
3. Uses the Pokédex ID to find the English Pokémon name
4. Searches English cards matching name + HP
5. Scores candidates by comparing illustrator, attacks, retreat cost, and stage
6. Displays both cards side by side with a confidence score

## Matching Strategy

Japanese and English Pokémon TCG sets use different IDs and numbering — there's no 1:1 mapping. This tool bridges the gap by fingerprinting cards on their game attributes:

| Signal | Weight | Why |
|--------|--------|-----|
| Illustrator | High | Same artist = same print run |
| HP | Medium | Narrows to the right card variant |
| Attack count & damage | Medium | Structural match |
| Attack costs | Low | Additional confirmation |
| Retreat cost | Low | Tiebreaker |
| Stage | Low | Tiebreaker |

## Limitations

- **Pokémon cards only** — Trainer and Energy cards don't have a Pokédex ID, so cross-language name lookup isn't possible yet
- **Japan-exclusive cards** — Some Japanese cards were never printed in English
- **Set merging** — English sets often combine multiple Japanese sets, so the "best match" may come from an unexpected English set
- **TCGdex coverage** — Japanese card data in TCGdex is still growing; some sets may be incomplete

## Tech

Zero dependencies. Single HTML file. All API calls run in the browser against TCGdex's free public API. No backend, no keys, no build step.

## License

MIT
