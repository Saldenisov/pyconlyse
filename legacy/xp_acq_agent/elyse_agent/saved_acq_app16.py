"""Original APP-16 complete source-defined logic in an explicit isolated domain.

This model does not execute LabVIEW, front-panel controls, hardware, or callees.
All inputs are required. The original IEEE exceptional domains and concurrent
panel mutation are excluded; native/runtime equivalence remains unqualified.
"""
import math

SOURCE_ID = 'APP-16'
SOURCE_VERSION = '276E9FDDDD9A29D5DC559A3F02BE1DF9E69514848A7C1D67251C9CA03EA2E831'
STORAGE_POLICY = 'ISOLATED_SINGLE_INVOCATION'
ARITHMETIC_DOMAIN = 'FINITE_BINARY64_NO_SUBTRACTION_OVERFLOW'
GROUP_NAMES = ('Quadrup\u00f4le 1', 'Quadrup\u00f4le 2', 'Triplet 2-1',
               'Triplet 2-2', 'Correcteur H4', 'Correcteur V4', 'Dip\u00f4le 2',
               'Correcteur H5', 'Correcteur V5')
FIELD_NAMES = ('M/A', 'en marche', 'orange', 'en d\u00e9faut', 'X1/X10',
               'Consigne', 'Lecture', '<<', '<', '>', '>>')
# Original star joins: [Subtract/output/y/x, Abs/output/input,
# Greater/output/y/x, Unbundle Consigne/Lecture, Bundle orange input].
CHANNELS = (
    ('3320','3326','3329','3332','3408','3445','3448','1400','1408','1411','1716','2577','2580','1578'),
    ('3460','3466','3469','3472','3478','3480','3483','68','1810','1817','1820','2583','2586','1583'),
    ('3545','3551','3554','3557','3563','3565','3568','1346','1357','1838','1841','2589','2592','1586'),
    ('3571','3573','3576','3579','3582','3584','3587','1847','1849','1852','1855','2595','2598','1589'),
    ('3592','3639','3642','3645','3651','3653','3656','1362','1372','1860','1863','2601','2604','1592'),
    ('3659','3661','3664','3667','3670','3672','3675','1869','1871','1874','1877','2607','2610','1595'),
    ('3678','3680','3683','3686','3689','3691','3694','1375','1385','1882','1885','2613','2616','1598'),
    ('3697','3699','3702','3705','3708','3710','3713','1891','1893','1896','1899','2619','2622','1601'),
    ('3728','3803','3806','3809','3815','3817','3820','1449','1732','1936','1939','2625','2628','1604'),
)


def _float64(value, name):
    if type(value) is not float or not math.isfinite(value):
        raise ValueError(name + ': finite binary64 float required; no coercion/default')
    return value


def _cluster(value):
    if type(value) not in (tuple, list) or len(value) != 9:
        raise ValueError('4245: exactly nine positional device clusters required')
    rows = []
    for group, row in enumerate(value):
        if type(row) not in (tuple, list) or len(row) != 11:
            raise ValueError('4245: each device cluster must have exactly eleven fields')
        items = []
        for field, item in enumerate(row):
            if field in (5, 6):
                items.append(_float64(item, '4245[%s][%s]' % (group, field)))
            elif type(item) is not bool:
                raise ValueError('4245[%s][%s]: exact Boolean required' % (group, field))
            else:
                items.append(item)
        rows.append(tuple(items))
    return tuple(rows)


