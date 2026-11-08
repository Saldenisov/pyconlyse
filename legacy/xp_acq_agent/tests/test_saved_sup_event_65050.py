"""New portable frame65050 cases; fixture embedded, no iteration-directory dependency."""
import copy
from fractions import Fraction
import itertools
import math
import os
import socket
import struct
import subprocess
import sys
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_sup_event_65050 as body


def fixture():
    return dict(source_id='APP-17',source_version='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9',event_uid='5909',frame_uid='65050',
        local_reads={'62319':20.0,'62327':10.0,'69067':40.0,'69089':30.0,'88920':[100.25+i for i in range(10)]},
        event_returns={'65078':{'65083':1073741826,'65087':321,'65090':{'supplied':'control-reference'},'65094':901.0,'65097':-902.0}},
        reference_inputs={'88958':{'supplied':'native-reference'}},
        unwired_inputs={'88947':{'status':True,'code':71,'source':'explicit-writer-error-input'},'86365':'explicit-input86365','86368':17,'86371':{'opaque':True},'86383':None},
        native_returns={'88939':{'88944':{'supplied':'unused-reference-return'},'88950':{'status':True,'code':-73,'source':'explicit-writer-fault'}},
            '83833':{'86359':'unused-out0','86362':False,'86374':4,'86377':{'supplied':'unused-handler-output'},'86380':None}},
        completed_sinks=['88976','83833'])


def decoded(hex_):return struct.unpack('>d',bytes.fromhex(hex_))[0]
def rounded_product(a,b):return float(Fraction.from_float(a)*Fraction.from_float(b))
def expected_fields(reads):
    p=decoded('3FB90FF972474539');n=decoded('BFB90FF972474539');h=decoded('3FA916872B020C4A');five=decoded('4014000000000000')
    first=float(Fraction.from_float(rounded_product(reads['62327'],p))+Fraction.from_float(five))
    second=float(Fraction.from_float(rounded_product(reads['69089'],n))+Fraction.from_float(five))
    return(float(Fraction.from_float(first)-Fraction.from_float(rounded_product(reads['62319'],h))),
        float(Fraction.from_float(second)-Fraction.from_float(rounded_product(reads['69067'],h))))


class Opaque(object):
    def __bool__(self):raise AssertionError('Native/event boundary truth tested')
    def __float__(self):raise AssertionError('Native/event boundary numerically coerced')
    def __call__(self,*unused):raise AssertionError('Native/event boundary called')
    def __iter__(self):raise AssertionError('Native/event boundary iterated')

class FloatSubclass(float):pass


