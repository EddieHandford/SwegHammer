"""
Parse cached BSData WH40k 2nd Edition .cat / .gst XML into a registry.

Every element with an `id` attribute is indexed so that `entryLink`/`infoLink`
`targetId` references can be resolved in O(1) across the whole game system.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .fetch import CACHE_DIR, cached_files


def _open_cat(path: Path):
    """Open a .cat / .gst file, transparently decompressing if it's .gz.

    The cache moved to gzipped storage (10× smaller, ~24 MB → ~2 MB) but
    we keep reading legacy plain-XML cache files in case the user pulled
    from before the migration.
    """
    if path.suffix == ".gz":
        return gzip.open(path, "rb")
    return open(path, "rb")

# BattleScribe uses two schemas with different namespaces; both files are tiny
# variations on the same shape so we strip the namespace at load time.

def _strip_ns(tree: ET.ElementTree) -> None:
    """Remove XML namespaces in place — makes element-tree iteration much simpler."""
    for elem in tree.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]


@dataclass
class Registry:
    """Global index of every id-bearing element across all .cat + .gst files."""

    by_id: Dict[str, ET.Element] = field(default_factory=dict)
    catalogues: Dict[str, ET.Element] = field(default_factory=dict)  # codex name -> root
    source_file: Dict[str, str] = field(default_factory=dict)        # id -> filename

    def add_tree(self, path: Path, tree: ET.ElementTree) -> None:
        root = tree.getroot()
        cat_name = root.get("name") or path.stem
        self.catalogues[cat_name] = root
        for elem in root.iter():
            eid = elem.get("id")
            if eid and eid not in self.by_id:
                self.by_id[eid] = elem
                self.source_file[eid] = path.name

    def resolve(self, target_id: str) -> Optional[ET.Element]:
        return self.by_id.get(target_id)


def load_registry(files: Optional[List[Path]] = None) -> Registry:
    """Load every cached .cat / .gst (or their .gz variants) into a registry."""
    if files is None:
        files = cached_files()
        if not files:
            files = (
                sorted(CACHE_DIR.glob("*.cat.gz"))
                + sorted(CACHE_DIR.glob("*.gst.gz"))
                + sorted(CACHE_DIR.glob("*.cat"))
                + sorted(CACHE_DIR.glob("*.gst"))
            )

    reg = Registry()
    for path in files:
        with _open_cat(path) as fh:
            tree = ET.parse(fh)
        _strip_ns(tree)
        reg.add_tree(path, tree)
    return reg


# ---------------------------------------------------------------------------
# Hidden-in-matched-play filter
# ---------------------------------------------------------------------------

def _is_hidden_in_matched_play(entry: ET.Element) -> bool:
    """Return True if this selectionEntry is a Crucible Crusade-only unit that
    is unconditionally hidden in matched-play.

    Two gates must both pass:

    **Gate 1 — name suffix ``[Crucible]``.**  Every Crusade campaign character
    in BSData 10e carries this suffix.  The name gate is essential because the
    same modifier shape (Gate 2) appears on other entry types for unrelated
    reasons (``[Legends]`` units, Chaos Daemons shared-library entries,
    terrain pieces).  Without it those valid matched-play entries would be
    filtered out of the catalogue.

    **Gate 2 — matched-play hidden modifier.**  BSData marks Crucible-only
    units with a modifier that sets ``hidden=true`` whenever fewer than 1 of
    the entry appears on the roster::

        <modifier type="set" field="hidden" value="true">
          <conditions>
            <condition type="lessThan" field="selections" value="1" scope="roster"/>
          </conditions>
        </modifier>

    In a matched-play context no Crucible unit is ever on the roster, so this
    modifier always fires and the entry is always hidden.  BattleScribe's UI
    suppresses hidden entries from the army-builder drop-down; the mapper
    applies the same filter to prevent Crusade-only stat-blocks from entering
    the matched-play unit catalogue.

    Conservative stance on the modifier shape — only the ``scope="roster"`` /
    ``lessThan value="1"`` pattern is treated as the unconditional matched-play
    hide.  The other conditions on Crucible entries (``instanceOf``,
    ``notInstanceOf``, ``atLeast`` on specific entry IDs, scope ``"self"`` /
    ``"parent"`` / ``"force"``) are Crusade-mode toggles that show/hide the
    entry based on campaign state; we do not evaluate them.

    BSData evidence: every ``[Crucible]``-suffixed selectionEntry in v10.6.0
    carries exactly one modifier of this shape in addition to any Crusade-state
    modifiers.  Confirmed across 20 faction catalogues (62 entries total).

    Note: the ``[Crucible]`` name gate is essential.  Other entry types use the
    same ``lessThan scope=roster`` modifier for unrelated purposes (``[Legends]``
    units, Chaos Daemons shared-library entries, terrain and scenery pieces).
    Without the name gate those entries would also be filtered, removing valid
    matched-play units from the catalogue.
    """
    # Gate 1: name must contain "[Crucible]".  Crusade Crucible campaign units
    # are the only entries in BSData 10e that combine this suffix with the
    # matched-play hidden modifier as their primary visibility control.
    name = entry.get("name") or ""
    if "[Crucible]" not in name:
        return False

    # Gate 2: entry must carry the matched-play hidden modifier.
    for mod in entry.findall("./modifiers/modifier"):
        if mod.get("type") != "set":
            continue
        if mod.get("field") != "hidden":
            continue
        if (mod.get("value") or "").lower() != "true":
            continue
        for cond in mod.findall("./conditions/condition"):
            if (
                cond.get("type") == "lessThan"
                and cond.get("field") == "selections"
                and (cond.get("value") or "").strip() == "1"
                and (cond.get("scope") or "").lower() == "roster"
            ):
                return True
    return False


# ---------------------------------------------------------------------------
# Iterators
# ---------------------------------------------------------------------------

def iter_unit_entries(reg: Registry) -> Iterator[tuple[str, ET.Element]]:
    """
    Yield (codex_filename, selectionEntry) for every "force-list" entry across all codices.

    The cleanest signal of what counts as a unit is the top-level <entryLinks> on each
    catalogue — these are the choices a player can directly add to their army roster.
    The `type="unit"` attribute on the underlying selectionEntry is inconsistent across
    BSData codices (some authors used `type="upgrade"` for everything), so we don't rely
    on it.

    Each entry is credited to the most specific codex file that imports it. This
    matters for sub-faction codices that share a library: e.g. Drukhari units are
    *defined* in ``Aeldari - Aeldari Library.cat.gz`` but *imported* by
    ``Aeldari - Drukhari.cat.gz``. Crediting the importing file lets the
    downstream ``faction_of()`` lookup produce the right tag ("Drukhari" rather
    than "Aeldari"). For entries imported by multiple non-library catalogues
    (e.g. Harlequins are imported by both Craftworlds and Drukhari), we pick
    the first importer in catalogue iteration order — typically the broader
    Aeldari codex, matching the 10e AELDARI keyword.
    """
    # Map each top-level entry to the list of catalogue *filenames* importing it.
    from collections import OrderedDict
    imports: "OrderedDict[str, list[str]]" = OrderedDict()
    for cat_name, root in reg.catalogues.items():
        if root.tag != "catalogue":
            continue
        top_links = root.find("./entryLinks")
        if top_links is None:
            continue
        # Translate root cat_name back to its source filename via the root's id.
        root_id = root.get("id") or ""
        cat_file = reg.source_file.get(root_id, cat_name)
        for el in top_links.findall("./entryLink"):
            target_id = el.get("targetId")
            if not target_id:
                continue
            target = reg.resolve(target_id)
            if target is None or target.tag != "selectionEntry":
                continue
            imports.setdefault(target_id, []).append(cat_file)

    def _is_library(fname: str) -> bool:
        # Library catalogues hold shared datasheets and have no top-level
        # entryLinks of their own — they should never be picked as the
        # crediting codex when a more specific importer is available.
        low = fname.lower()
        return "library" in low or low.endswith(".gst.gz") or low.endswith(".gst")

    def _entry_faction_tag(entry: ET.Element) -> str:
        # The "Faction: X" categoryLink on a unit's selectionEntry pins it to
        # exactly one army-level faction. Used to disambiguate when multiple
        # codices import the same datasheet via cross-faction allies (e.g.
        # Genestealer Cults imports Astra Militarum's Cadians as allied
        # units in 10e — the Cadians stay tagged "Faction: Astra Militarum",
        # so we credit AM, not GSC).
        for cl in entry.findall(".//categoryLink"):
            name = (cl.get("name") or "").strip()
            if name.lower().startswith("faction:"):
                return name.split(":", 1)[1].strip()
        return ""

    # Late-bound import to avoid a parser → factions circular reference at
    # module load (factions is a leaf module, but keep this lazy as a guard).
    from code.factions import faction_of

    for target_id, files in imports.items():
        target = reg.resolve(target_id)
        if target is None or target.tag != "selectionEntry":
            continue
        faction_tag = _entry_faction_tag(target)
        # First choice: an importer whose CODEX_TO_FACTION mapping matches the
        # entry's own Faction keyword. This handles cross-faction allies.
        owning_codex = ""
        if faction_tag:
            for f in files:
                if faction_of(f) == faction_tag:
                    owning_codex = f
                    break
        # Second choice: any non-library importer.
        if not owning_codex:
            owning_codex = next((f for f in files if not _is_library(f)), "")
        # Last resort: the first importer (typically a library).
        if not owning_codex:
            owning_codex = files[0]
        # Skip entries that are unconditionally hidden in matched-play (e.g.
        # all [Crucible] Crusade characters).  The hidden modifier fires via
        # `lessThan field="selections" value="1" scope="roster"`, which is
        # always true in a matched-play context where no Crusade unit appears
        # on the roster.  Filtering here removes all 62 [Crucible] entries
        # in a single structural pass, replacing the per-unit `enabled: false`
        # override approach used before CRUCIBLE-HIDDEN-FILTER-V1.
        if _is_hidden_in_matched_play(target):
            continue
        yield owning_codex, target


def get_profile(reg: Registry, target_id: str) -> Optional[ET.Element]:
    """Resolve a target id to the underlying <profile> if any."""
    elem = reg.resolve(target_id)
    if elem is None:
        return None
    if elem.tag == "profile":
        return elem
    return None


def profile_characteristics(profile: ET.Element) -> Dict[str, str]:
    """Flatten characteristics into a {name: text} dict for a profile element."""
    out: Dict[str, str] = {}
    for c in profile.iter("characteristic"):
        name = c.get("name") or ""
        out[name] = (c.text or "").strip()
    return out


def selection_cost(entry: ET.Element) -> float:
    """Return the points cost listed directly on this entry (0 if none)."""
    for cost in entry.findall("./costs/cost"):
        if cost.get("typeId") == "points" or cost.get("name") == "pts":
            try:
                return float(cost.get("value") or 0)
            except ValueError:
                return 0.0
    return 0.0
