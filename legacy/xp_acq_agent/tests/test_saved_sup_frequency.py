"""Independent source-ordinal expectations; no VI/PSP/native execution."""
import itertools
import math
import unittest

from elyse_agent import saved_sup_frequency as core


class Opaque(object):
    def __bool__(self):
        raise AssertionError('unused supplied boundary was inspected')

    def __eq__(self, other):
        raise AssertionError('unused supplied boundary was compared')

    def __iter__(self):
        raise AssertionError('unused supplied boundary was iterated')

    def __getattr__(self, name):
        raise AssertionError('unused supplied boundary field was decoded')


def supplied(new_value=17, completion=None):
    snapshot = tuple(float(i) + 0.25 for i in range(33))
    event = core.EventDataReturn(Opaque(), Opaque(), Opaque(), Opaque(), new_value)
    return (snapshot, event, Opaque(), core.UnwiredInput(Opaque()),
            core.WriterReturn(Opaque(), Opaque()), completion)


def payload(new_value=17, completion=None):
    return dict(source_id='APP-17', event_uid='5909', frame_uid='70866',
        local_reads={'60452':[float(i) + 0.25 for i in range(33)]},
        event_returns={'70885':{'70890':{'opaque':'type'}, '70893':None, '71466':['opaque-ref'],
                              '71471':{'opaque':'old'}, '71474':new_value}},
        references={'70272':{'opaque':'native-reference'}}, unwired_inputs={'70261':{'opaque':'effective-error'}},
        writer_returns={'70253':{'70258':{'opaque':'returned-reference'}, '70264':{'opaque':'returned-error'}}},
        completed_sinks=completion)


