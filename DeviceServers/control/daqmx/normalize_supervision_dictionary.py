import json
from pathlib import Path

from DeviceServers.control.daqmx.supervision_channel_mapper import (
    make_match_key,
    normalize_human_text,
)

BASE = Path(__file__).resolve().parent
LIVE_DICTIONARY = BASE / "live_psp_raw_dictionary.after_clear.json"
NORMALIZED_REPORT_JSON = BASE / "live_psp_coverage_check.normalized.json"
NORMALIZED_REPORT_MD = BASE / "live_psp_coverage_check.normalized.md"

IGNORED_TOKENS = ("reserve", "libre")


def should_ignore_uncovered(raw_name: str, normalized_raw_name: str, match_key: str) -> str | None:
    if not raw_name.strip() or raw_name.strip() == "-":
        return "blank_label"
    if raw_name.strip().isdigit():
        return "numeric_slot"
    if match_key.startswith("acq libre") or match_key == "acq libre":
        return "unused_acq_slot"
    if any(token in match_key.split() for token in IGNORED_TOKENS):
        return "reserve_or_libre"
    return None


def load_mapping_entries() -> list[dict]:
    mapping_entries = []
    for path in sorted(BASE.glob("*mapping.proposed.json")):
        payload = json.loads(path.read_text())
        for entry in payload.get("entries", []):
            raw_name = entry.get("raw_name")
            if not raw_name:
                continue
            mapping_entries.append(
                {
                    "source_file": path.name,
                    "raw_name": raw_name,
                    "normalized_raw_name": normalize_human_text(raw_name),
                    "match_key": make_match_key(raw_name),
                    "canonical_name": entry.get("canonical_name"),
                }
            )
    return mapping_entries


def main() -> None:
    live_payload = json.loads(LIVE_DICTIONARY.read_text())
    channels = live_payload["channels"]
    mapping_entries = load_mapping_entries()

    exact_raw_names = {entry["raw_name"] for entry in mapping_entries}
    normalized_index = {}
    for entry in mapping_entries:
        normalized_index.setdefault(entry["match_key"], []).append(entry)

    exact_covered = []
    normalized_rescued = []
    actionable_uncovered = []
    ignored_uncovered = []

    for channel in channels:
        raw_name = channel.get("raw_name", "")
        normalized_raw_name = normalize_human_text(raw_name)
        match_key = make_match_key(raw_name)
        channel["normalized_raw_name"] = normalized_raw_name
        channel["match_key"] = match_key

        if raw_name in exact_raw_names:
            exact_covered.append(raw_name)
            continue

        matched_entries = normalized_index.get(match_key, [])
        if matched_entries:
            normalized_rescued.append(
                {
                    "raw_name": raw_name,
                    "normalized_raw_name": normalized_raw_name,
                    "match_key": match_key,
                    "mapped_to": [entry["raw_name"] for entry in matched_entries],
                    "canonical_names": [entry["canonical_name"] for entry in matched_entries if entry["canonical_name"]],
                }
            )
            continue

        ignore_reason = should_ignore_uncovered(raw_name, normalized_raw_name, match_key)
        target_list = ignored_uncovered if ignore_reason else actionable_uncovered
        record = {
            "raw_name": raw_name,
            "normalized_raw_name": normalized_raw_name,
            "match_key": match_key,
        }
        if ignore_reason:
            record["ignore_reason"] = ignore_reason
        target_list.append(record)

    live_count = len(channels)
    effective_covered = len(exact_covered) + len(normalized_rescued)
    normalized_report = {
        "stats": {
            "live_count": live_count,
            "exact_covered_count": len(exact_covered),
            "normalized_rescued_count": len(normalized_rescued),
            "effective_covered_count": effective_covered,
            "actionable_uncovered_count": len(actionable_uncovered),
            "ignored_uncovered_count": len(ignored_uncovered),
            "effective_coverage_pct": round((effective_covered / live_count) * 100, 2) if live_count else 0.0,
        },
        "sample_normalized_rescues": normalized_rescued[:80],
        "sample_actionable_uncovered": actionable_uncovered[:120],
        "sample_ignored_uncovered": ignored_uncovered[:120],
    }

    live_payload["meta"]["normalization_applied"] = True
    live_payload["meta"]["normalization_note"] = (
        "normalized_raw_name and match_key are generated from raw_name using mojibake repair, "
        "accent folding and whitespace normalization."
    )
    live_payload["meta"]["last_manual_update"] = "normalized coverage recomputed"
    live_payload["meta"]["normalized_effective_coverage_pct"] = normalized_report["stats"]["effective_coverage_pct"]

    LIVE_DICTIONARY.write_text(json.dumps(live_payload, ensure_ascii=False, indent=2) + "\n")
    NORMALIZED_REPORT_JSON.write_text(json.dumps(normalized_report, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Normalized Live Coverage Check",
        "",
        f"Live channels now: `{normalized_report['stats']['live_count']}`",
        f"Exact raw-name matches: `{normalized_report['stats']['exact_covered_count']}`",
        f"Recovered by normalization: `{normalized_report['stats']['normalized_rescued_count']}`",
        f"Effective covered total: `{normalized_report['stats']['effective_covered_count']}`",
        f"Actionable uncovered: `{normalized_report['stats']['actionable_uncovered_count']}`",
        f"Ignored uncovered (`Libre` / `Réserve` / numeric placeholders): `{normalized_report['stats']['ignored_uncovered_count']}`",
        f"Effective coverage: `{normalized_report['stats']['effective_coverage_pct']}%`",
        "",
        "## Sample Normalized Rescues",
        "",
    ]
    for item in normalized_rescued[:40]:
        mapped_to = ", ".join(f"`{value}`" for value in item["mapped_to"])
        lines.append(f"- `{item['raw_name']}` -> {mapped_to}")
    lines.extend(["", "## Sample Actionable Uncovered", ""])
    for item in actionable_uncovered[:80]:
        lines.append(f"- `{item['raw_name']}`")
    NORMALIZED_REPORT_MD.write_text("\n".join(lines) + "\n")

    print(json.dumps(normalized_report["stats"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
