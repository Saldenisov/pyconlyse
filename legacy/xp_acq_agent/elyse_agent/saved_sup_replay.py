"""Stateless JSON replay for exact saved SUP pure-kernel input domains."""
from . import saved_sup_helpers as core


def replay_saved_sup_helpers(payload):
    if type(payload) is not dict:
        raise TypeError('Explicit saved SUP helper object required')
    sid=payload.get('source_id')
    if sid=='APP-19':
        names=('buffer_x','buffer_y','extracted_row','extracted_column','integral_x','integral_y','average','iteration')
        if set(payload)!=set(('source_id',)+names):
            raise ValueError('Exact APP-19 supplied kernel fields required')
        value=core.profile_xy(*(payload[name] for name in names))
        outputs=dict(buffer_x=value[0],buffer_y=value[1],mean_x=value[2],mean_y=value[3],gate_x=value[4],gate_y=value[5],slot=value[6])
    elif sid in ('APP-21','APP-22'):
        if set(payload)!=set(('source_id','rows','threshold')):
            raise ValueError('Exact APP-21/22 supplied cluster fields required')
        function=core.discrepancy_vdirecte if sid=='APP-21' else core.discrepancy_vdeviee
        outputs=dict(rows=function(payload['rows'],payload['threshold']))
    else:
        raise ValueError('Only APP-19/21/22 SUP pure kernels qualified')
    return dict(source_id=sid,scope='BOUNDED_SAVED_PURE_KERNEL',outputs=outputs,
                native_execution=False,hardware_writes=False,image_processing_qualified=False,
                native_returned_semantics_qualified=False,runtime_defaults_qualified=False,
                native_scheduling_qualified=False,whole_VI_equivalence=False)