class FrequencyTests(unittest.TestCase):
    def test_source_two_field_copy_and_all_sink_fanout(self):
        args = supplied()
        before = args[0]
        result = core.project_frequency(*args)
        self.assertIs(result.local_read.data, before)
        self.assertIs(result.event_return, args[1])
        self.assertIsNot(result.updated_cluster, before)
        expected = tuple(17.0 if i == 3 else 4.0 if i == 32 else before[i] for i in range(33))
        self.assertEqual(result.updated_cluster, expected)
        self.assertEqual(before, tuple(float(i) + 0.25 for i in range(33)))
        for i in range(33):
            if i not in (3,32):
                self.assertIs(result.updated_cluster[i], before[i])
        self.assertEqual(result.updated_cluster[2], before[2])
        self.assertEqual([(a.node_uid,a.control_id,a.saved_param_index,a.saved_bank_uid) for a in result.local_assignments],
            [('59714','38232',163,'38230'),('70290','30288',170,'30286')])
        for assignment in result.local_assignments:
            self.assertIs(assignment.data, result.updated_cluster)
        self.assertIs(result.writer_call.data, result.updated_cluster)
        self.assertIs(result.writer_call.reference_in, args[2])
        self.assertIs(result.writer_call.supplied_error_input, args[3].effective_value)
        self.assertIs(result.writer_call.returned, args[4])
        self.assertEqual(result.writer_call.source_error_connection, 'unwired')
        self.assertEqual(result.writer_call.reference_literal, 'ni.var.psp://localhost/SUPERVISION/C1011NI6602')

    def test_unsigned_storage_boundaries_and_exact_promotion(self):
        for value in (0,1,2,2**24-1,2**24,2**24+1,2**31-1,2**31,2**31+1,2**32-2,2**32-1):
            result = core.project_frequency(*supplied(value))
            self.assertIs(type(result.updated_cluster[3]), float)
            self.assertEqual(int(result.updated_cluster[3]), value)
            self.assertEqual(result.updated_cluster[32], 4.0)
        for value in (-1,2**32,2**64,True,False,1.0,None,'1'):
            with self.assertRaises(ValueError):
                core.project_frequency(*supplied(value))

    def test_no_inspection_of_unused_or_native_return_content(self):
        result = core.project_frequency(*supplied())
        self.assertIsNotNone(result)
        for status in (False,True):
            for code in (-2147483648,-1,0,1,2147483647):
                args = list(supplied())
                args[4] = core.WriterReturn(Opaque(), {'status':status,'code':code,'source':'supplied'})
                self.assertEqual(core.project_frequency(*args).updated_cluster[3], 17.0)

    def test_all_independent_caller_completion_prefixes(self):
        sinks = ('59714','70290','70253')
        observed = set()
        for size in range(4):
            for prefix in itertools.permutations(sinks, size):
                result = core.project_frequency(*supplied(completion=prefix))
                self.assertIs(result.completed_sinks, prefix)
                self.assertEqual(len(result.local_assignments), 2)
                self.assertEqual(result.updated_cluster[3], 17.0)
                observed.add(prefix)
        self.assertEqual(len(observed), 16)
        self.assertIsNone(core.project_frequency(*supplied()).completed_sinks)
        self.assertEqual(set(core.DEPENDENCIES), {('60452','61621'),('70885','61621'),('68378','61621'),
            ('61621','59714'),('61621','70290'),('61621','70253'),('70272','70253')})
        for invalid in ([],('59714','59714'),('unknown',),('70253',True),('59714','70290','70253','x')):
            with self.assertRaises(ValueError):
                core.project_frequency(*supplied(completion=invalid))

    def test_carrier_domain_and_nonfinite_untouched_slots(self):
        args = list(supplied())
        fields = list(args[0]); fields[0] = float('nan'); fields[1] = float('inf'); fields[2] = -0.0
        args[0] = tuple(fields)
        result = core.project_frequency(*args)
        self.assertIs(result.updated_cluster[0], args[0][0])
        self.assertIs(result.updated_cluster[1], args[0][1])
        self.assertEqual(math.copysign(1.0, result.updated_cluster[2]), -1.0)
        for value in ([],tuple([0.0]*32),tuple([0.0]*34),tuple([0]*33),tuple([False]*33)):
            wrong = list(supplied()); wrong[0] = value
            with self.assertRaises(TypeError):
                core.project_frequency(*wrong)
        for index in (1,3,4):
            wrong = list(supplied()); wrong[index] = None
            with self.assertRaises(TypeError):
                core.project_frequency(*wrong)

    def test_json_exact_adapter_same_core_and_borrowed_opaque_slots(self):
        p = payload()
        before = list(p['local_reads']['60452'])
        result = core.replay_saved_sup_frequency(p)
        expected = [17.0 if i == 3 else 4.0 if i == 32 else before[i] for i in range(33)]
        self.assertEqual(result['projected_cluster'], expected)
        self.assertEqual(p['local_reads']['60452'], before)
        self.assertIs(result['event_returns'], p['event_returns']['70885'])
        self.assertIs(result['writer_call']['supplied_returns'], p['writer_returns']['70253'])
        self.assertIs(result['writer_call']['supplied_native_reference'], p['references']['70272'])
        self.assertIs(result['writer_call']['supplied_effective_unwired_error'], p['unwired_inputs']['70261'])
        self.assertEqual(set(result['local_assignments']), {'59714','70290'})
        self.assertFalse(result['fanout_order_qualified'])
        self.assertFalse(result['writer_success_gates_local_assignments'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertFalse(result['external_calls_executed'])
        for size in range(4):
            for prefix in itertools.permutations(('59714','70290','70253'),size):
                p = payload(completion=list(prefix))
                encoded = core.replay_saved_sup_frequency(p)
                self.assertIs(encoded['completed_sinks'],p['completed_sinks'])
                self.assertEqual(encoded['projected_cluster'],expected)

    def test_json_missing_extra_identity_and_domain_refusals(self):
        for field in payload():
            p = payload();del p[field]
            with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        for path in ('root','local_reads','event_returns','event','references','unwired_inputs','writer_returns','writer'):
            p = payload()
            target = {'root':p,'local_reads':p['local_reads'],'event_returns':p['event_returns'],
                'event':p['event_returns']['70885'],'references':p['references'],
                'unwired_inputs':p['unwired_inputs'],'writer_returns':p['writer_returns'],
                'writer':p['writer_returns']['70253']}[path]
            target['extra'] = None
            with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        for field in ('source_id','event_uid','frame_uid'):
            p = payload();p[field]='wrong'
            with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        for field in ('70890','70893','71466','71471','71474'):
            p=payload();del p['event_returns']['70885'][field]
            with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        for field in ('70258','70264'):
            p=payload();del p['writer_returns']['70253'][field]
            with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        for invalid in (True,-1,2**32,1.0):
            p=payload();p['event_returns']['70885']['71474']=invalid
            with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)

    def test_json_inert_finite_bounded_storage(self):
        for value in (float('nan'),float('inf'),-float('inf'),2**80,'x'*4097,[None]*65):
            p=payload();p['writer_returns']['70253']['70264']=value
            with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        p=payload();p['references']['70272']=Opaque()
        with self.assertRaises(TypeError):core.replay_saved_sup_frequency(p)
        p=payload();nested=None
        for unused in range(10):nested=[nested]
        p['event_returns']['70885']['71471']=nested
        with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        p=payload();p['local_reads']['60452'][0]=float('nan')
        with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)
        p=payload();p['references']['70272']={False:'value'}
        with self.assertRaises(ValueError):core.replay_saved_sup_frequency(p)


if __name__ == '__main__':
    unittest.main()
