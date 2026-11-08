"""Complete APP15 finite isolated STATIC-INTERPRETED control-state model.

The sole Boolean literal is fixed by the reviewed LabVIEW20.0.1f1 static
rendering of byte-identical original LV12 source, not by a raw0000 decoder.
This model does not qualify original LV12 literal/runtime equivalence,
native concurrency, connector invocation or unrestricted numeric semantics.
"""
from collections import namedtuple
import math

SOURCE_ID = 'APP-15'
SOURCE_VERSION = '6688203B4D70431CEBA479182F1330492F9EEE9919440CCD301FF4E1E5F78836'
ORIGINAL_VI_SHA256 = '5C9E6C4E20FB9CC5B023C9DC56DC58C4D17EB4C63504722A0D6B8D19CF499AD5'
MODEL_CATEGORY = 'COMPLETE_STATIC_INTERPRETED_FINITE_ISOLATED_STATE_PROJECTION'
LITERAL_DCO_UID = '3054'
LITERAL_TERMINAL_UID = '3056'
LITERAL_NATIVE_VERSION = '20.0.1f1'
LITERAL_STATIC_VALUE = False

# Logical operand order follows upper/lower source ports, not termList order.
# Subtract: node, upperConsigne, lowerLecture, out;
# Absolute: node, in, out; Greater: node, upperAbs, lowerThreshold, out.
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
    ('3823', '3831', '3828', '3825', '3834', '3839', '3836', '1945', '1953', '1950', '1947'),
    ('3842', '3850', '3847', '3844', '3853', '3858', '3855', '1956', '1964', '1961', '1958'),
)

PrimitiveStep = namedtuple('PrimitiveStep',
    'physical_diagram_uid node_uid operation argument_terminal_uids '
    'output_terminal_uid arguments result result_consumed')
LocalStateStep = namedtuple('LocalStateStep',
    'physical_diagram_uid node_uid terminal_uid action target_fPDCO_uid control_state')
StaticApp15Result = namedtuple('StaticApp15Result',
    'output_control_state arithmetic_trace local_state_trace interpretation_limits')


class App15DomainError(ValueError):
    """Input lies outside this finite isolated static model's explicit domain."""


def interpretation_limits():
    return dict(
        model_category=MODEL_CATEGORY,
        complete_static_interpreted_model=True,
        complete_original_semantic_qualification=False,
        specific_native20_static_literal_interpretation=True,
        LV12_literal_equivalence=False,
        serializer_qualified=False,
        original_LV12_runtime_equivalence=False,
        original_connector_invocation=False,
        native_concurrency=False,
        unrestricted_numeric_semantics=False,
        native_or_source_VI_execution=False,
        supplied_business_returns=False,
        supplied_literal_or_field_index=False,
        original_native_whole_semantic_equivalence=False,
        trace_order_is_native_schedule=False)


def _finite_float(value, name):
    if type(value) is not float or not math.isfinite(value):
        raise App15DomainError(name + ': exact finite float required')
    return value


def _input_state(value):
    if type(value) not in (tuple, list) or len(value) != 11:
        raise App15DomainError('IN: exact 11-row list or tuple required')
    rows = []
    for group, row in enumerate(value):
        if type(row) not in (tuple, list) or len(row) != 11:
            raise App15DomainError('IN row: exact 11-field list or tuple required')
        for field, item in enumerate(row):
            if field in (5, 6):
                _finite_float(item, 'IN[{0}][{1}]'.format(group, field))
            elif type(item) is not bool:
                raise App15DomainError('IN Boolean: exact bool required')
        rows.append(tuple(row))
    return tuple(rows)


def project_app15_static_interpreted(input_control_state, threshold):
    """Return final OUT state and all source arithmetic/local-state steps.

    Domain: 11 rows of 11 fields (99 exact bools, 22 exact finite floats),
    finite signed float threshold, all 11 subtraction results finite, isolated
    invocation. No initial OUT value is supplied: stage5910 writes IN to OUT.
    All ten other fields in every row retain their supplied object identities.
    Trace group order is this Python model's order, not native scheduling.
    """
    threshold = _finite_float(threshold, 'threshold')
    initial_out = _input_state(input_control_state)

    # FlatSequence2636: physical stage5910 writes OUT bank2/fPDCO2983.
    local_trace = [LocalStateStep('5910', '5927', '5934', 'write', '2983', initial_out)]
    # Physical stage5053 reads the initialized same OUT control before bundle1555.
    read_out = initial_out
    local_trace.append(LocalStateStep('5053', '1336', '1369', 'read', '2983', read_out))

    arithmetic = []
    updated_rows = []
    for group, source_uids in enumerate(ARITHMETIC_UIDS):
        (sub_node, consigne_term, lecture_term, difference_term,
         abs_node, abs_input_term, absolute_term,
         greater_node, greater_input_term, threshold_term, comparison_term) = source_uids
        consigne = initial_out[group][5]
        lecture = initial_out[group][6]
        difference = consigne - lecture
        if not math.isfinite(difference):
            raise App15DomainError('Subtract' + sub_node + ': finite result required')
        arithmetic.append(PrimitiveStep('5053', sub_node, 'Subtract',
            (consigne_term, lecture_term), difference_term,
            (consigne, lecture), difference, True))
        absolute = abs(difference)
        arithmetic.append(PrimitiveStep('5053', abs_node, 'Absolute Value',
            (abs_input_term,), absolute_term, (difference,), absolute, True))
        comparison = absolute > threshold
        arithmetic.append(PrimitiveStep('5053', greater_node, 'Greater',
            (greater_input_term, threshold_term), comparison_term,
            (absolute, threshold), comparison, group != 2))

        row = list(read_out[group])
        # Original1346->1357 is evaluated but has no saved outgoing branch.
        # Original3054->3056->signal1341->1586 feeds row2 orange instead.
        row[2] = LITERAL_STATIC_VALUE if group == 2 else comparison
        updated_rows.append(tuple(row))

    final_out = tuple(updated_rows)
    local_trace.append(LocalStateStep('5053', '3800', '3813', 'write', '2983', final_out))
    return StaticApp15Result(final_out, tuple(arithmetic), tuple(local_trace),
        interpretation_limits())
