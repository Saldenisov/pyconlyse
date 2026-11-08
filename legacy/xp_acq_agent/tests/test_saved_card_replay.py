"""Adapter expectations retain only source outputs; no hardware runtime."""
import copy
import unittest
from elyse_agent.saved_card_replay import replay_saved_card_init


def fixture(sid='APP-01',fault=None,seed=None):
    count=136 if sid=='APP-02' else 12
    returns=[dict(task='r'+str(i),error=dict(status=i==fault,code=i-50,source='returned'+str(i))) for i in range(count)]
    if sid=='APP-02':returns.append(dict(status=True,code=999,source='discarded handler'))
    value=dict(source_id=sid,returns=returns,error_in=dict(status=True,code=-1,source='input'))
    if sid!='APP-01':value.update(rate_hz=5000.0,samples_per_channel=10,public_error_seed=seed)
    if sid=='APP-02':value.update(trigger_c1='/1/PFI0',trigger_c2='/2/PFI0')
    return value


class SavedCardReplayTests(unittest.TestCase):
    def test_source_outputs_and_inputs_unchanged(self):
        for sid,indices in [('APP-01',[1,3,5,7,9,11]),('APP-02',[67,135]),('APP-04',[11])]:
            for fault in [None,0,5,11]:
                data=fixture(sid,fault);before=copy.deepcopy(data)
                result=replay_saved_card_init(data)
                self.assertEqual(result['outputs']['tasks'],['r'+str(i) for i in indices])
                self.assertEqual(result['outputs']['internal_error'],data['returns'][indices[-1]]['error'])
                self.assertEqual(result['outputs']['public_error'],data['returns'][11]['error'] if sid=='APP-01' else dict(kind='unwritten_public_indicator_unknown'))
                self.assertEqual(data,before)
                self.assertFalse(result['native_execution'])

    def test_public_seed_and_unused_handler_are_separate(self):
        seed=dict(status=True,code=17,source='explicit retained seed')
        data=fixture('APP-02',135,seed)
        result=replay_saved_card_init(data)
        self.assertEqual(result['outputs']['public_error'],seed)
        self.assertEqual(result['outputs']['internal_error']['source'],'returned135')
        self.assertEqual(result['call_bindings'],137)

    def test_exact_representation_refuses(self):
        changes=[lambda d:d.update(source_id='APP-03'),lambda d:d.update(extra=True),
                 lambda d:d.update(returns=d['returns'][:-1]),lambda d:d['returns'][0]['error'].update(status=1),
                 lambda d:d['returns'][0].update(task=''),lambda d:d['error_in'].update(code=2**31)]
        for mutate in changes:
            data=fixture();mutate(data)
            with self.assertRaises((TypeError,ValueError)):replay_saved_card_init(data)
        for field,value in [('rate_hz',5000),('samples_per_channel',-1),('samples_per_channel',True)]:
            data=fixture('APP-02');data[field]=value
            with self.assertRaises((TypeError,ValueError)):replay_saved_card_init(data)


if __name__=='__main__':unittest.main()
