"""
Faction grouping and canonical colour palette for the WH40k 10e catalogue.

Each codex (`.cat` file) is mapped to a top-level faction string and a
recognisable canonical colour. Used by the loader to tag UnitProfile.faction
and by app.py to colour-code armies in the dashboard.

Colour choices use box-art canonical schemes:
  Ultramarines blue for vanilla Astartes, Necron green for Necrons,
  Orks goff-green, Tyranid Leviathan purple, Death Guard plague-green, etc.
"""

from __future__ import annotations

from typing import Dict


# ---------------------------------------------------------------------------
# Codex → faction lookup
# ---------------------------------------------------------------------------

CODEX_TO_FACTION: Dict[str, str] = {
    # ---- Imperium ----
    "Imperium - Space Marines.cat":                "Adeptus Astartes",
    "Imperium - Blood Angels.cat":                 "Blood Angels",
    "Imperium - Dark Angels.cat":                  "Dark Angels",
    "Imperium - Black Templars.cat":               "Black Templars",
    "Imperium - Space Wolves.cat":                 "Space Wolves",
    "Imperium - Ultramarines.cat":                 "Ultramarines",
    "Imperium - Imperial Fists.cat":               "Imperial Fists",
    "Imperium - Iron Hands.cat":                   "Iron Hands",
    "Imperium - Raven Guard.cat":                  "Raven Guard",
    "Imperium - Salamanders.cat":                  "Salamanders",
    "Imperium - White Scars.cat":                  "White Scars",
    "Imperium - Deathwatch.cat":                   "Deathwatch",
    "Imperium - Grey Knights.cat":                 "Grey Knights",
    "Imperium - Adepta Sororitas.cat":             "Adepta Sororitas",
    "Imperium - Adeptus Custodes.cat":             "Adeptus Custodes",
    "Imperium - Adeptus Mechanicus.cat":           "Adeptus Mechanicus",
    "Imperium - Imperial Knights.cat":             "Imperial Knights",
    "Imperium - Imperial Knights - Library.cat":   "Imperial Knights",
    "Imperium - Adeptus Titanicus.cat":            "Adeptus Titanicus",
    "Imperium - Astra Militarum.cat":              "Astra Militarum",
    "Imperium - Astra Militarum - Library.cat":    "Astra Militarum",
    "Imperium - Agents of the Imperium.cat":       "Agents of the Imperium",

    # ---- Chaos ----
    "Chaos - Chaos Space Marines.cat":             "Chaos Space Marines",
    "Chaos - Death Guard.cat":                     "Death Guard",
    "Chaos - Thousand Sons.cat":                   "Thousand Sons",
    "Chaos - World Eaters.cat":                    "World Eaters",
    # Emperor's Children — Slaanesh-aligned Chaos Marines. Standalone codex
    # WIP on BSData master; not yet in the latest tagged release (v10.6.0).
    # Will auto-pick-up when the BSData refresh lands.
    "Chaos - Emperor's Children.cat":              "Emperor's Children",
    "Chaos - Chaos Daemons.cat":                   "Chaos Daemons",
    "Chaos - Chaos Daemons Library.cat":           "Chaos Daemons",
    "Chaos - Chaos Knights.cat":                   "Chaos Knights",
    "Chaos - Chaos Knights Library.cat":           "Chaos Knights",
    "Chaos - Titanicus Traitoris.cat":             "Chaos Titans",

    # ---- Xenos ----
    "Aeldari - Aeldari Library.cat":               "Aeldari",
    # Note: the Craftworlds sub-codex maps to the umbrella "Aeldari" faction
    # rather than a "Aeldari (Craftworlds)" sub-name. The Battle Focus army
    # rule applies to all AELDARI keyword units (Asuryani + their characters),
    # and the simulator + eval harness gate on faction == "Aeldari" — keeping
    # the bucket flat ensures Wraithguard, Guardians, Aspect Warriors, etc.
    # land in the same army-builder pool as Drukhari-adjacent allies. Sub-
    # faction discrimination is handled via the ASURYANI unit keyword.
    "Aeldari - Craftworlds.cat":                   "Aeldari",
    "Aeldari - Drukhari.cat":                      "Drukhari",
    "Aeldari - Ynnari.cat":                        "Ynnari",
    "Necrons.cat":                                 "Necrons",
    "Orks.cat":                                    "Orks",
    "Tyranids.cat":                                "Tyranids",
    "T'au Empire.cat":                             "T'au Empire",
    "Genestealer Cults.cat":                       "Genestealer Cults",
    "Leagues of Votann.cat":                       "Leagues of Votann",

    # ---- Libraries / shared ----
    "Library - Astartes Heresy Legends.cat":       "Heresy Legends",
    "Library - Titans.cat":                        "Titan Legions",
    "Unaligned Forces.cat":                        "Unaligned",
}


# ---------------------------------------------------------------------------
# Canonical faction colours (box-art reference)
# ---------------------------------------------------------------------------

