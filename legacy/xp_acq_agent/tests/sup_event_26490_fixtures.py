"""Portable literal fixtures; Boolean decodes/native observations are hypothetical."""
import copy

SOURCE_VERSION = 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
FLAGS = ('native_execution_qualified', 'native_storage_serializer_qualified',
         'native_default_policy_qualified', 'native_reference_validity_qualified',
         'native_wait_units_or_timing_qualified', 'native_event_selection_qualified',
         'native_delivery_or_scheduling_qualified', 'native_atomic_snapshot_qualified',
         'native_primitive_coercion_qualified', 'whole_event_equivalence', 'whole_VI_equivalence')


def minimal_payload():
    return dict(source_id='APP-17', source_version=SOURCE_VERSION, event_uid='5909',
                frame_uid='26490', literal_inputs={'20659': True, '21637': False},
                unqualified_boundaries={flag: False for flag in FLAGS})


def full_payload():
    value = minimal_payload()
    value.update(wait_return={'22087': {'opaque': 'supplied unused U32 return'}},
                 event_outputs={'26508': {'opaque': 'unwired aggregate'},
                                '26511': 7, '26516': 123, '26519': ['opaque ref'],
                                '26532': 9, '26538': 10},
                 completed_sinks=['19732', '22081', '21619'])
    return value


def sparse_payload():
    value = minimal_payload()
    value.update(literal_inputs={'20659': False, '21637': True},
                 wait_return=None, completed_sinks=['21619'])
    return value


def payload(kind='full'):
    return copy.deepcopy({'full': full_payload, 'minimal': minimal_payload,
                          'sparse': sparse_payload}[kind]())
