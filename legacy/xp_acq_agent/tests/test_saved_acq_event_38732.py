"""Portable new-body tests. {
  "event_uid": "43",
  "field_index_bindings": {
    "38855": 0,
    "38911": 0
  },
  "frame_uid": "38732",
  "leaf_returns": {
    "39076": {
      "39083": true,
      "39087": -10,
      "39122": "first handler source",
      "39125": {
        "code": -10,
        "source": "explicit supplied fault -10",
        "status": true
      },
      "39128": "unused first message"
    },
    "39140": {
      "39147": {
        "opaque": "C6-return"
      },
      "39153": {
        "code": 61,
        "source": "explicit supplied fault 61",
        "status": true
      }
    },
    "39162": {
      "39167": {
        "opaque": "C7-return"
      },
      "39176": {
        "code": 71,
        "source": "explicit supplied fault 71",
        "status": true
      }
    },
    "39266": {
      "39269": 123
    },
    "39861": {
      "39866": {
        "opaque": "DPS-return"
      },
      "39872": {
        "code": 21,
        "source": "explicit supplied fault 21",
        "status": true
      }
    },
    "39885": {
      "39892": {
        "opaque": "EPS-return"
      },
      "39898": {
        "code": 59,
        "source": "explicit supplied fault 59",
        "status": true
      }
    },
    "39904": {
      "39907": false,
      "39910": 11,
      "39922": "second handler source",
      "39925": {
        "code": 11,
        "source": "explicit supplied fault 11",
        "status": true
      },
      "39928": "unused second message"
    },
    "39983": {
      "39985": 456
    }
  },
  "literal_inputs": {
    "38829": 0.0,
    "39475": false,
    "39502": false,
    "42005": false
  },
  "new_value": true,
  "reference_bindings": {
    "38993": {
      "constant_uid": "38993",
      "native_ref": {
        "opaque_supplied_ref": "C6NI6703"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/C6NI6703"
    },
    "39011": {
      "constant_uid": "39011",
      "native_ref": {
        "opaque_supplied_ref": "C7NI6703"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/C7NI6703"
    },
    "39778": {
      "constant_uid": "39778",
      "native_ref": {
        "opaque_supplied_ref": "DPS"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/DPS"
    },
    "39813": {
      "constant_uid": "39813",
      "native_ref": {
        "opaque_supplied_ref": "EPS"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/EPS"
    }
  },
  "schedule": [
    {
      "kind": "step",
      "uid": "38883"
    },
    {
      "kind": "step",
      "uid": "38849"
    },
    {
      "kind": "step",
      "uid": "38841"
    },
    {
      "kind": "step",
      "uid": "38959"
    },
    {
      "kind": "step",
      "uid": "38905"
    },
    {
      "kind": "step",
      "uid": "38897"
    },
    {
      "kind": "step",
      "uid": "38889"
    },
    {
      "kind": "stage_complete",
      "uid": "38812"
    },
    {
      "kind": "step",
      "uid": "39059"
    },
    {
      "kind": "step",
      "uid": "39043"
    },
    {
      "kind": "leaf_call",
      "uid": "39140"
    },
    {
      "kind": "leaf_return",
      "uid": "39140"
    },
    {
      "kind": "leaf_call",
      "uid": "39162"
    },
    {
      "kind": "leaf_return",
      "uid": "39162"
    },
    {
      "kind": "leaf_call",
      "uid": "39076"
    },
    {
      "kind": "leaf_return",
      "uid": "39076"
    },
    {
      "kind": "stage_complete",
      "uid": "38987"
    },
    {
      "kind": "leaf_call",
      "uid": "39266"
    },
    {
      "kind": "leaf_return",
      "uid": "39266"
    },
    {
      "kind": "stage_complete",
      "uid": "39227"
    },
    {
      "kind": "step",
      "uid": "39698"
    },
    {
      "kind": "step",
      "uid": "39675"
    },
    {
      "kind": "step",
      "uid": "39654"
    },
    {
      "kind": "step",
      "uid": "39636"
    },
    {
      "kind": "step",
      "uid": "39579"
    },
    {
      "kind": "step",
      "uid": "39559"
    },
    {
      "kind": "stage_complete",
      "uid": "39387"
    },
    {
      "kind": "step",
      "uid": "39878"
    },
    {
      "kind": "step",
      "uid": "39855"
    },
    {
      "kind": "leaf_call",
      "uid": "39861"
    },
    {
      "kind": "leaf_return",
      "uid": "39861"
    },
    {
      "kind": "leaf_call",
      "uid": "39885"
    },
    {
      "kind": "leaf_return",
      "uid": "39885"
    },
    {
      "kind": "leaf_call",
      "uid": "39904"
    },
    {
      "kind": "leaf_return",
      "uid": "39904"
    },
    {
      "kind": "stage_complete",
      "uid": "39743"
    },
    {
      "kind": "leaf_call",
      "uid": "39983"
    },
    {
      "kind": "leaf_return",
      "uid": "39983"
    },
    {
      "kind": "stage_complete",
      "uid": "39965"
    }
  ],
  "snapshots": {
    "38883": [
      1.25,
      2.25,
      3.25,
      4.25,
      5.25,
      6.25,
      7.25,
      8.25,
      9.25,
      10.25
    ],
    "38959": [
      21.25,
      22.25,
      23.25,
      24.25,
      25.25,
      26.25,
      27.25,
      28.25,
      29.25,
      30.25
    ],
    "39043": [
      101.125,
      102.125,
      103.125,
      104.125,
      105.125,
      106.125,
      107.125,
      108.125,
      109.125,
      110.125
    ],
    "39059": [
      201.125,
      202.125,
      203.125,
      204.125,
      205.125,
      206.125,
      207.125,
      208.125,
      209.125,
      210.125
    ],
    "39636": [
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true
    ],
    "39698": [
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false
    ],
    "39855": [
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false
    ],
    "39878": [
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true
    ]
  },
  "source_id": "APP-00",
  "source_version": "57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5",
  "unwired_inputs": {
    "39097": {
      "opaque": "first void input"
    },
    "39106": -2147483648,
    "39115": "explicit first string",
    "39131": 65535,
    "39150": {
      "code": 1,
      "source": "explicit supplied fault 1",
      "status": true
    },
    "39869": {
      "code": 2,
      "source": "explicit supplied fault 2",
      "status": true
    },
    "39913": {
      "opaque": "second void input"
    },
    "39916": 2147483647,
    "39919": "explicit second string",
    "39931": 0
  }
}
 replaced with exact owned example."""
