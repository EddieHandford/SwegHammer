"""
Parse cached BSData WH40k 2nd Edition .cat / .gst XML into a registry.

Every element with an `id` attribute is indexed so that `entryLink`/`infoLink`
`targetId` references can be resolved in O(1) across the whole game system.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .fetch import CACHE_DIR, cached_files

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
    """Load every cached .cat and .gst into a single registry."""
    if files is None:
        files = cached_files()
        if not files:
            files = sorted(CACHE_DIR.glob("*.cat")) + sorted(CACHE_DIR.glob("*.gst"))

    reg = Registry()
    for path in files:
        tree = ET.parse(path)
        _strip_ns(tree)
        reg.add_tree(path, tree)
    return reg


# ---------------------------------------------------------------------------
# Iterators
# ---------------------------------------------------------------------------

def iter_unit_entries(reg: Registry) -> Iterator[tuple[str, ET.Element]]:
    """
    Yield (codex_name, selectionEntry) for every "force-list" entry across all codices.

    The cleanest signal of what counts as a unit is the top-level <entryLinks> on each
    catalogue — these are the choices a player can directly add to their army roster.
    The `type="unit"` attribute on the underlying selectionEntry is inconsistent across
    BSData codices (some authors used `type="upgrade"` for everything), so we don't rely
    on it.
    """
    seen: set[str] = set()
    for cat_name, root in reg.catalogues.items():
        # Game-system file has no force-list entries — skip its top-level entryLinks
        # which would otherwise pick up shared rules / weapons.
        if root.tag != "catalogue":
            continue
        top_links = root.find("./entryLinks")
        if top_links is None:
            continue
        for el in top_links.findall("./entryLink"):
            target_id = el.get("targetId")
            if not target_id:
                continue
            target = reg.resolve(target_id)
            if target is None or target.tag != "selectionEntry":
                continue
            if target_id in seen:
                continue
            seen.add(target_id)
            # Use the codex where the entry is *defined* (not where it's imported via
            # cross-codex entryLink). E.g. Space Marine Captain is defined in the
            # Blood Angels codex and re-used by Ultramarines / Dark Angels.
            owning_codex = reg.source_file.get(target_id, cat_name)
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
