"""Stateless JSON adapter for three source-linked supplied-return card bodies."""
from . import saved_card_init as core


def exact(value, fields):
    if type(value) is not dict or set(value)!=set(fields):
        raise ValueError('Exact saved card replay fields required: '+','.join(fields))


def error(value):
    exact(value,('status','code','source'))
    result=core.ErrorValue(value['status'],value['code'],value['source'])
    core.require_error(result)
    return result


def returned(value):
    exact(value,('task','error'))
    result=core.ReturnValue(core.Reference(value['task']),error(value['error']))
    core.require_return(result)
    return result


def encoded_error(value):
    if value is core.UNASSIGNED:
        return dict(kind='unwritten_public_indicator_unknown')
    return dict(status=value.status,code=value.code,source=value.source)


def replay_saved_card_init(payload):
    if type(payload) is not dict:
        raise TypeError('Explicit saved card replay object required')
    sid=payload.get('source_id')
    if sid not in ('APP-01','APP-02','APP-04'):
        raise ValueError('Only APP-01/02/04 saved card bodies qualified')
    fields=['source_id','returns','error_in']
    if sid!='APP-01':
        fields+=['rate_hz','samples_per_channel','public_error_seed']
    if sid=='APP-02':fields+=['trigger_c1','trigger_c2']
    exact(payload,fields)
    values=payload['returns']
    if type(values) is not list:
        raise TypeError('Ordered JSON completed-return list required')
    incoming=error(payload['error_in'])
    if sid=='APP-02':
        if len(values)!=137:
            raise ValueError('136 task returns andone handler error return required')
        fixtures=tuple(returned(v) for v in values[:136])+(error(values[136]),)
    else:
        fixtures=tuple(returned(v) for v in values)
    if sid=='APP-01':
        result=core.project_dio96(incoming,fixtures)
    else:
        seed=core.UNASSIGNED if payload['public_error_seed'] is None else error(payload['public_error_seed'])
        if sid=='APP-02':
            result=core.project_ni6071e(payload['rate_hz'],payload['samples_per_channel'],
                 payload['trigger_c1'],payload['trigger_c2'],incoming,fixtures,seed)
        else:
            result=core.project_ni6259(payload['rate_hz'],payload['samples_per_channel'],incoming,fixtures,seed)
    return dict(source_id=sid,scope='SUPPLIED_COMPLETED_RETURN_BODY',
                outputs=dict(tasks=[r.token for r in result.tasks],public_error=encoded_error(result.public_error),
                             internal_error=encoded_error(result.internal_error)),
                call_bindings=len(result.steps),native_execution=False,hardware_writes=False,
                reference_validity_qualified=False,runtime_defaults_qualified=False,
                native_scheduling_qualified=False,whole_VI_equivalence=False)