from __future__ import print_function
import copy,hashlib,json,sys,unittest
from elyse_agent import saved_acq_event_38732 as c
FULL=json.loads(r'''{
  "event_uid": "43",
  "field_index_bindings": {
    "38855": 0,
    "38911": 0
  },
  "frame_uid": "38732",
  "leaf_returns": {
    "39076": {
      "39083": true,
      "39087": -10,
      "39122": "first handler source",
      "39125": {
        "code": -10,
        "source": "explicit supplied fault -10",
        "status": true
      },
      "39128": "unused first message"
    },
    "39140": {
      "39147": {
        "opaque": "C6-return"
      },
      "39153": {
        "code": 61,
        "source": "explicit supplied fault 61",
        "status": true
      }
    },
    "39162": {
      "39167": {
        "opaque": "C7-return"
      },
      "39176": {
        "code": 71,
        "source": "explicit supplied fault 71",
        "status": true
      }
    },
    "39266": {
      "39269": 123
    },
    "39861": {
      "39866": {
        "opaque": "DPS-return"
      },
      "39872": {
        "code": 21,
        "source": "explicit supplied fault 21",
        "status": true
      }
    },
    "39885": {
      "39892": {
        "opaque": "EPS-return"
      },
      "39898": {
        "code": 59,
        "source": "explicit supplied fault 59",
        "status": true
      }
    },
    "39904": {
      "39907": false,
      "39910": 11,
      "39922": "second handler source",
      "39925": {
        "code": 11,
        "source": "explicit supplied fault 11",
        "status": true
      },
      "39928": "unused second message"
    },
    "39983": {
      "39985": 456
    }
  },
  "literal_inputs": {
    "38829": 0.0,
    "39475": false,
    "39502": false,
    "42005": false
  },
  "new_value": true,
  "reference_bindings": {
    "38993": {
      "constant_uid": "38993",
      "native_ref": {
        "opaque_supplied_ref": "C6NI6703"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/C6NI6703"
    },
    "39011": {
      "constant_uid": "39011",
      "native_ref": {
        "opaque_supplied_ref": "C7NI6703"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/C7NI6703"
    },
    "39778": {
      "constant_uid": "39778",
      "native_ref": {
        "opaque_supplied_ref": "DPS"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/DPS"
    },
    "39813": {
      "constant_uid": "39813",
      "native_ref": {
        "opaque_supplied_ref": "EPS"
      },
      "saved_uri": "ni.var.psp://10.20.30.2/SUPERVISION/EPS"
    }
  },
  "schedule": [
    {
      "kind": "step",
      "uid": "38883"
    },
    {
      "kind": "step",
      "uid": "38849"
    },
    {
      "kind": "step",
      "uid": "38841"
    },
    {
      "kind": "step",
      "uid": "38959"
    },
    {
      "kind": "step",
      "uid": "38905"
    },
    {
      "kind": "step",
      "uid": "38897"
    },
    {
      "kind": "step",
      "uid": "38889"
    },
    {
      "kind": "stage_complete",
      "uid": "38812"
    },
    {
      "kind": "step",
      "uid": "39059"
    },
    {
      "kind": "step",
      "uid": "39043"
    },
    {
      "kind": "leaf_call",
      "uid": "39140"
    },
    {
      "kind": "leaf_return",
      "uid": "39140"
    },
    {
      "kind": "leaf_call",
      "uid": "39162"
    },
    {
      "kind": "leaf_return",
      "uid": "39162"
    },
    {
      "kind": "leaf_call",
      "uid": "39076"
    },
    {
      "kind": "leaf_return",
      "uid": "39076"
    },
    {
      "kind": "stage_complete",
      "uid": "38987"
    },
    {
      "kind": "leaf_call",
      "uid": "39266"
    },
    {
      "kind": "leaf_return",
      "uid": "39266"
    },
    {
      "kind": "stage_complete",
      "uid": "39227"
    },
    {
      "kind": "step",
      "uid": "39698"
    },
    {
      "kind": "step",
      "uid": "39675"
    },
    {
      "kind": "step",
      "uid": "39654"
    },
    {
      "kind": "step",
      "uid": "39636"
    },
    {
      "kind": "step",
      "uid": "39579"
    },
    {
      "kind": "step",
      "uid": "39559"
    },
    {
      "kind": "stage_complete",
      "uid": "39387"
    },
    {
      "kind": "step",
      "uid": "39878"
    },
    {
      "kind": "step",
      "uid": "39855"
    },
    {
      "kind": "leaf_call",
      "uid": "39861"
    },
    {
      "kind": "leaf_return",
      "uid": "39861"
    },
    {
      "kind": "leaf_call",
      "uid": "39885"
    },
    {
      "kind": "leaf_return",
      "uid": "39885"
    },
    {
      "kind": "leaf_call",
      "uid": "39904"
    },
    {
      "kind": "leaf_return",
      "uid": "39904"
    },
    {
      "kind": "stage_complete",
      "uid": "39743"
    },
    {
      "kind": "leaf_call",
      "uid": "39983"
    },
    {
      "kind": "leaf_return",
      "uid": "39983"
    },
    {
      "kind": "stage_complete",
      "uid": "39965"
    }
  ],
  "snapshots": {
    "38883": [
      1.25,
      2.25,
      3.25,
      4.25,
      5.25,
      6.25,
      7.25,
      8.25,
      9.25,
      10.25
    ],
    "38959": [
      21.25,
      22.25,
      23.25,
      24.25,
      25.25,
      26.25,
      27.25,
      28.25,
      29.25,
      30.25
    ],
    "39043": [
      101.125,
      102.125,
      103.125,
      104.125,
      105.125,
      106.125,
      107.125,
      108.125,
      109.125,
      110.125
    ],
    "39059": [
      201.125,
      202.125,
      203.125,
      204.125,
      205.125,
      206.125,
      207.125,
      208.125,
      209.125,
      210.125
    ],
    "39636": [
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true
    ],
    "39698": [
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false
    ],
    "39855": [
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false,
      true,
      false
    ],
    "39878": [
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true,
      false,
      false,
      true
    ]
  },
  "source_id": "APP-00",
  "source_version": "57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5",
  "unwired_inputs": {
    "39097": {
      "opaque": "first void input"
    },
    "39106": -2147483648,
    "39115": "explicit first string",
    "39131": 65535,
    "39150": {
      "code": 1,
      "source": "explicit supplied fault 1",
      "status": true
    },
    "39869": {
      "code": 2,
      "source": "explicit supplied fault 2",
      "status": true
    },
    "39913": {
      "opaque": "second void input"
    },
    "39916": 2147483647,
    "39919": "explicit second string",
    "39931": 0
  }
}
''')
COUNTS={'accepted':0,'refused':0,'checks':0};WITNESS=[]
def ck(condition):
 COUNTS['checks']+=1
 if not condition:raise AssertionError('fresh source expectation failed')
