"""Signed stateless request-facet replay cannot access live runtime."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_requests import payload


class UnusableRuntime(object):
    def __getattr__(self,name):
        raise AssertionError('request replay accessed runtime:'+name)


class SavedRequestRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,data=None):
        data=payload() if data is None else data
        path='/v1/replay/request-facet'
        timestamp,nonce=str(int(time.time())),uuid.uuid4().hex
        return dict(method='POST',path=path,payload=data,timestamp=timestamp,nonce=nonce,
           signature=request_mac(self.key,'RPC/POST',path,timestamp,nonce,json_bytes(data)))

    def test_signed_response_uses_shared_body_with_independent_base(self):
        request=self.request()
        response=self.endpoint.dispatch(request)
        self.assertEqual(response['status'],200)
        self.assertFalse(response['body']['result']['external_calls_executed'])
        self.assertTrue(response['body']['result']['outputs']['projected_dps'][0])
        self.assertEqual(response['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(response['body'])))

    def test_nonce_repeat_and_bad_mac_refuse(self):
        request=self.request()
        self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)
        request=self.request()
        request['signature']='0'*64
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_wrong_scalar_domain400_without_runtime_access(self):
        data=payload()
        data['commands'][0]=1
        response=self.endpoint.dispatch(self.request(data))
        self.assertEqual(response['status'],400)
        self.assertFalse(response['body']['accepted'])


if __name__=='__main__':
    unittest.main()
