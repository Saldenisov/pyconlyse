"""Qualified Supervision C5 command pulses; injected callbacks, Python 3.4.

These are command intentions, not measured positions. In particular the saved
Faraday3 feedback labels conflict with Acquisition's channel map. No Faraday
HORS write was qualified; fields28/30 below are exclusion checks ONLY.

Original PSP writes are replaced by same-owner full-bank NI callbacks. Source
native errors/dialogs, PSP scheduling and physical pulse widths are not claimed
equivalent. Python failure policy releases the selected bit after any possibly
applied assertion; an unsuccessful release retains ownership and blocks new
energizing/motion paths and cleanup. Independent reviewed protective stops
remain available, without writing/retrying C5. Release never replays motion.
"""
import copy


SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
SOURCE_BDHB_SHA256 = "F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7"
SOURCE_PSP_URI = "ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96"
BEAMLINE_OPERATIONS = ("faraday_1.en_pulse", "faraday_3.en_pulse",
                       "laser_mirror.en_pulse", "laser_mirror.hors_pulse")
SOURCE_PATHS = {
    "faraday_1.en_pulse": dict(event=9, diagram_uid="53772", case_uid="53995",
        sequence_uid="54575", frame_uids=("54581", "54873", "54970"),
        field=23, opposite_exclusion_field=28, nominal_wait_seconds=.5,
        assertion_literal_uid="54623", assertion_mux_uid="54659", assertion_writer_uid="54669",
        wait_uid="54943", wait_literal_uid="54903", release_literal_uid="55116",
        release_mux_uid="55231", release_writer_uid="55252"),
    "faraday_3.en_pulse": dict(event=11, diagram_uid="56943", case_uid="57006",
        sequence_uid="62574", frame_uids=("62578", "62813", "62872"),
        field=25, opposite_exclusion_field=30, nominal_wait_seconds=.5,
        assertion_literal_uid="62607", assertion_mux_uid="62637", assertion_writer_uid="62647",
        wait_uid="62840", wait_literal_uid="62820", release_literal_uid="62918",
        release_mux_uid="62945", release_writer_uid="62956"),
    "laser_mirror.en_pulse": dict(event=8, diagram_uid="53656", case_uid="76431",
        selector=0, sequence_uid="77973", frame_uids=("77981", "81258", "85997"),
        field=22, opposite_exclusion_field=26, nominal_wait_seconds=1.,
        assertion_literal_uid="79753", assertion_mux_uid="53898", assertion_writer_uid="53908",
        wait_uid="81888", wait_literal_uid="83199", release_literal_uid="86078",
        release_mux_uid="86018", release_writer_uid="86028"),
    "laser_mirror.hors_pulse": dict(event=8, diagram_uid="53656", case_uid="76431",
        selector=1, sequence_uid="56518", frame_uids=("56523", "56742", "56785"),
        field=26, opposite_exclusion_field=22, nominal_wait_seconds=1.,
        assertion_literal_uid="56550", assertion_mux_uid="56574", assertion_writer_uid="56584",
        wait_uid="56768", wait_literal_uid="56748", release_literal_uid="56817",
        release_mux_uid="56839", release_writer_uid="56849"),
}
ACQUISITION_WRITER_PATH = dict(timeout_reader_uid="25449", timeout_uri_uid="25268",
    local_bank=13, local_writer_uid="25484", runtime_frame_uid="7386",
    runtime_local_reader_uid="2378", cluster_to_array_uid="8127",
    dio96_call_uid="686", helper="1_ACQ_RW_DIO96.vi", helper_c5_write_uid="742")


class BeamlineExecutionError(RuntimeError):
    def __init__(self, report):
        self.report = report
        RuntimeError.__init__(self, report["operation"] + ": " + report["status"])


class BeamlineExecutionCancelled(BeamlineExecutionError):
    pass


def validate_c5(values):
    if (type(values) is not tuple or len(values) != 40
            or any(type(value) is not bool for value in values)):
        raise ValueError("Complete immutable forty-Boolean C5 command image required")
    return values


