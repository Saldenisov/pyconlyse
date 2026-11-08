"""Signed stateless supplied-return replay never touches live runtime."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_requests_rpc import UnusableRuntime
from test_saved_sup_reads import payload


class SupReadsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,data):
        path='/v1/replay/supervision-read-slice';timestamp=str(int(time.time()));nonce=uuid.uuid4().hex
        return dict(method='POST',path=path,payload=data,timestamp=timestamp,nonce=nonce,
            signature=request_mac(self.key,'RPC/POST',path,timestamp,nonce,json_bytes(data)))

    def test_signed_chain_and_independent_slice(self):
        for independent in (False,True):
            request=self.request(payload(independent));result=self.endpoint.dispatch(request)
            self.assertEqual(result['status'],200)
            self.assertFalse(result['body']['result']['native_runtime_equivalence'])
            self.assertEqual(result['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(result['body'])))

    def test_nonce_replay_refused(self):
        request=self.request(payload())
        self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_partial_frame_refused(self):
        data=payload();data['frames_returned']=[]
        self.assertEqual(self.endpoint.dispatch(self.request(data))['status'],400)


if __name__=='__main__':unittest.main()
