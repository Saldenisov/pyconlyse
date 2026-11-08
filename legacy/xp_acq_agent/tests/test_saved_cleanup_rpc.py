"""Signed stateless cleanup replay never invokes live lifecycle runtime."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_cleanup import payload


class UnusableRuntime(object):
    def __getattr__(self,name):
        raise AssertionError('cleanup replay accessed runtime:'+name)


class SavedCleanupRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,data=None):
        data=payload() if data is None else data
        path='/v1/replay/cleanup-frame'
        timestamp,nonce=str(int(time.time())),uuid.uuid4().hex
        return dict(method='POST',path=path,payload=data,timestamp=timestamp,nonce=nonce,
            signature=request_mac(self.key,'RPC/POST',path,timestamp,nonce,json_bytes(data)))

    def test_signed_cleanup_returns_with_explicit_faults_and_no_execution(self):
        request=self.request()
        response=self.endpoint.dispatch(request)
        self.assertEqual(response['status'],200)
        self.assertTrue(response['body']['result']['outputs']['frame_returned'])
        self.assertFalse(response['body']['result']['external_calls_executed'])
        self.assertEqual(response['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(response['body'])))

    def test_signed_nonce_cannot_repeat_and_invalid_mac_refuses(self):
        request=self.request()
        self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)
        request=self.request()
        request['signature']='0'*64
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_missing_seed_is400_without_runtime_access(self):
        data=payload()
        data['psp_error_seed']=None
        response=self.endpoint.dispatch(self.request(data))
        self.assertEqual(response['status'],400)
        self.assertFalse(response['body']['accepted'])


if __name__=='__main__':
    unittest.main()