def execute_beamline_pulse(operation, read_bank, commit_field, wait_seconds,
                           cancelled, observer=None, new_value=True):
    """Preserve True -> nominal wait -> False, with mandatory release policy.

    commit_field(index, exactbool) owns full-bank same-owner serialization,
    uncertainty latch and successful command memory. observer(frame, uid) is
    RAM-only; no safe input-sampling checkpoint is offered during this pulse.
    Cancellation can shorten the wait but can never suppress release. An
    assertion failure skips dwell and attempts release without replaying True.
    """
    if type(operation) is not str or operation not in BEAMLINE_OPERATIONS:
        raise ValueError("Unqualified beamline pulse operation")
    if type(new_value) is not bool:
        raise ValueError("Exact Boolean beamline NewVal required")
    if any(not callable(callback) for callback in (read_bank, commit_field, wait_seconds, cancelled)):
        raise TypeError("Beamline callbacks must be callable")
    if observer is not None and not callable(observer):
        raise TypeError("Beamline observer must be callable or None")
    source = copy.deepcopy(SOURCE_PATHS[operation])
    report = dict(operation=operation, status="NOOP" if not new_value else "EXECUTING",
        completed=False, source_vi_sha256=SOURCE_VI_SHA256, source_bdhb_sha256=SOURCE_BDHB_SHA256,
        source_path=source, source_psp_uri=SOURCE_PSP_URI,
        acquisition_writer_path=dict(ACQUISITION_WRITER_PATH),
        source_transport_replaced_by="SAME_OWNER_FULL_C5_BANK_CALLBACK",
        psp_delivery_acknowledged=False, hardware_acknowledged=False,
        position_feedback_qualified=False, physical_position="UNKNOWN",
        source_native_timing_equivalence=False, source_error_dialog_equivalence=False,
        software_command_only=True, cancelled=False, assertion_attempted=False,
        assertion_callback_completed=False, release_attempted=False,
        release_callback_completed=False, pending_release=None, failures=[],
        opposite_exclusion_policy="additional_python_fail_closed_not_source_permit")
    if not new_value:
        return report

    class CancelledSignal(Exception):
        pass

    def check_cancel():
        value = cancelled()
        if type(value) is not bool:
            raise ValueError("Beamline cancellation result must be Boolean")
        if value:
            report["cancelled"] = True
            raise CancelledSignal()

    def frame(index):
        report["frame"] = index
        report["source_uid"] = source["frame_uids"][index]
        if observer is not None:
            observer(index, report["source_uid"])

    stage = "admission"
    try:
        check_cancel()
        before = validate_c5(read_bank())
        if before[source["field"]] or before[source["opposite_exclusion_field"]]:
            raise RuntimeError("Selected and opposite beamline command fields must be released")
        frame(0)
        check_cancel()
        stage = "assert"
        report["assertion_attempted"] = True
        report["pending_release"] = dict(field=source["field"], value=False)
        commit_field(source["field"], True)
        report["assertion_callback_completed"] = True
        stage = "wait"
        frame(1)
        check_cancel()
        wait_seconds(source["nominal_wait_seconds"])
        check_cancel()
    except CancelledSignal:
        report["status"] = "CANCELLED"
    except Exception as error:
        report["status"] = "FAILED"
        report["failures"].append(dict(stage=stage, error_type=type(error).__name__, message=str(error)))
    finally:
        if report["assertion_attempted"]:
            try:
                frame(2)
            except Exception as error:
                report["status"] = "FAILED"
                report["failures"].append(dict(stage="release_observer", error_type=type(error).__name__, message=str(error)))
            report["release_attempted"] = True
            # No cancellation or observer callback can prevent this release.
            try:
                commit_field(source["field"], False)
                report["release_callback_completed"] = True
                report["pending_release"] = None
            except Exception as error:
                report["status"] = "FAILED"
                report["failures"].append(dict(stage="release", error_type=type(error).__name__, message=str(error)))
    if report["status"] == "EXECUTING":
        try:
            check_cancel()
        except CancelledSignal:
            report["status"] = "CANCELLED"
        except Exception as error:
            report["status"] = "FAILED"
            report["failures"].append(dict(stage="complete", error_type=type(error).__name__, message=str(error)))
        else:
            report["status"] = "SOFTWARE_PULSE_COMPLETED_NOT_POSITION_ACK"
            report["completed"] = True
    if report["status"] == "CANCELLED":
        raise BeamlineExecutionCancelled(report)
    if not report["completed"]:
        raise BeamlineExecutionError(report)
    return report
