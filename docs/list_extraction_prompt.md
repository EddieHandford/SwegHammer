# Tournament list extraction prompt

A prompt template for converting a Goonhammer "Competitive Innovations in 10th"
article (or any similar source that publishes tournament lists as plain text)
into a structured JSON file that the SwegHammer validation pipeline can ingest.

## How to use

1. Open the article in your browser.
2. Open the browser console: Control+click anywhere on the page and choose
   "Inspect", then click the "Console" tab. On Mac you can also try F12.
3. Paste this into the console and hit Enter to expand every list at once:
   ```js
   document.querySelectorAll('.expandBody').forEach(el => el.style.display = 'block')
   ```
4. Click at the start of the first list, then Shift+click at the end of the
   last one, then Command+C to copy the selected text.
5. Open a fresh chat with Claude (or any capable language model).
6. Paste the prompt block below, then paste the article text underneath it,
   then send.
7. Save the returned JSON into `data/tournament_lists/<event-slug>.json`
   (create the directory if it doesn't exist yet).

The schema matches the validation criteria written up in the
2026-05-24 conversation: faction, detachment, full roster with model counts and
wargear, enhancements, warlord, event metadata, result, and per-round opponent
faction where available.

---

## The prompt (copy from here)

You are extracting Warhammer 40,000 10th edition tournament lists from a
published article into structured JSON. Read the article text I paste after
this prompt and return a single JSON object that conforms exactly to the
schema below. Return only the JSON — no commentary, no markdown fence.

Schema:

```json
{
  "event": {
    "name": "string — full event name as written in the article",
    "date": "YYYY-MM-DD — start date if a range is given",
    "size_players": "integer or null if not stated",
    "rounds": "integer or null if not stated",
    "format": "string — e.g. 'matched play 2000 points', or null",
    "source_url": "string — the article URL if visible, otherwise null"
  },
  "lists": [
    {
      "player": "string or null",
      "placement": "integer or null — final ranking",
      "record": {
        "wins": "integer",
        "losses": "integer",
        "draws": "integer"
      },
      "faction": "string — top-level faction as printed (e.g. 'Necrons', 'Adepta Sororitas')",
      "detachment": "string — detachment name (e.g. 'Awakened Dynasty', 'Hallowed Martyrs')",
      "warlord": "string or null — named character designated as warlord",
      "total_points": "integer",
      "enhancements": [
        {
          "name": "string",
          "attached_to": "string — unit or character that carries it",
          "points": "integer or null"
        }
      ],
      "units": [
        {
          "name": "string — unit name as printed",
          "model_count": "integer",
          "points": "integer",
          "wargear": ["list of wargear or weapon option strings as printed; empty list if default loadout"]
        }
      ],
      "per_round_opponents": [
        {
          "round": "integer",
          "opponent_faction": "string",
          "opponent_detachment": "string or null",
          "result": "win | loss | draw"
        }
      ]
    }
  ]
}
```

Rules:
- If a field is not stated in the article, use `null` (or an empty array for
  list-typed fields). Do not invent values.
- Preserve faction and detachment names exactly as printed, including
  capitalisation. Do not normalise to internal keys.
- If a list shows enhancements inline with the character (e.g.
  "Overlord with Veil of Darkness, 95 pts"), break the enhancement out into
  the `enhancements` array and leave the base unit cost in `units`.
- Per-round opponents are usually not in the article; leave that array empty
  unless the article gives a round-by-round breakdown.
- If the article contains lists from multiple events, return them as separate
  objects inside a top-level `events` array instead — same schema, just
  wrapped: `{"events": [ {"event": {...}, "lists": [...]}, ... ]}`.
- Total points should be the sum printed in the article. If the list has a
  partial roster (e.g. only "highlights" shown), set `total_points` to null
  and add `"partial": true` at the list level.

Once you have produced the JSON, save it to the file
`data/tournament_lists/<slug>.json` where `<slug>` is derived from the event
name and date — lowercase, hyphens instead of spaces, e.g.
`goonhammer-competitive-innovations-2026-05-20.json`. If you cannot determine
the date, use the article publication date. If you are running in a context
where you cannot write files, print the intended filename as the first line
before the JSON so the user knows where to save it.

Article text follows below.