FACTION_COLOURS: Dict[str, str] = {
    # Imperium
    "Adeptus Astartes":         "#1F4B8B",   # Ultramarines blue (the default Astartes)
    "Ultramarines":             "#1F4B8B",
    "Blood Angels":             "#A20F0F",   # Sanguine red
    "Dark Angels":              "#1B5E20",   # Caliban green
    "Black Templars":           "#202020",
    "Space Wolves":             "#7B96B3",   # Fenrisian grey-blue
    "Imperial Fists":           "#E2B62E",   # Yellow
    "Iron Hands":               "#3A3F44",
    "Raven Guard":              "#1A1A1A",
    "Salamanders":              "#1C6E3A",   # Salamander green
    "White Scars":              "#E0E0E0",   # White with red-trim accent
    "Deathwatch":               "#2F2F2F",   # Black silver-trim
    "Grey Knights":             "#58708E",
    "Adepta Sororitas":         "#5B0F11",   # Order Ebon Chalice red-black
    "Adeptus Custodes":         "#C6A664",   # Gold
    "Adeptus Mechanicus":       "#7A1010",   # Mars red
    "Imperial Knights":         "#94181E",   # House Krast heraldic red
    "Astra Militarum":          "#5C6E48",   # Cadian olive/khaki
    "Agents of the Imperium":   "#4A4A4A",

    # Chaos
    "Chaos Space Marines":      "#1A1A1A",   # Black Legion
    "Death Guard":              "#9CA876",   # Nurgle pale plague-green
    "Thousand Sons":            "#1E5BA8",   # Tzeentch blue + gold trim
    "World Eaters":             "#B71C1C",   # Khorne blood red
    "Emperor's Children":       "#E91E63",   # Slaaneshi pink-magenta
    "Chaos Daemons":            "#4B0082",   # Slaaneshi/Tzeentch purple
    "Chaos Knights":            "#5A0E18",

    # Xenos
    "Aeldari":                  "#6A1B9A",   # Wraithbone purple (Ulthwé-ish)
    "Drukhari":                 "#3B0E2E",   # Dark Kin near-black-purple
    "Ynnari":                   "#1F2B5A",   # Reborn navy
    "Chaos Titans":             "#3A2A4F",   # Traitor titan dark plum
    "Adeptus Titanicus":        "#0F1E3E",   # Loyalist titan deep blue
    "Necrons":                  "#2E7D32",   # Necrodermis-green / arc lightning
    "Orks":                     "#4A6B27",   # Goff green
    "Tyranids":                 "#6B1B5F",   # Leviathan / Behemoth purple
    "T'au Empire":              "#B8722F",   # Tan / sept ochre
    "Genestealer Cults":        "#B85533",   # Cult orange
    "Leagues of Votann":        "#8B6914",   # Brass / bronze

    # Libraries / fallback
    "Heresy Legends":           "#6D5A36",
    "Titan Legions":            "#6D5A36",
    "Unaligned":                "#555555",
    "":                         "#888888",   # unknown / no faction tag
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

# Top-level Adeptus Astartes umbrella — every chapter codex tagged as a
# Space Marines successor for the purposes of army rules like Oath of
# Moment and Combat Doctrines. The Adeptus Astartes army rules from the
# Space Marines codex apply to every chapter; supplements layer on top
# (e.g. Blood Angels keep Oath + Doctrines and add Sons of Sanguinius).
# Grey Knights are excluded: they have their own dedicated army rule
# ("Teleport Strike" / "Brotherhood Psyker") and do not use Oath /
# Doctrines on Wahapedia.
MARINE_FACTIONS = frozenset({
    "Adeptus Astartes",
    "Ultramarines",
    "Blood Angels",
    "Dark Angels",
    "Black Templars",
    "Space Wolves",
    "Imperial Fists",
    "Iron Hands",
    "Raven Guard",
    "Salamanders",
    "White Scars",
    "Deathwatch",
})


def is_marine_faction(faction: str) -> bool:
    """Return True iff `faction` is any flavour of Adeptus Astartes chapter.

    Used to gate army-rule effects (Oath of Moment, Combat Doctrines) that
    are shared across every Marine chapter codex. The check is a pure
    membership test against `MARINE_FACTIONS` — no substring matching, no
    case normalisation. Grey Knights are deliberately excluded (they have
    their own army rule).
    """
    return faction in MARINE_FACTIONS


def faction_of(codex: str) -> str:
    """Return the faction string for a codex filename, or '' if unrecognised.

    Tolerates the gzipped cache suffix introduced in #100 — the canonical
    lookup keys end in ``.cat`` so we strip a trailing ``.gz`` before the
    match. Plain ``.cat`` filenames continue to hit directly.
    """
    if codex.endswith(".gz"):
        codex = codex[:-3]
    return CODEX_TO_FACTION.get(codex, "")


def colour_for(faction: str) -> str:
    """Return the canonical hex colour for a faction string. Falls back to grey."""
    return FACTION_COLOURS.get(faction, FACTION_COLOURS[""])