def pure(p):
 classes={'step':c.Step,'leaf_call':c.LeafCall,'leaf_return':c.LeafReturn,'stage_complete':c.StageComplete};tokens=tuple(classes[r['kind']](r['uid'])for r in p['schedule'])
 def e(v):return c.ErrorValue(v['status'],v['code'],v['source'])
 returns=copy.deepcopy(p['leaf_returns']);unwired=copy.deepcopy(p['unwired_inputs'])
 for faces in returns.values():
  for face,v in list(faces.items()):
   if type(v)is dict and set(v)==set(('status','code','source')):faces[face]=e(v)
 for face in ('39150','39869'):
  if face in unwired:unwired[face]=e(unwired[face])
 return tokens,dict(snapshots={u:tuple(v)for u,v in p['snapshots'].items()},leaf_returns=returns,unwired_inputs=unwired,reference_bindings=copy.deepcopy(p['reference_bindings']),field_index_bindings=copy.deepcopy(p['field_index_bindings']),literal_inputs=copy.deepcopy(p['literal_inputs']))
def expected(snapshot,fields):
 out=list(snapshot)
 for i,v in fields:out[i]=v
 return tuple(out)
def accepted(p):
 out=c.replay_saved_acq_event_38732(p);COUNTS['accepted']+=1;WITNESS.append(('accepted',len(p['schedule'])if p['schedule']is not None else -1,out['selected_body_completed']));return out
