"""Adapter checks preserve exact source shape, strict boundaries and purity."""
import copy
import json
import unittest
from elyse_agent.saved_sup_replay import replay_saved_sup_helpers


def fixture(sid='APP-19'):
    if sid=='APP-19':
        return dict(source_id=sid,buffer_x=[[10,20],[30,40]],buffer_y=[[1],[3]],extracted_row=[7,8],
                    extracted_column=[9],integral_x=1001.0,integral_y=1000.0,average=2,iteration=3)
    count=11 if sid=='APP-21' else 9
    return dict(source_id=sid,rows=[[True,False,True,False,True,0.0,1.0,True,False,True,False] for _ in range(count)],threshold=0.5)


class SupHelpersTests(unittest.TestCase):
    def test_profile_threshold_row_and_mean(self):
        data=fixture();before=copy.deepcopy(data);value=replay_saved_sup_helpers(data)
        self.assertEqual(value['outputs'],dict(buffer_x=((10,20),(7,8)),buffer_y=((1,),(3,)),
             mean_x=(8.5,14.0),mean_y=(2.0,),gate_x=True,gate_y=False,slot=1))
        self.assertEqual(data,before)
        self.assertFalse(value['image_processing_qualified'])
        self.assertFalse(value['whole_VI_equivalence'])

    def test_all_eleven_fields_and_forced_false(self):
        for sid in ('APP-21','APP-22'):
            data=fixture(sid);result=replay_saved_sup_helpers(data)['outputs']['rows']
            for i,row in enumerate(result):
                self.assertEqual(len(row),11)
                self.assertEqual(row[2],False if sid=='APP-21' and i==2 else True)
                for field in (0,1,3,4,5,6,7,8,9,10):self.assertIs(row[field],data['rows'][i][field])

    def test_json_roundtrips_and_domain_refusals(self):
        for sid in ('APP-19','APP-21','APP-22'):
            result=replay_saved_sup_helpers(json.loads(json.dumps(fixture(sid))))
            self.assertEqual(json.loads(json.dumps(result))['source_id'],sid)
        for field,value in [('average',0),('iteration',True),('extracted_row',[256,1]),('extra',0)]:
            data=fixture();data[field]=value
            with self.assertRaises((ValueError,TypeError)):replay_saved_sup_helpers(data)
        data=fixture('APP-21');data['rows'][0]=data['rows'][0][:7]
        with self.assertRaises(ValueError):replay_saved_sup_helpers(data)
        with self.assertRaises(ValueError):replay_saved_sup_helpers(dict(source_id='APP-15'))


if __name__=='__main__':unittest.main()
