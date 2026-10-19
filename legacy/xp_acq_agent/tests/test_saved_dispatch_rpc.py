"""Signed stateless facets have no route into live runtime."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_requests_rpc import UnusableRuntime
from test_saved_dispatch import payload


class SavedDispatchRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,data):
        path='/v1/replay/dispatch-facet'
        timestamp,nonce=str(int(time.time())),uuid.uuid4().hex
        return dict(method='POST',path=path,payload=data,timestamp=timestamp,nonce=nonce,
            signature=request_mac(self.key,'RPC/POST',path,timestamp,nonce,json_bytes(data)))

    def test_all_facets_sign_response_without_runtime(self):
        for facet,event in (('dispatch',None),('reset',3),('publication',3)):
            request=self.request(payload(facet,event))
            result=self.endpoint.dispatch(request)
            self.assertEqual(result['status'],200)
            self.assertFalse(result['body']['result']['external_calls_executed'])
            self.assertEqual(result['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(result['body'])))

    def test_repeated_nonce_is_refused(self):
        request=self.request(payload())
        self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_saved_tail_default_signs_false_action_without_runtime(self):
        for index in range(24,29):
            data=payload()
            data['dps'][index]=True
            request=self.request(data)
            result=self.endpoint.dispatch(request)
            self.assertEqual(result['status'],200)
            outputs=result['body']['result']['outputs']
            self.assertEqual(outputs['state'],'SAVED_DEFAULT')
            self.assertEqual(outputs['case_selector'],index+1)
            self.assertIs(outputs['action_assignment'],False)
            self.assertEqual(outputs['property_assignments'],[])
            self.assertIsNone(outputs['registered_event'])
            self.assertEqual(result['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(result['body'])))

    def test_bad_scalar_domain_refuses_without_runtime(self):
        data=payload()
        data['dps'][0]=1
        self.assertEqual(self.endpoint.dispatch(self.request(data))['status'],400)


if __name__=='__main__':
    unittest.main()