class Event65050Tests(unittest.TestCase):
    def setUp(self):
        self.reads={'62319':20.0,'62327':10.0,'69067':40.0,'69089':30.0,'88920':tuple(1000.25+i for i in range(10))}
        self.opaque=Opaque();self.event=body.EventDataReturn(*(self.opaque for i in range(5)))
        self.error=body.UnwiredInput(self.opaque);self.writer=body.WriterReturn(self.opaque,self.opaque)
        self.handler_inputs=body.HandlerUnwiredInputs(*(self.opaque for i in range(4)))
        self.handler_returns=body.HandlerReturn(*(self.opaque for i in range(5)))
    def project(self,reads=None,completion=None):
        return body.project_event_65050(self.reads if reads is None else reads,self.event,self.opaque,self.error,self.writer,self.handler_inputs,self.handler_returns,completion)

    def test_source_operand_slots_and_fraction_expectations(self):
        patterns=[(20.0,10.0,40.0,30.0),(1.0,-9.0,77.0,2.0),(-0.0,0.0,0.0,-0.0),(2.0**40,-2.0**40,-2.0**40,2.0**40),(5e-324,-5e-324,1e-300,-1e-300)]
        for values in patterns:
            reads=dict(self.reads);reads.update(zip(('62319','62327','69067','69089'),values));result=self.project(reads)
            expected=expected_fields(reads);steps={s.node_uid:s for s in result.arithmetic_steps}
            self.assertEqual((result.updated_cluster[2],result.updated_cluster[3]),expected)
            self.assertEqual(steps['62285'].input_slots,((1,steps['62296'].value),(2,steps['62171'].value)))
            self.assertEqual(steps['69033'].input_slots,((1,steps['69044'].value),(2,steps['67319'].value)))
            self.assertEqual(steps['62285'].value,steps['62285'].input_slots[1][1]-steps['62285'].input_slots[0][1])
            self.assertEqual(len(result.arithmetic_steps),8)

    def test_independent_reads_shared_target_no_atomicity(self):
        result=self.project();reads={r.node_uid:r for r in result.local_reads}
        self.assertNotEqual(reads['62327'].data,reads['69089'].data)
        self.assertNotEqual(reads['62319'].data,reads['69067'].data)
        self.assertEqual((reads['62327'].saved_param_index,reads['69089'].saved_param_index),(221,221))
        self.assertEqual((reads['62319'].saved_param_index,reads['69067'].saved_param_index),(222,222))
        self.assertEqual((reads['88920'].saved_param_index,reads['88920'].control_id),(25,'66941'))

    def test_two_fields_eight_untouched_objects_and_fanout(self):
        result=self.project()
        for i in range(10):
            if i not in(2,3):self.assertIs(result.updated_cluster[i],self.reads['88920'][i])
        self.assertIsNot(result.updated_cluster,self.reads['88920'])
        self.assertIs(result.local_assignment.data,result.updated_cluster)
        self.assertIs(result.writer_call.data,result.updated_cluster)
        self.assertEqual(result.local_assignment.node_uid,'88976')

    def test_all_unused_native_event_leaves_never_accessed(self):
        result=self.project()
        self.assertIs(result.event_return,self.event)
        self.assertIs(result.writer_call.reference_in,self.opaque)
        self.assertIs(result.writer_call.supplied_error_input,self.opaque)
        self.assertIs(result.writer_call.returned,self.writer)
        self.assertIs(result.handler_call.supplied_error_in,self.writer.error_out)
        self.assertIs(result.handler_call.unwired_inputs,self.handler_inputs)
        self.assertIs(result.handler_call.returned,self.handler_returns)
        self.assertEqual(result.handler_call.wired_error_input_uid,'86386')

    def test_completions_permutations_error_does_not_gate_assignment(self):
        choices=[None]+[p for n in range(4)for p in itertools.permutations(('88976','88939','83833'),n)]
        for completion in choices:
            result=self.project(completion=completion)
            self.assertIs(result.completed_sinks,completion)
            self.assertIs(result.local_assignment.data,result.writer_call.data)
            self.assertIs(result.handler_call.supplied_error_in,self.opaque)
        for bad in ([],('88976','88976'),('88944',),('88976',False),('88976','88939','83833','88976')):
            with self.assertRaises(ValueError):self.project(completion=bad)

    def test_bounded_float_inputs_and_exact_boundary_records(self):
        for value in(True,1,'2',None,FloatSubclass(2.0),float('nan'),float('inf'),-float('inf'),2.0**41):
            reads=dict(self.reads);reads['62319']=value
            with self.assertRaises(ValueError):self.project(reads)
        for carrier in(list(self.reads['88920']),self.reads['88920'][:-1],(1,)+self.reads['88920'][1:]):
            reads=dict(self.reads);reads['88920']=carrier
            with self.assertRaises(TypeError):self.project(reads)
        for extra in(dict(self.reads,unexpected=1.0),{k:v for k,v in self.reads.items()if k!='69089'}):
            with self.assertRaises(ValueError):self.project(extra)
        args=[self.reads,self.event,self.opaque,self.error,self.writer,self.handler_inputs,self.handler_returns]
        for index in(1,3,4,5,6):
            bad=list(args);bad[index]=tuple(args[index])
            with self.assertRaises(TypeError):body.project_event_65050(*bad)

    def test_embedded_portable_json_fixture_exact_source_and_fault(self):
        payload=fixture();before=copy.deepcopy(payload);result=body.replay_saved_sup_event_65050(payload)
        self.assertEqual(payload,before);self.assertEqual(tuple(result['projected_cluster'][i]for i in(2,3)),expected_fields(payload['local_reads']))
        self.assertEqual(result['writer_call']['supplied_returns']['88950']['code'],-73)
        self.assertIs(result['handler_call']['supplied_error_in'],payload['native_returns']['88939']['88950'])
        self.assertFalse(result['writer_success_gates_local_assignment']);self.assertFalse(result['handler_success_gates_local_assignment'])
        self.assertFalse(result['native_float_bitwise_equivalence']);self.assertFalse(result['whole_event_equivalence'])
        for bad in(dict(payload,source_id='APP-18'),dict(payload,source_version='0'*64),dict(payload,frame_uid='73301'),dict(payload,extra=0)):
            with self.assertRaises(ValueError):body.replay_saved_sup_event_65050(bad)

    def test_json_bounds_finite_exact_shape_and_native_tree(self):
        for path,value in[(('local_reads','62327'),1),(('local_reads','62327'),float('nan')),(('native_returns','88939','88950'),Opaque())]:
            payload=fixture();target=payload
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.assertRaises((ValueError,TypeError)):body.replay_saved_sup_event_65050(payload)
        payload=fixture();payload['event_returns']['65078']['65097']='x'*4097
        with self.assertRaises(ValueError):body.replay_saved_sup_event_65050(payload)
        payload=fixture();payload['unwired_inputs']['86365']=list(range(65))
        with self.assertRaises(ValueError):body.replay_saved_sup_event_65050(payload)

    def test_external_IO_tripwires(self):
        import builtins
        def refused(*args,**kwargs):raise AssertionError('External IO attempted')
        slots=((socket,'socket'),(subprocess,'Popen'),(os,'system'),(builtins,'open'))
        for module,name in slots:
            previous=getattr(module,name);setattr(module,name,refused)
            try:self.project();body.replay_saved_sup_event_65050(fixture())
            finally:setattr(module,name,previous)

    def test_pure_untouched_nonfinite_carrier_does_not_infer_native_domain(self):
        reads=dict(self.reads);carrier=list(reads['88920']);carrier[0]=float('nan');carrier[9]=float('inf');reads['88920']=tuple(carrier)
        result=self.project(reads)
        self.assertIs(result.updated_cluster[0],carrier[0]);self.assertIs(result.updated_cluster[9],carrier[9])
        payload=fixture();payload['local_reads']['88920'][0]=float('nan')
        with self.assertRaises(ValueError):body.replay_saved_sup_event_65050(payload)

if __name__=='__main__':unittest.main()
