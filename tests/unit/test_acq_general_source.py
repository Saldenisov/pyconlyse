"""Tie the new General procedure to hash-pinned original VI wires, offline."""
from pathlib import Path

from legacy.xp_acq_agent.elyse_agent.acquisition_procedures import (
    GENERAL_START_FRAMES, GENERAL_START_EPS, GENERAL_START_DPS,
    GENERAL_STOP_FRAMES, GENERAL_STOP_EPS, GENERAL_STOP_DPS,
    GENERAL_ONLY_STOP_FRAMES, GENERAL_ONLY_STOP_EPS, GENERAL_ONLY_STOP_DPS,
)
from tools.validate_acq_modulator_start_event_guards import checked_root, unique


def test_general_frames_and_wait_literals_match_pinned_original():
    root = checked_root(Path(__file__).resolve().parents[2] /
                        "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip")
    sequence = unique(root, "sequence", "34597")
    assert tuple(frame.get("uid") for frame in sequence.find("diagramList")) == tuple(
        row[1] for row in GENERAL_START_FRAMES)
    for uid, value in (("35689", 150), ("35019", 1000), ("29319", 1000), ("35576", 100)):
        term = unique(root, "term", uid)
        assert int(term.findtext("dco/ConstValue"), 16) == value
    for uid in ("34786", "35081", "32023", "35031", "29271", "35606"):
        assert unique(root, "prim", uid).findtext("primResID") == "1302"


def test_general_writes_follow_exact_local_bundle_and_literal_wires():
    root = checked_root(Path(__file__).resolve().parents[2] /
                        "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip")
    frames = list(unique(root, "sequence", "34597").find("diagramList"))
    # stage, bundle, selected field terminal, field index, constant terminal,
    # Boolean, write-local node, bank index, bundle-output/local-input wire.
    rows = (
        (0, "34714", "34732", 0, "34627", True, "34688", 15, ("34717", "34697")),
        (1, "34924", "34942", 0, "34877", False, "34906", 15, ("34931", "34915")),
        (3, "35065", "35071", 2, "35049", True, "35059", 15, ("35067", "35062")),
        (4, "25168", "25197", 2, "25728", False, "25108", 15, ("25179", "25125")),
        (6, "32007", "32013", 2, "32033", True, "31999", 15, ("32009", "32002")),
        (7, "33241", "33247", 2, "33267", False, "33233", 15, ("33243", "33236")),
        (8, "35487", "35493", 11, "35419", False, "35479", 44, ("35489", "35482")),
        (8, "35487", "35496", 8, "35429", True, "35479", 44, ("35489", "35482")),
        (8, "35487", "23461", 6, "32614", False, "35479", 44, ("35489", "35482")),
        (8, "35523", "35529", 2, "35459", False, "35515", 36, ("35525", "35518")),
    )
    actual_dio, actual_eps, actual_dps = {}, [], []
    for stage, mux_uid, face, index, constant_uid, value, writer_uid, bank, output_wire in rows:
        frame = frames[stage]
        signals = [{term.get("uid") for term in wire.findall("termList/*")}
                   for wire in frame.findall("signalList/*")]
        mux = unique(frame, "nMux", mux_uid)
        field = next(term for term in mux.find("termList") if term.get("uid") == face)
        # These two field-zero indices are omitted in the saved XML. This
        # uses the explicit source-specific index-zero projection already
        # recorded by the saved-body model, not a new global parser rule.
        assert int(field.findtext("dco/i", "0")) == index
        assert any({face, constant_uid} <= signal for signal in signals)
        raw = unique(frame, "term", constant_uid).findtext("dco/ConstValue")
        assert raw == ("01" if value else "0000")
        writer = unique(frame, "gRef", writer_uid)
        assert writer.findtext("termList/*/dco/paramIdx") == str(bank)
        assert any(set(output_wire) <= signal for signal in signals)
        if bank == 15:
            actual_dio[stage] = ((index, value),)
        elif bank == 44:
            actual_eps.append((index, value))
        elif bank == 36:
            actual_dps.append((index, value))
    assert actual_dio == {stage: assignments for stage, _, assignments, _ in GENERAL_START_FRAMES if assignments}
    assert tuple(actual_eps) == GENERAL_START_EPS
    assert tuple(actual_dps) == GENERAL_START_DPS


