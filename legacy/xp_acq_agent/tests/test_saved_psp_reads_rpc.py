"""Signed replay does not access live runtime or native PSP."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_requests_rpc import UnusableRuntime
from test_saved_psp_reads import payload


class SavedPspReadRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,data):
        path='/v1/replay/psp-read-frame'
        timestamp,nonce=str(int(time.time())),uuid.uuid4().hex
        return dict(method='POST',path=path,payload=data,timestamp=timestamp,nonce=nonce,
            signature=request_mac(self.key,'RPC/POST',path,timestamp,nonce,json_bytes(data)))

    def test_signed_full_frame_is_inert(self):
        request=self.request(payload())
        result=self.endpoint.dispatch(request)
        self.assertEqual(result['status'],200)
        self.assertFalse(result['body']['result']['psp_delivery_qualified'])
        self.assertEqual(result['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(result['body'])))

    def test_repeated_nonce_refuses(self):
        request=self.request(payload())
        self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_partial_frame_refuses_without_runtime(self):
        data=payload()
        data['frame_returned']=False
        self.assertEqual(self.endpoint.dispatch(self.request(data))['status'],400)


if __name__=='__main__':
    unittest.main()
