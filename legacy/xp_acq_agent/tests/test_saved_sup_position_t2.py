"""Independent positional expectations and refused native/default assumptions."""
import copy
from fractions import Fraction
import itertools
import math
import os
import socket
import struct
import subprocess
import unittest
from unittest.mock import patch

from elyse_agent import saved_sup_position_t2 as core


class Opaque(object):
    def __bool__(self): raise AssertionError('Opaque supplied leaf inspected')
    def __eq__(self, other): raise AssertionError('Opaque supplied leaf compared')
    def __iter__(self): raise AssertionError('Opaque supplied leaf iterated')
    def __getattr__(self, name): raise AssertionError('Opaque supplied leaf decoded')


def supplied(selector=1, completion=None):
    return (tuple(float(i) + 0.25 for i in range(10)),
        core.EventDataReturn(Opaque(), Opaque(), Opaque(), Opaque(), selector),
        Opaque(), core.UnwiredInput(Opaque()), core.WriterReturn(Opaque(), Opaque()), completion)


def payload(selector=1, completion=None):
    return dict(source_id='APP-17', event_uid='5909', frame_uid='71391',
        local_reads={'71442':[float(i) + 0.25 for i in range(10)]},
        event_returns={'71410':{'71415':{'opaque':'event-type'}, '71418':None,
            '71421':['opaque-control-reference'], '71424':{'opaque':'old-value'}, '71427':selector}},
        references={'71489':{'opaque':'native-reference'}}, unwired_inputs={'71476':{'opaque':'effective-native-error'}},
        writer_returns={'71458':{'71467':['opaque-returned-ref'],
            '71480':{'status':True, 'code':-1, 'source':'supplied fault'}}}, completed_sinks=completion)


def gain(selector):
    return struct.unpack('>d',bytes.fromhex(('4001020C49BA5E35','4021F5C28F5C28F6','40163645A1CAC083')[selector]))[0]