def compute_vi(input_cluster, threshold, *, storage_policy):
    """Execute both original sequence stages without supplied business returns.

    ``storage_policy`` explicitly excludes external mutation between the first
    OUT write, the later OUT local read, and the final OUT write. No native
    scheduling, serializer, default value, or callback is selected implicitly.
    """
    if type(storage_policy) is not str or storage_policy != STORAGE_POLICY:
        raise ValueError('explicit ISOLATED_SINGLE_INVOCATION storage domain required')
    source = _cluster(input_cluster)
    limit = _float64(threshold, '1741')
    trace = []
    node_outputs = {}
    # Sequence2636 first physical diagram5910: tunnel5177 transports IN and
    # local5927 writes the entire OUT5285 bank before diagram5053 begins.
    storage = source
    node_outputs['5927'] = {'5934': storage}
    trace.append(dict(uid='5927', diagram_uid='5910', operation='WRITE_OUT', ports={'5934': storage}))
    # In the declared isolated storage domain, local1336 reads the bank that the
    # completed prior sequence stage wrote. The aggregate input1555 is this read.
    aggregate = storage
    node_outputs['1336'] = {'1369': aggregate}
    trace.append(dict(uid='1336', diagram_uid='5053', operation='READ_OUT', ports={'1369': aggregate}))
    values = {}
    for index, row in enumerate(source):
        values[CHANNELS[index][11]] = row[5]
        values[CHANNELS[index][12]] = row[6]
    node_outputs['2568'] = values
    trace.append(dict(uid='2568', diagram_uid='5053', operation='UNBUNDLE_NAMED', ports=values))
    rows = [list(row) for row in aggregate]
    differences = []
    magnitudes = []
    flags = []
    for index, channel in enumerate(CHANNELS):
        (sub, sub_out, sub_y, sub_x, absolute, abs_out, abs_in,
         greater, greater_out, greater_y, greater_x, consigne, lecture, orange) = channel
        x, y = values[consigne], values[lecture]
        delta = x - y
        if not math.isfinite(delta):
            raise ValueError('Subtract' + sub + ': result outside finite no-overflow domain')
        magnitude = abs(delta)
        result = magnitude > limit
        differences.append(delta); magnitudes.append(magnitude); flags.append(result)
        node_outputs[sub] = {sub_out: delta}
        node_outputs[absolute] = {abs_out: magnitude}
        node_outputs[greater] = {greater_out: result}
        trace.append(dict(uid=sub, diagram_uid='5053', operation='SUBTRACT', input_ports={sub_x:x, sub_y:y}, ports={sub_out:delta}))
        trace.append(dict(uid=absolute, diagram_uid='5053', operation='ABS', input_ports={abs_in:delta}, ports={abs_out:magnitude}))
        trace.append(dict(uid=greater, diagram_uid='5053', operation='GREATER', input_ports={greater_x:magnitude, greater_y:limit}, ports={greater_out:result}))
        rows[index][2] = result
    result = tuple(tuple(row) for row in rows)
    bundle_inputs = {'1577': aggregate}
    for index, channel in enumerate(CHANNELS):
        bundle_inputs[channel[13]] = flags[index]
    node_outputs['1555'] = {'1565': result}
    trace.append(dict(uid='1555', diagram_uid='5053', operation='BUNDLE_NAMED', input_ports=bundle_inputs, ports={'1565':result}))
    storage = result
    node_outputs['3800'] = {'3813':storage}
    trace.append(dict(uid='3800', diagram_uid='5053', operation='WRITE_OUT', ports={'3813':storage}))
    node_outputs['2636'] = {'completed_diagrams': ('5910','5053')}
    return dict(source_id=SOURCE_ID, source_version=SOURCE_VERSION,
                input_ports={'4245':source, '1741':limit}, output_control_state={'5285':storage},
                difference_values=tuple(differences), absolute_values=tuple(magnitudes),
                orange_values=tuple(flags), node_outputs=node_outputs, trace=tuple(trace),
                completed_diagrams=('5910','5053'),
                complete_source_defined_logic_in_domain=True,
                domain={'local_storage':STORAGE_POLICY, 'arithmetic':ARITHMETIC_DOMAIN},
                supplied_callee_returns=0, supplied_literal_or_index_hypotheses=0,
                source_VI_execution=False, native_execution=False, hardware_execution=False,
                original_connector_return_qualified=False, original_runtime_equivalence=False,
                unrestricted_whole_VI_semantic_equivalence=False)


def compute_saved_app16(payload):
    """Strict JSON-compatible input/output adapter; no external-file access."""
    if type(payload) is not dict or set(payload) != {'source_id','source_version','inputs','domain'}:
        raise ValueError('exact APP-16 source/version/inputs/domain envelope required')
    if payload['source_id'] != SOURCE_ID or payload['source_version'] != SOURCE_VERSION:
        raise ValueError('exact original APP-16 compound source version required')
    inputs, domain = payload['inputs'], payload['domain']
    if type(inputs) is not dict or set(inputs) != {'4245','1741'}:
        raise ValueError('exact original connector input terminals4245/1741 required')
    if type(domain) is not dict or domain != {'local_storage':STORAGE_POLICY, 'arithmetic':ARITHMETIC_DOMAIN}:
        raise ValueError('explicit exact isolated finite arithmetic domain required')
    value = compute_vi(inputs['4245'], inputs['1741'], storage_policy=domain['local_storage'])
    def encode(item):
        if type(item) is dict:
            return {key:encode(value) for key,value in item.items()}
        if type(item) is tuple:
            return [encode(value) for value in item]
        return item
    return encode(value)
