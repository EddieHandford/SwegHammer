"""
Fetch BSData WH40k 2nd Edition .cat files, pinned to a release tag.

The cache lives under data/bsdata/cache/ and is committed to the repo so the
simulator does not need internet access at runtime. Run

    python -m code.bsdata.fetch --tag v1.9.7

to refresh against a newer BSData release.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

REPO = "BSData/wh40k-10e"
DEFAULT_TAG = "v10.6.0"

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "bsdata" / "cache"
MANIFEST_PATH = CACHE_DIR / "_manifest.json"


def _list_cat_files(tag: str) -> List[str]:
    """List all .cat files in the repo at a given tag, via the GitHub contents API."""
    url = f"https://api.github.com/repos/{REPO}/contents/?ref={tag}"
    with urllib.request.urlopen(url) as resp:
        entries = json.loads(resp.read().decode("utf-8"))
    return sorted(
        e["name"] for e in entries
        if e["name"].endswith(".cat") or e["name"].endswith(".gst")
    )


def _raw_url(tag: str, filename: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{REPO}/{tag}/"
        f"{urllib.parse.quote(filename)}"
    )


def fetch(tag: str = DEFAULT_TAG, force: bool = False) -> List[Path]:
    """Download every .cat file at `tag` to the cache directory."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if MANIFEST_PATH.exists() and not force:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if manifest.get("tag") == tag:
            cached = [CACHE_DIR / f for f in manifest.get("files", [])]
            if all(p.exists() for p in cached):
                print(f"[bsdata] cache already at {tag} ({len(cached)} files)")
                return cached

    print(f"[bsdata] listing files at {tag}…")
    filenames = _list_cat_files(tag)
    print(f"[bsdata] {len(filenames)} .cat files found")

    fetched: List[Path] = []
    for name in filenames:
        dest = CACHE_DIR / name
        url = _raw_url(tag, name)
        print(f"[bsdata] fetching {name}")
        with urllib.request.urlopen(url) as resp:
            dest.write_bytes(resp.read())
        fetched.append(dest)

    MANIFEST_PATH.write_text(
        json.dumps({"tag": tag, "files": [p.name for p in fetched]}, indent=2),
        encoding="utf-8",
    )
    print(f"[bsdata] cached {len(fetched)} files at tag {tag}")
    return fetched


def cached_files() -> List[Path]:
    """Return the list of .cat files currently in the cache."""
    if not MANIFEST_PATH.exists():
        return []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [CACHE_DIR / f for f in manifest.get("files", []) if (CACHE_DIR / f).exists()]


def cached_tag() -> Optional[str]:
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("tag")


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default=DEFAULT_TAG, help=f"Release tag (default {DEFAULT_TAG})")
    p.add_argument("--force", action="store_true", help="Re-download even if cache is current")
    args = p.parse_args(argv)
    fetch(args.tag, force=args.force)


if __name__ == "__main__":
    main(sys.argv[1:])
