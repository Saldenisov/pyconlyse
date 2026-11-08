"""Complete SUP APP22 source-defined logic in a finite isolated domain.

Source: the separately audited SUP original, not ACQ APP16 or a generated
draft. Native connector invocation, concurrency and unrestricted numeric
semantics remain unqualified. No literal/index/callee value is supplied.
"""
from collections import namedtuple
import math

SOURCE_ID = 'APP-22'
SOURCE_VERSION = 'EBDEFE7988AF770EAEDE9741C740AF16386987A1C31D65F06E150641F411ED04'
ORIGINAL_VI_SHA256 = 'BB17412EA188A1EBC0218673E5DD694775A8A1F25034CCC5AA8740F236641C0C'
MODEL_CATEGORY = 'COMPLETE_SOURCE_DEFINED_FINITE_ISOLATED_CONTROL_STATE_PROJECTION'

# Each row follows original upper/lower operand faces, not saved termList order.
# Subtract(node, Consigne, Lecture, out), Abs(node, in, out), Greater(node, Abs, threshold, out).
ARITHMETIC_UIDS = (
    ('3320', '3332', '3329', '3326', '3408', '3448', '3445', '1400', '1716', '1411', '1408'),
    ('3460', '3472', '3469', '3466', '3478', '3483', '3480', '68', '1820', '1817', '1810'),
    ('3545', '3557', '3554', '3551', '3563', '3568', '3565', '1346', '1841', '1838', '1357'),
    ('3571', '3579', '3576', '3573', '3582', '3587', '3584', '1847', '1855', '1852', '1849'),
    ('3592', '3645', '3642', '3639', '3651', '3656', '3653', '1362', '1863', '1860', '1372'),
    ('3659', '3667', '3664', '3661', '3670', '3675', '3672', '1869', '1877', '1874', '1871'),
    ('3678', '3686', '3683', '3680', '3689', '3694', '3691', '1375', '1885', '1882', '1385'),
    ('3697', '3705', '3702', '3699', '3708', '3713', '3710', '1891', '1899', '1896', '1893'),
    ('3728', '3809', '3806', '3803', '3815', '3820', '3817', '1449', '1939', '1936', '1732'),
)
Primitive = namedtuple('Primitive',
    'diagram_uid node_uid operation input_face_uids output_face_uid arguments value')
StateAccess = namedtuple('StateAccess',
    'diagram_uid local_uid face_uid action bank_index target_fPDCO_uid state')
App22Result = namedtuple('App22Result',
    'output_control_state arithmetic_trace local_state_trace qualification_limits')


class App22DomainError(ValueError):
    """Value lies outside this source-defined model's declared domain."""


def qualification_limits():
    return dict(model_category=MODEL_CATEGORY,
        complete_source_defined_model_within_domain=True,
        complete_original_native_runtime_equivalence=False,
        unrestricted_original_numeric_semantics=False,
        native_rounding_coercion_ABI_equivalence=False,
        native_connector_invocation=False, native_panel_concurrency=False,
        model_trace_order_is_native_schedule=False, source_or_native_VI_execution=False,
        supplied_business_returns=False, supplied_literal_or_index_hypotheses=False,
        initial_OUT_default_required=False)


def _finite(value, role):
    if type(value) is not float or not math.isfinite(value):
        raise App22DomainError(role + ': exact finite float required')
    return value


def _control_carrier(value):
    if type(value) not in (list, tuple) or len(value) != 9:
        raise App22DomainError('IN: exact9-row list or tuple required')
    validated = []
    for group, row in enumerate(value):
        if type(row) not in (list, tuple) or len(row) != 11:
            raise App22DomainError('IN row: exact11-field list or tuple required')
        for field, item in enumerate(row):
            if field in (5, 6):
                _finite(item, 'IN[{0}][{1}]'.format(group, field))
            elif type(item) is not bool:
                raise App22DomainError('IN field: exact bool required')
        validated.append(tuple(row))
    return tuple(validated)


def project_app22_source(input_control_state, threshold):
    """Return final OUT control-state projection and all27 arithmetic steps.

    Exact source inputs: IN fPDCO4243/bank1 and signed threshold1739/bank0.
    Carrier9x11:81 exact Bool and18 exact finite floats. Threshold and every
    subtraction must remain finite. Invocation is isolated from external
    panel/local mutation. Stage5910 initializes OUT5283/bank2 before stage5053
    reads and updates it. No preexisting OUT state or saved default is used.
    """
    threshold = _finite(threshold, 'threshold')
    initial_out = _control_carrier(input_control_state)
    epochs = [StateAccess('5910', '5927', '5934', 'write', 2, '5283', initial_out)]
    current_out = initial_out
    epochs.append(StateAccess('5053', '1336', '1369', 'read', 2, '5283', current_out))
    arithmetic = []
    final_rows = []
    for group, ids in enumerate(ARITHMETIC_UIDS):
        sub, cons_face, lect_face, diff_face, absolute_node, abs_in, abs_out, greater, gt_in, limit_in, gt_out = ids
        consigne = initial_out[group][5]
        lecture = initial_out[group][6]
        difference = consigne - lecture
        if not math.isfinite(difference):
            raise App22DomainError('Subtract' + sub + ': finite result required')
        arithmetic.append(Primitive('5053', sub, 'Subtract', (cons_face, lect_face),
            diff_face, (consigne, lecture), difference))
        distance = abs(difference)
        arithmetic.append(Primitive('5053', absolute_node, 'Absolute Value', (abs_in,),
            abs_out, (difference,), distance))
        predicate = distance > threshold
        arithmetic.append(Primitive('5053', greater, 'Greater', (gt_in, limit_in),
            gt_out, (distance, threshold), predicate))
        updated = list(current_out[group])
        updated[2] = predicate
        final_rows.append(tuple(updated))
    final_out = tuple(final_rows)
    epochs.append(StateAccess('5053', '3800', '3813', 'write', 2, '5283', final_out))
    return App22Result(final_out, tuple(arithmetic), tuple(epochs), qualification_limits())
