from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional


MOJIBAKE_MARKERS = ("Ã", "Â", "â", "�")


def mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


def maybe_fix_mojibake(text: str) -> str:
    candidates = [text]
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        for encoding in ("latin1", "cp1252"):
            try:
                decoded = text.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            candidates.append(decoded)

    unique: List[str] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)

    return min(unique, key=lambda value: (mojibake_score(value), -len(value)))


def normalize_human_text(text: str) -> str:
    fixed = maybe_fix_mojibake(str(text or "")).strip()
    fixed = fixed.replace("’", "'").replace("`", "'")
    fixed = fixed.replace("œ", "oe").replace("Œ", "OE")
    fixed = fixed.replace("N°", "N ").replace("Nº", "N ").replace("№", "N ")
    fixed = re.sub(r"\s+", " ", fixed)
    return fixed


def make_match_key(text: str) -> str:
    normalized = normalize_human_text(text)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


class SupervisionChannelMapper:
    """Resolve raw LabVIEW channel names to canonical internal names."""

    def __init__(self, mapping_dir: Optional[Path] = None):
        if mapping_dir is None:
            mapping_dir = Path(__file__).resolve().parent
        self.mapping_dir = Path(mapping_dir)
        self.exact_map: Dict[str, str] = {}
        self.match_key_map: Dict[str, str] = {}
        self.ambiguous_match_keys: Dict[str, List[str]] = {}
        self.loaded_files: List[str] = []
        self.loaded_entries = 0
        self.reload()

    def reload(self) -> None:
        exact_map: Dict[str, str] = {}
        match_candidates: Dict[str, set[str]] = {}
        loaded_files: List[str] = []
        loaded_entries = 0

        for path in sorted(self.mapping_dir.glob("*mapping.proposed.json")):
            try:
                payload = json.loads(path.read_text())
            except Exception:
                continue

            entries = payload.get("entries", [])
            if not isinstance(entries, list):
                continue

            loaded_files.append(path.name)
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                raw_name = str(entry.get("raw_name") or "").strip()
                canonical_name = str(entry.get("canonical_name") or "").strip()
                if not raw_name or not canonical_name:
                    continue

                exact_map.setdefault(raw_name, canonical_name)
                match_candidates.setdefault(make_match_key(raw_name), set()).add(canonical_name)
                loaded_entries += 1

        match_key_map: Dict[str, str] = {}
        ambiguous: Dict[str, List[str]] = {}
        for match_key, canonical_names in match_candidates.items():
            if len(canonical_names) == 1:
                match_key_map[match_key] = next(iter(canonical_names))
            else:
                ambiguous[match_key] = sorted(canonical_names)

        self.exact_map = exact_map
        self.match_key_map = match_key_map
        self.ambiguous_match_keys = ambiguous
        self.loaded_files = loaded_files
        self.loaded_entries = loaded_entries

    def resolve(self, raw_name: str) -> Dict[str, object]:
        raw_name = str(raw_name or "").strip()
        normalized_raw_name = normalize_human_text(raw_name)
        match_key = make_match_key(raw_name)

        if not raw_name:
            return {
                "raw_name": raw_name,
                "normalized_raw_name": normalized_raw_name,
                "match_key": match_key,
                "canonical_name": raw_name,
                "match_type": "empty",
                "mapped": False,
            }

        if raw_name.startswith("elyse/"):
            return {
                "raw_name": raw_name,
                "normalized_raw_name": normalized_raw_name,
                "match_key": match_key,
                "canonical_name": raw_name,
                "match_type": "already_canonical",
                "mapped": True,
            }

        canonical_name = self.exact_map.get(raw_name)
        if canonical_name:
            return {
                "raw_name": raw_name,
                "normalized_raw_name": normalized_raw_name,
                "match_key": match_key,
                "canonical_name": canonical_name,
                "match_type": "exact",
                "mapped": True,
            }

        canonical_name = self.match_key_map.get(match_key)
        if canonical_name:
            return {
                "raw_name": raw_name,
                "normalized_raw_name": normalized_raw_name,
                "match_key": match_key,
                "canonical_name": canonical_name,
                "match_type": "normalized",
                "mapped": True,
            }

        return {
            "raw_name": raw_name,
            "normalized_raw_name": normalized_raw_name,
            "match_key": match_key,
            "canonical_name": raw_name,
            "match_type": "unmapped",
            "mapped": False,
        }

    def stats(self) -> Dict[str, object]:
        return {
            "loaded_files": list(self.loaded_files),
            "loaded_file_count": len(self.loaded_files),
            "loaded_entries": int(self.loaded_entries),
            "exact_map_count": len(self.exact_map),
            "match_key_map_count": len(self.match_key_map),
            "ambiguous_match_key_count": len(self.ambiguous_match_keys),
        }