class PositionT2Tests(unittest.TestCase):
    def test_no_file_network_process_or_system_access(self):
        def refused(*args,**kwargs):raise AssertionError('Pure projection attempted external IO')
        with patch('builtins.open',refused),patch.object(socket,'socket',refused),patch.object(subprocess,'Popen',refused),patch.object(os,'system',refused):
            core.project_position_t2(*supplied())
            result=core.replay_saved_sup_position_t2(payload())
            self.assertIs(result['external_calls_executed'],False)

    def test_three_source_literals_scalar_and_distinct_cluster_sink_data(self):
        for selector in range(3):
            args=supplied(selector);result=core.project_position_t2(*args);g=gain(selector)
            expected=float(Fraction.from_float(g)*10)
            self.assertEqual(result.selected_gain,g);self.assertEqual(result.multiplied_value,expected)
            self.assertEqual(result.case_frame_uid,('78323','78344','78365')[selector])
            self.assertEqual(result.gain_constant_uid,('78329','78350','78371')[selector])
            self.assertEqual(result.updated_cluster,tuple(g if i==5 else args[0][i] for i in range(10)))
            self.assertEqual(args[0],tuple(float(i)+0.25 for i in range(10)))
            self.assertIs(result.local_read.data,args[0]);self.assertIs(result.event_return,args[1])
            for i in range(10):
                if i!=5:self.assertIs(result.updated_cluster[i],args[0][i])
            a,b=result.local_assignments
            self.assertEqual((a.node_uid,a.control_id,a.saved_param_index,a.saved_bank_uid),('57843','33171',152,'33032'))
            self.assertEqual((b.node_uid,b.control_id,b.saved_param_index,b.saved_bank_uid),('71434','66941',25,'66939'))
            self.assertEqual(a.data,expected);self.assertIs(b.data,result.updated_cluster)
            self.assertIs(result.writer_call.data,result.updated_cluster)
        self.assertEqual(struct.pack('>d',core.project_position_t2(*supplied(1)).multiplied_value),bytes.fromhex('4056733333333334'))

    def test_selector_u16_storage_does_not_admit_unproved_default(self):
        for bad in (-1,3,4,32767,65535,65536,2**64,True,False,0.0,1.0,'1',None):
            with self.assertRaises(ValueError):core.project_position_t2(*supplied(bad))

    def test_native_and_unused_outputs_never_inspected_or_success_gates(self):
        args=supplied();result=core.project_position_t2(*args)
        self.assertIs(result.writer_call.reference_in,args[2]);self.assertIs(result.writer_call.supplied_error_input,args[3].effective_value)
        self.assertIs(result.writer_call.returned,args[4]);self.assertEqual(result.writer_call.source_error_connection,'unwired')
        self.assertEqual(result.writer_call.reference_literal,'ni.var.psp://localhost/SUPERVISION/C9NI6703')
        for status in (False,True):
            for code in (-2147483648,-1,0,1,2147483647):
                args=list(supplied());args[4]=core.WriterReturn(Opaque(),{'status':status,'code':code,'source':'supplied'})
                self.assertEqual(core.project_position_t2(*args).local_assignments[0].data,result.multiplied_value)

    def test_completion_all_prefixes_independent_from_fanout_and_failure(self):
        prefixes=[p for n in range(4)for p in itertools.permutations(('57843','71434','71458'),n)]
        self.assertEqual(len(prefixes),16)
        for p in prefixes:
            result=core.project_position_t2(*supplied(completion=p));self.assertIs(result.completed_sinks,p)
            self.assertEqual(len(result.local_assignments),2)
        self.assertIsNone(core.project_position_t2(*supplied()).completed_sinks)
        for bad in ([],('57843','57843'),('unknown',),('71458',True),('57843','71434','71458','unknown')):
            with self.assertRaises(ValueError):core.project_position_t2(*supplied(completion=bad))
        self.assertNotIn(('71458','57843'),core.DEPENDENCIES);self.assertNotIn(('57843','71434'),core.DEPENDENCIES)

    def test_carrier_shape_no_coercion_and_untouched_nonfinite_signed_zero(self):
        args=list(supplied());fields=list(args[0]);fields[0]=float('nan');fields[1]=float('inf');fields[2]=-0.0
        args[0]=tuple(fields);result=core.project_position_t2(*args)
        self.assertIs(result.updated_cluster[0],args[0][0]);self.assertIs(result.updated_cluster[1],args[0][1])
        self.assertEqual(math.copysign(1.0,result.updated_cluster[2]),-1.0)
        for bad in ([],tuple([0.0]*9),tuple([0.0]*11),tuple([0]*10),tuple([False]*10)):
            args=list(supplied());args[0]=bad
            with self.assertRaises(TypeError):core.project_position_t2(*args)
        for i in (1,3,4):
            args=list(supplied());args[i]=None
            with self.assertRaises(TypeError):core.project_position_t2(*args)

    def test_exact_json_adapter_uses_same_core_preserves_supplied_slots(self):
        for selector in range(3):
            p=payload(selector,['71458','57843']);before=copy.deepcopy(p);r=core.replay_saved_sup_position_t2(p)
            self.assertEqual(p,before);self.assertEqual(r['projected_cluster'][5],gain(selector))
            self.assertEqual(r['multiplied_value'],float(Fraction.from_float(gain(selector))*10))
            self.assertIs(r['event_returns'],p['event_returns']['71410'])
            self.assertIs(r['writer_call']['supplied_returns'],p['writer_returns']['71458'])
            self.assertIs(r['writer_call']['supplied_native_reference'],p['references']['71489'])
            self.assertIs(r['writer_call']['supplied_effective_unwired_error'],p['unwired_inputs']['71476'])
            self.assertIs(r['completed_sinks'],p['completed_sinks'])
            for k in ('fanout_order_qualified','writer_success_gates_local_assignments','case_default_qualified',
                      'native_float_bitwise_equivalence','whole_event_equivalence','external_calls_executed'):
                self.assertIs(r[k],False)

    def test_json_exact_site_ports_and_identity_refusals(self):
        for key in payload():
            p=payload();del p[key]
            with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
        for key in ('source_id','event_uid','frame_uid'):
            p=payload();p[key]='wrong'
            with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
        for outer in ('local_reads','event_returns','references','unwired_inputs','writer_returns'):
            p=payload();p[outer]={'wrong-site':None}
            with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
        for outer,inner,ports in [('event_returns','71410',('71415','71418','71421','71424','71427')),
                                 ('writer_returns','71458',('71467','71480'))]:
            for port in ports:
                p=payload();del p[outer][inner][port]
                with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
            p=payload();p[outer][inner]['extra']=None
            with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)

    def test_json_bounds_and_default_refusals(self):
        for bad in (float('nan'),float('inf'),-float('inf'),2**80,'x'*4097,[None]*65):
            p=payload();p['writer_returns']['71458']['71480']=bad
            with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
        for bad in (3,65535,True,1.0):
            p=payload();p['event_returns']['71410']['71427']=bad
            with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
        p=payload();p['references']['71489']=Opaque()
        with self.assertRaises(TypeError):core.replay_saved_sup_position_t2(p)
        p=payload();nested=None
        for unused in range(10):nested=[nested]
        p['references']['71489']=nested
        with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
        p=payload();p['local_reads']['71442'][0]=float('nan')
        with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)
        p=payload();p['references']['71489']={False:None}
        with self.assertRaises(ValueError):core.replay_saved_sup_position_t2(p)


if __name__=='__main__':unittest.main()