def refuse(p):
 try:c.replay_saved_acq_event_38732(p)
 except(ValueError,TypeError,KeyError):COUNTS['refused']+=1;return
 raise AssertionError('invalid fresh boundary admitted')
class Poison:
 def __iter__(self):raise AssertionError('unselected input accessed')
 def __getitem__(self,k):raise AssertionError('unselected input accessed')
 def __len__(self):raise AssertionError('unselected input accessed')
class Original38732(unittest.TestCase):
 def test_complete_source_projection_and_identity(self):
  tokens,kw=pure(FULL);o=c.replay_event(True,tokens,**kw);COUNTS['accepted']+=1
  ck(o['selected_body_completed']and o['completed_stages']==['38812','38987','39227','39387','39743','39965'])
  writes={r['node_uid']:r for r in o['writes']}
  oracle={'38841':expected(kw['snapshots']['38883'],[(i,0.0)for i in(0,1,2,3,4,5,6,7,9)]),'38897':expected(kw['snapshots']['38959'],[(i,0.0)for i in(0,1,3,4,6,7,8,9)]),'38889':True,'39559':expected(kw['snapshots']['39636'],[(59,False),(64,False),(61,True)]),'39654':expected(kw['snapshots']['39698'],[(21,False)])}
  ck(set(writes)==set(oracle))
  for u,v in oracle.items():ck(writes[u]['value']==v)
  ck(writes['38841']['value'][8]==9.25);ck(writes['38897']['value'][2]==23.25 and writes['38897']['value'][5]==26.25)
  calls={r['node_uid']:r['input_ports']for r in o['leaf_calls']}
  for face,read,leaf in(('39158','39043','39140'),('39180','39059','39162'),('39875','39855','39861'),('39901','39878','39885')):ck(calls[leaf][face]is kw['snapshots'][read])
  ck(calls['39140']['39158']!=writes['38841']['value']);ck(calls['39162']['39180']!=writes['38897']['value'])
  for prod,out,consumer,face in(('39140','39153','39162','39171'),('39162','39176','39076','39134'),('39861','39872','39885','39895'),('39885','39898','39904','39934')):ck(calls[consumer][face]is kw['leaf_returns'][prod][out])
  ck(calls['39140']['39150']is kw['unwired_inputs']['39150']);ck(calls['39861']['39869']is kw['unwired_inputs']['39869'])
  for constant,leaf,face in(('38993','39140','39144'),('39011','39162','39164'),('39778','39861','39863'),('39813','39885','39888')):ck(calls[leaf][face]is kw['reference_bindings'][constant]['native_ref'])
  ck(calls['39266']=={'39273':1000});ck(calls['39983']=={'39988':200})
  ck(all(r['success_does_not_gate_stage']for r in o['leaf_returns']))
  for k in c.LIMITS:ck(o[k]is False)
  ck(len(o['leaf_calls'])==8 and len(o['leaf_returns'])==8);ck(o['event_data_unconsumed_ports']==('38753','38756','38759','38762'))
  for uid in ('38883','38959','39043','39059','39636','39698','39855','39878'):
   row=next(r for r in o['log']if r['kind']=='local_read'and r['node_uid']==uid);ck(row['value']is kw['snapshots'][uid])
  ck(c._json_tree(o)==accepted(FULL))
 def test_independent_finite_snapshots_and_preserved_fields(self):
  for seed in range(12):
   p=copy.deepcopy(FULL)
   for uid,shift in(('38883',-90),('38959',30),('39043',1000),('39059',2000)):p['snapshots'][uid]=[float(shift+seed+i+.5)for i in range(10)]
   p['snapshots']['39636']=[(i+seed)%3==0 for i in range(77)];p['snapshots']['39698']=[(i+seed)%2==0 for i in range(29)]
   p['snapshots']['39878']=[(i+seed)%5==0 for i in range(77)];p['snapshots']['39855']=[(i+seed)%7==0 for i in range(29)]
   o=accepted(p);w={r['node_uid']:r['value']for r in o['writes']};ck(w['38841']==list(expected(p['snapshots']['38883'],[(i,0.0)for i in(0,1,2,3,4,5,6,7,9)])));ck(w['38897']==list(expected(p['snapshots']['38959'],[(i,0.0)for i in(0,1,3,4,6,7,8,9)])));ck(w['39559']==list(expected(p['snapshots']['39636'],[(59,False),(64,False),(61,True)])));ck(w['39654']==list(expected(p['snapshots']['39698'],[(21,False)])))
 def test_partial_prefixes_and_alternate_valid_orders(self):
  schedules=[copy.deepcopy(FULL['schedule'])]
  q=copy.deepcopy(FULL['schedule']);q[:7]=[dict(kind='step',uid=u)for u in('38889','38959','38905','38897','38883','38849','38841')];q[8:10]=list(reversed(q[8:10]));q[20:26]=[dict(kind='step',uid=u)for u in('39636','39579','39559','39698','39675','39654')];schedules.append(q)
  for schedule in schedules:
   for length in range(40):
    p=copy.deepcopy(FULL);p['schedule']=schedule[:length];o=accepted(p);ck(o['selected_body_completed']is(length==39))
    joins=[r['uid']for r in p['schedule']if r['kind']=='stage_complete'];ck(o['completed_stages']==joins)
    for call in o['leaf_calls']:
     if call['node_uid']in o['pending_leaf_uids']:ck(call['node_uid']not in [r['node_uid']for r in o['leaf_returns']])
 def test_inflight_unused_returns_and_false_nonaccess(self):
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:11];p['leaf_returns']={};o=accepted(p);ck(o['pending_leaf_uids']==['39140']and not o['selected_body_completed'])
  bad=Poison();o=c.replay_event(False,bad,snapshots=bad,leaf_returns=bad,unwired_inputs=bad,reference_bindings=bad,field_index_bindings=bad,literal_inputs=bad);COUNTS['accepted']+=1;ck(not o['leaf_calls']and not o['writes']and o['selected_case_frame']=='38786')
  p=copy.deepcopy(FULL);p.update(new_value=False,schedule=bad,snapshots=bad,leaf_returns=bad,unwired_inputs=bad,reference_bindings=bad,field_index_bindings=bad,literal_inputs=bad);o=c.replay_saved_acq_event_38732(p);COUNTS['accepted']+=1;ck(o['selected_body_completed'])
  p=copy.deepcopy(FULL);p['schedule']=[dict(kind='step',uid='38889')];p.update(field_index_bindings={},literal_inputs={'38829':0.0},leaf_returns={},reference_bindings={},unwired_inputs={},snapshots={});o=accepted(p);ck(len(o['writes'])==1)
 def test_invalid_indices_literal_storage_and_numeric_domain(self):
  for face in('38855','38911'):
   for value in(None,False,True,-1,1,0.0,'0'):
    p=copy.deepcopy(FULL);p['field_index_bindings'][face]=value;refuse(p)
   p=copy.deepcopy(FULL);del p['field_index_bindings'][face];refuse(p)
  for uid in('38829','39475','39502','42005'):
   p=copy.deepcopy(FULL);del p['literal_inputs'][uid];refuse(p)
   for value in([0,-0.0,1.0,float('nan'),float('inf')]if uid=='38829'else[0,True,None]):
    p=copy.deepcopy(FULL);p['literal_inputs'][uid]=value;refuse(p)
  for uid in('38883','38959','39043','39059'):
   for value in(True,0,1,float('nan'),float('inf'),None):
    p=copy.deepcopy(FULL);p['snapshots'][uid][8]=value;refuse(p)
   p=copy.deepcopy(FULL);p['snapshots'][uid].pop();refuse(p)
  for uid in('39636','39698','39855','39878'):
   p=copy.deepcopy(FULL);p['snapshots'][uid][0]=1;refuse(p)
 def test_invalid_exact_identity_ports_unwired_and_schedules(self):
  for key,value in(('source_id','APP-13'),('source_version','0'*64),('event_uid','44'),('frame_uid','48846'),('new_value',1)):
   p=copy.deepcopy(FULL);p[key]=value;refuse(p)
  for key in FULL:
   p=copy.deepcopy(FULL);del p[key];refuse(p)
  p=copy.deepcopy(FULL);p['execute']=True;refuse(p)
  for face,value in(('39106',True),('39131',65536),('39916',2147483648),('39919',0)):
   p=copy.deepcopy(FULL);p['unwired_inputs'][face]=value;refuse(p)
  for uid,face,value in(('39266','39269',-1),('39076','39087',False),('39904','39907',1)):
   p=copy.deepcopy(FULL);p['leaf_returns'][uid][face]=value;refuse(p)
  for uid,face in(('39140','39153'),('39904','39925')):
   p=copy.deepcopy(FULL);del p['leaf_returns'][uid][face];refuse(p)
  for uid in('38993','39011','39778','39813'):
   p=copy.deepcopy(FULL);p['reference_bindings'][uid]['saved_uri']='wrong';refuse(p)
  for rows in([[dict(kind='step',uid='38849')],[dict(kind='leaf_call',uid='39140')],[dict(kind='stage_complete',uid='38812')],[dict(kind='leaf_return',uid='39266')],FULL['schedule']+[dict(kind='step',uid='38889')],[dict(kind='step',uid='foreign')],[dict(kind='step',uid='38889')]*2]):
   p=copy.deepcopy(FULL);p['schedule']=rows;refuse(p)
  p=copy.deepcopy(FULL);p['schedule'][12],p['schedule'][11]=p['schedule'][11],p['schedule'][12];refuse(p)
if __name__=='__main__':
 target=sys.argv[1]if len(sys.argv)>1 else None
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Original38732);result=unittest.TextTestRunner(verbosity=2).run(suite)
 receipt=dict(status='PASS'if result.wasSuccessful()else'FAIL',methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest().upper(),python_version=sys.version,executable=sys.executable,new_body_only=True,source_execution=False,native_execution=False,whole_event_equivalence=False)
 if target:
  with open(target,'w',encoding='utf-8')as f:f.write(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 print(json.dumps(receipt,sort_keys=True));sys.exit(0 if result.wasSuccessful()else 1)
