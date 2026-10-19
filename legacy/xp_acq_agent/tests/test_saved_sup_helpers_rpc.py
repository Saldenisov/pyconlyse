"""Signed stateless SUP pure-kernel route never accesses agent runtime."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_card_replay_rpc import UnusableRuntime
from test_saved_sup_helpers import fixture


class SupHelperRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,payload):
        path='/v1/replay/supervision-helper';stamp=str(int(time.time()));nonce=uuid.uuid4().hex
        return dict(method='POST',path=path,payload=payload,timestamp=stamp,nonce=nonce,
                    signature=request_mac(self.key,'RPC/POST',path,stamp,nonce,json_bytes(payload)))

    def test_three_signed_source_kernels(self):
        for sid in ('APP-19','APP-21','APP-22'):
            request=self.request(fixture(sid));response=self.endpoint.dispatch(request)
            self.assertEqual(response['status'],200)
            self.assertFalse(response['body']['hardware_writes'])
            self.assertEqual(response['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(response['body'])))

    def test_authentication_before_validation_and_nonce(self):
        request=self.request(fixture());self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)
        request=self.request({'wrong':'shape'});request['signature']='0'*64
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)
        self.assertEqual(self.endpoint.dispatch(self.request(dict(source_id='APP-15')))['status'],400)


if __name__=='__main__':unittest.main()
