"""Recorded replay payloads for test_saved_acq_event_38732.py."""

import json

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