def test_general_stop_frames_pulses_status_and_delays_match_source():
    root = checked_root(Path(__file__).resolve().parents[2] /
                        "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip")
    frames = list(unique(root, "sequence", "26556").find("diagramList"))
    assert tuple(frame.get("uid") for frame in frames) == tuple(row[1] for row in GENERAL_STOP_FRAMES)
    rows = (
        (1, "55151", 8, "55203", False), (2, "31217", 8, "31262", True),
        (4, "33302", 17, "33347", False), (5, "35326", 17, "35353", True),
        (7, "36891", 6, "36918", False), (8, "23604", 6, "23636", True),
        (10, "25792", 4, "25850", False), (11, "29506", 4, "29587", True),
        (13, "30043", 1, "30124", False), (14, "32882", 1, "32909", True),
    )
    for stage, mux_uid, field_index, literal_uid, value in rows:
        frame = frames[stage]
        mux = unique(frame, "nMux", mux_uid)
        ports = mux.findall("termList/*")
        assert int(ports[2].findtext("dco/i", "0")) == field_index
        assert unique(frame, "term", literal_uid).findtext("dco/ConstValue") == ("01" if value else "0000")
        signals = [{term.get("uid") for term in wire.findall("termList/*")}
                   for wire in frame.findall("signalList/*")]
        assert any({literal_uid, ports[2].get("uid")} <= signal for signal in signals)
        assert all(node.findtext("termList/*/dco/paramIdx") == "15"
                   for node in frame.iter() if node.get("class") == "gRef")
        assert GENERAL_STOP_FRAMES[stage][2] == ((field_index, value),)
    waits = {0: 150, 1: 150, 3: 1000, 4: 150, 6: 1000, 7: 150,
             9: 1000, 10: 150, 12: 2000, 13: 150, 16: 100}
    assert {i: ms for i, _, _, ms in GENERAL_STOP_FRAMES if ms} == waits
    for stage, uid, value in ((0, "53942", 500), (3, "27289", 1000), (6, "35218", 1000),
                              (9, "23552", 1000), (12, "24938", 2000), (16, "35153", 100)):
        assert int(unique(frames[stage], "term", uid).findtext("dco/ConstValue"), 16) == value
    assert int(unique(root, "term", "37763").findtext("dco/ConstValue"), 16) == 150
    status = frames[15]
    signals = [{term.get("uid") for term in wire.findall("termList/*")}
               for wire in status.findall("signalList/*")]
    expected = []
    for constant_uid, value, fields in (
        ("28667", False, ((8, "28779"), (14, "30016"), (20, "30196"), (26, "30205"), (32, "30214"), (9, "44931"))),
        ("28677", True, ((11, "31248"), (17, "31647"), (23, "36547"), (29, "36851"), (35, "23531"))),
    ):
        for index, uid in fields:
            field = next(t for t in unique(status, "nMux", "28738").find("termList") if t.get("uid") == uid)
            assert int(field.findtext("dco/i")) == index
            assert any({constant_uid, uid} <= signal for signal in signals)
            expected.append((index, value))
    assert tuple(expected) == GENERAL_STOP_EPS
    assert GENERAL_STOP_DPS == ((3, False),)
    assert int(unique(status, "term", "35108").findtext("dco/i")) == 3
    assert any({"28699", "35108"} <= signal for signal in signals)
    flat = unique(frames[0], "flatSequence", "53825")
    cells = flat.find("sequenceList")
    assert unique(cells[0], "iUse", "53841").findtext("label/textRec/text") == '"1_Focales OFF.vi"'
    assert unique(cells[0], "iUse", "49738").findtext("label/textRec/text") == '"Clear Errors.vi"'
    assert unique(cells[1], "term", "53942") is not None
    assert unique(frames[16], "sharedVariableDynamicWrite", "37694") is not None


def test_general_only_stop_is_explicit_source_subset_not_full_event_6():
    assert GENERAL_ONLY_STOP_FRAMES == GENERAL_STOP_FRAMES[13:]
    assert tuple((i, uid) for i, uid, _assignments, _wait in GENERAL_ONLY_STOP_FRAMES) == (
        (13, "29980"), (14, "32864"), (15, "28661"), (16, "35146"))
    assert tuple(pair for _i, _uid, assignments, _ms in GENERAL_ONLY_STOP_FRAMES for pair in assignments) == (
        (1, False), (1, True))
    assert GENERAL_ONLY_STOP_EPS == ((8, False), (9, False), (11, True))
    assert all(pair in GENERAL_STOP_EPS for pair in GENERAL_ONLY_STOP_EPS)
    assert GENERAL_ONLY_STOP_DPS == GENERAL_STOP_DPS == ((3, False),)
