"""Offline application composition. No hardware registry commissioning is inferred."""

from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
from pathlib import Path

from ..domain.magnet_registry import candidate_registry
from ..domain.magnet_readback import magnet_display_snapshot
from ..domain.supervision_orchestrator import EVENT_CASES, TIMED_LOOP_FRAMES
from .shadow import parse_preview, preview_currents
from .store import ShadowJournal


EXPECTED_MAIN_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"


class OfflineSupervision:
    def __init__(self, journal: ShadowJournal, *, supervision_root: Path):
        self.registry = candidate_registry()
        self.journal = journal
        self.supervision_root = supervision_root

    def snapshot(self, *, now: datetime) -> dict:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Explicit timezone-aware snapshot time required")
        main = self.supervision_root / "extracted/PILOTAGE_ELYSE_SUP/SUPERVISION_VIs/0_SUP_ELYSE.vi"
        observed = hashlib.sha256(main.read_bytes()).hexdigest().upper() if main.is_file() else None
        catalog = json.loads((self.supervision_root / "python_reconstruction/src/supervision_reconstruction/catalog/catalog.json").read_text(encoding="utf-8"))
        records = catalog["records"]
        application_records = [record for record in records if record["record_scope"] == "application_scope"]
        states = dict(Counter(record["conversion_state"] for record in application_records))
        journal, history = self.journal.snapshot()
        return {"schema_version": 1, "mode": "OFFLINE_SHADOW", "execution_allowed": False,
                "generated_at": now.astimezone(timezone.utc).isoformat(),
                "registry": magnet_display_snapshot(self.registry),
                "journal": journal,
                "history": history,
                "coverage": {"top_level_events": len(EVENT_CASES), "timed_frames": len(TIMED_LOOP_FRAMES),
                    "catalog_vi_count": len(records), "application_vi_count": len(application_records),
                    "application_evidence_states": states,
                    "verified_replacement_count": sum(record["conversion_state"] == "verified" for record in records),
                    "events": [{"index": event.index, "label": event.selector_label,
                                "boundary": event.boundary} for event in EVENT_CASES],
                    "complete_vi_replacement": False,
                    "blockers": ["Unverified physical routes, operating limits, interlocks, and authority",
                                 "Remaining event/frame semantics and hardware contracts",
                                 "Password-protected Error Code Database.vi",
                                 "0_SUP_ELYSE.vi working-copy source drift" if observed != EXPECTED_MAIN_SHA256
                                 else "No independently verified executable VI replacements"]},
                "source_integrity": {"expected_main_sha256": EXPECTED_MAIN_SHA256,
                    "observed_main_sha256": observed, "matches": observed == EXPECTED_MAIN_SHA256,
                    "source_modified_by_service": False}}

    def preview(self, body: object, *, now: datetime) -> dict:
        intent = parse_preview(self.registry, body)
        # Runtime availability is deliberately empty. There are no live adapters.
        result = preview_currents(self.registry, intent)
        record, replayed = self.journal.append(intent.idempotency_key, intent.canonical_request(), result, now=now)
        return {"kind": "SHADOW_PREVIEW_RECORD", "execution_allowed": False,
                "replayed": replayed, "record": record}
