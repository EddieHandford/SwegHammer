# N2 Reanimation Protocols rate verification — DIAG (no fix shipped)

Branch: claude/sim-calibration-4 @ d24de44
Date: 2026-05-20

## Conclusion

**No change made.** The brief's premise — "real codex says d3 models per RP
unit per Command phase" — is incorrect. The verbatim 10e Reanimation
Protocols army rule restores **one** destroyed bodyguard model per unit
per Command phase, and the simulator already implements this correctly.
The "d3" wording refers to a separate Necron Stratagem (Protocol of the
Undying Legions), not the army rule.

## Wahapedia accessibility

WebFetch against `https://wahapedia.ru/wh40k10ed/factions/necrons/`
returned ECONNREFUSED (DNS dead at edit time, consistent with prior
fetches in the repo — see RUBRICAE_PHALANX.all_is_dust citation note
about the same problem). Per CLAUDE.md §6 the fallback is BSData
(`data/bsdata/cache/`), but BSData carries datasheets and points, not
army-rule prose. The next-best source is therefore the verbatim
quoted_text already in the repo's rule citations, which were captured
from Wahapedia in previous sessions when the site was reachable.

## Verbatim rule (sourced from in-repo citations, captured pre-DNS-outage)

Three independent places in the repo carry the same verbatim Wahapedia
quote for the Reanimation Protocols army rule:

1. `code/simulator.py` lines 3412-3418 (docstring on `_apply_reanimation`):

   > "If your Warlord is a NECRONS model, then at the end of each of
   > your Command phases, each unit from your army with this ability
   > that has had one or more destroyed bodyguard models can use this
   > ability. If it does, restore **one** destroyed bodyguard model in
   > that unit to your army (with its full wounds remaining)."

2. `data/rule_citations.d/detachments.json` entry
   `AWAKENED_DYNASTY.reanimate_per_round`, `quoted_text` field — same
   verbatim text.

3. `data/rule_citations.d/keywords_and_mechanics.json` entry
   `simulator.reanimation_protocols`, `quoted_text` field — same
   verbatim text (line 241, omitted from grep output but confirmed by
   context).

The rate is unambiguously "**one** destroyed bodyguard model" per unit
per Command phase. There is no D3 in the army-rule wording.

## Where "D3" actually comes from

Grep for `D3 wounds` surfaced one match in citations:
`data/rule_citations.d/necrons.json:17` — the Stratagem **Protocol of
the Undying Legions** (Awakened Dynasty Strategic Ploy):

> "EFFECT: Your unit activates its Reanimation Protocols and reanimates
> **D3 wounds** (or D3+1 wounds if a NECRONS CHARACTER is leading your
> unit)."

This is a 1 CP Stratagem fired in the opponent's Shooting/Fight phase,
not the once-per-Command-phase army rule. The simulator implements it
separately as `transient_undying_legions_pulse` / `_apply_undying_legions_pulse`
(see `code/simulator.py:_try_protocol_undying_legions` lines 1776-1786
and `_apply_undying_legions_pulse` lines 3092-3100), which uses the
median D3 = 2 (or 3 if led) approximation. That is the correct place
for the D3 number; conflating it with the army rule was the brief's
error.

## Simulator implementation review

`AWAKENED_DYNASTY.reanimate_per_round = 1` (code/detachments.py:296)
is read in two places:

1. `code/simulator.py:3442` — gating check (skip armies with
   `reanimate_per_round <= 0`).
2. `code/simulator.py:3490` — `to_revive = min(destroyed, deaths_this_round, 1)`.

The hard-coded `1` in `to_revive` matches the verbatim "one destroyed
bodyguard model" wording exactly. The `reanimate_per_round` field
itself is currently treated as a boolean gate (any value > 0 turns
RP on) rather than as a cap, so setting it to 2 would NOT actually
change behaviour without also editing the `min(..., 1)` cap on line
3490. The brief's proposed change (1 -> 2 in detachments.py) would
have been a no-op without a second edit.

Comment block at simulator.py:3485-3489 explicitly justifies the
1-per-profile cap by citing the verbatim Wahapedia text and noting
that the previous "median D3 = 2" behaviour was reverted because it
over-fired (iter-1 cluster A diagnostic). Iter29-NE1 (referenced in
the docstring at simulator.py:3498) reverted a separate misread about
revive-at-1-wound vs revive-at-full-wounds, but kept the 1-per-profile
rate.

## Final state

- Current rule (simulator): 1 model revived per RP unit per round, gated
  on at-least-one-loss-this-round. Matches verbatim 10e.
- Real codex rule: 1 model per RP unit per Command phase. Verbatim
  quoted in 3 separate places in the repo.
- Fix applied: none. The current implementation is rule-correct.
- MAE delta: not measured (no change to evaluate).

## Recommendation for the parent agent

The N2 task as briefed is based on a misread of the rule. If the
parent agent wants to *experiment* with bumping RP to 2 revives/round
for MAE reasons, that would be a deliberate over-approximation (the
opposite of iter-1's correction) and must be documented as such — not
as a rule fix. The brief's framing ("real rule IS d3 per unit") does
not survive contact with the verbatim citation. Per the brief's own
hard constraint ("if real rule IS 1, do not change it for MAE
reasons"), N2 stops here.
