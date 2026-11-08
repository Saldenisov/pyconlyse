"""Pure supplied-return projections of APP-01/02/04; Python 3.4 stdlib.

No callback or driver is invoked. Steps are wire-binding records, not native
scheduling. Unwired ports and unwritten public errors are explicit values.
"""
from collections import namedtuple
import math

ErrorValue = namedtuple('ErrorValue', 'status code source')
Reference = namedtuple('Reference', 'token')
ReturnValue = namedtuple('ReturnValue', 'task error')
CallStep = namedtuple('CallStep', 'uid frame iteration operation task_in error_in arguments returned')
Projection = namedtuple('Projection', 'source_id steps tasks public_error internal_error')
MissingValue = namedtuple('MissingValue', 'kind')
UNWIRED = MissingValue('unwired_external_default_unknown')
UNASSIGNED = MissingValue('unwritten_public_indicator_unknown')
DIO = (('2471','1345','C3_IN_DIO','3/port0:6','23'),
       ('1134','579','C4_IN_DIO','4/port0:7','23'),
       ('1456','912','C5_IN_DIO','5/port0:6','23'),
       ('1801','1740','C3_OUT_DIO','3/port7:11','24'),
       ('1953','1886','C4_OUT_DIO','4/port8:11','24'),
       ('2119','2047','C5_OUT_DIO','5/port7:11','24'))
AI = (('2383','2798','2629','2818','2393','2454','2561',1,'C1_NI6071E'),
      ('944','2948','2462','2959','998','2212','2380',2,'C2_NI6071E'))

def require_error(value):
    if type(value) is not ErrorValue or type(value.status) is not bool or type(value.code) is not int or type(value.source) is not str:
        raise TypeError('explicit bool/int/str ErrorValue required')
    if not -(2**31) <= value.code < 2**31:
        raise ValueError('I32 error code required; replay representation policy')

def require_return(value):
    if type(value) is not ReturnValue or type(value.task) is not Reference or type(value.task.token) is not str or not value.task.token:
        raise TypeError('explicit opaque Reference and ReturnValue required')
    require_error(value.error)

def require_fixtures(values, count):
    if type(values) is not tuple or len(values) != count:
        raise ValueError('exact ordered completed-return tuple required')
    for value in values:
        require_return(value)

def require_inputs(rate, samples, seed):
    if type(rate) is not float or not math.isfinite(rate):
        raise TypeError('finite DBL rate required; no native coercion inferred')
    if type(samples) is not int or not 0 <= samples < 2**31:
        raise ValueError('nonnegative I32 sample input required; negative-to-U64 coercion unresolved')
    if seed is not UNASSIGNED:
        require_error(seed)

def step(uid, frame, iteration, operation, task, error, arguments, returned):
    return CallStep(uid, frame, iteration, operation, task, error, tuple(arguments), returned)

def project_dio96(error_in, returns):
    require_error(error_in)
    require_fixtures(returns,12)
    steps=[];tasks=[];error=error_in
    for index,(create,channel,name,physical,selector) in enumerate(DIO):
        created,configured=returns[2*index:2*index+2]
        steps.append(step(create,'3',None,'create_task',UNWIRED,error,
                          (('name',name),('auto_cleanup',True)),created))
        steps.append(step(channel,'3',None,'create_digital_channel',created.task,created.error,
                          (('physical_channel',physical),('selector',selector)),configured))
        tasks.append(configured.task);error=configured.error
    return Projection('APP-01',tuple(steps),tuple(tasks),error,error)

def _ai_stage(spec, returned, rate, samples, trigger, incoming, steps, dormant=False):
    frame,body,create,channel,timing,trigger_uid,prop,device,name=spec
    created=returned[0]
    steps.append(step(create,frame,None,'create_task',UNWIRED,incoming,
                      (('name',name),('auto_cleanup',True)),created))
    channel_count=8 if dormant else 64
    for i in range(channel_count):
        maximum=.2 if dormant else (.05 if device==1 and i==2 else 1.0 if device==1 and i in(3,4) else 10.0)
        result=returned[i+1]
        steps.append(step(channel,body,i,'create_ai_voltage_channel',created.task,created.error,
                          (('physical_channel',str(device)+'/ai'+str(i)),('minimum',-maximum),('maximum',maximum),
                           ('terminal_configuration_code',0x277A if dormant else 0x2763),('units_code',0x286C),('selector','02')),result))
    last=returned[channel_count]
    timed=returned[channel_count+1]
    steps.append(step(timing,frame,None,'configure_sample_clock',last.task,last.error,
                      (('source','OnboardClock'),('rate_hz',rate),('samples_per_channel',samples),
                       ('sample_mode_code',0x27C2),('edge_code',0x2828),('selector','02')),timed))
    triggered=returned[channel_count+2]
    arguments=(('selector','02'),) if dormant else (('source',trigger),('edge_code',0x2828),('selector','03'))
    steps.append(step(trigger_uid,frame,None,'configure_start_trigger_none' if dormant else 'configure_start_trigger',
                      timed.task,timed.error,arguments,triggered))
    result=returned[channel_count+3]
    steps.append(step(prop,frame,None,'set_read_properties',triggered.task,triggered.error,
                      (('relative_to_code',0x28B9),('auto_start',True),('property_codes',(6410,6182))),result))
    return result

def project_ni6071e(rate_hz,samples_per_channel,trigger_c1,trigger_c2,error_in,returns,public_error_seed=UNASSIGNED):
    require_error(error_in)
    require_inputs(rate_hz,samples_per_channel,public_error_seed)
    if type(trigger_c1) is not str or type(trigger_c2) is not str:
        raise TypeError('explicit trigger strings required')
    if type(returns) is not tuple or len(returns)!=137:
        raise ValueError('136 DAQ/property returns and one unused handler error return required')
    require_fixtures(returns[:136],136)
    require_error(returns[136])
    steps=[]
    c1=_ai_stage(AI[0],returns[:68],rate_hz,samples_per_channel,trigger_c1,UNWIRED,steps)
    c2=_ai_stage(AI[1],returns[68:136],rate_hz,samples_per_channel,trigger_c2,c1.error,steps)
    steps.append(step('134','944',None,'simple_error_handler',UNWIRED,c2.error,(),returns[136]))
    return Projection('APP-02',tuple(steps),(c1.task,c2.task),public_error_seed,c2.error)

def project_ni6259(rate_hz,samples_per_channel,error_in,returns,public_error_seed=UNASSIGNED):
    require_error(error_in)
    require_inputs(rate_hz,samples_per_channel,public_error_seed)
    require_fixtures(returns,12)
    spec=('3','2798','2629','2818','2393','2454','2561',11,'C1_NI6220')
    steps=[]
    result=_ai_stage(spec,returns,rate_hz,samples_per_channel,None,UNWIRED,steps,True)
    # Saved property error output2593 is unwired. Internal error is a retained
    # analysis value only; no native public error value is synthesized.
    return Projection('APP-04',tuple(steps),(result.task,),public_error_seed,result.error)
