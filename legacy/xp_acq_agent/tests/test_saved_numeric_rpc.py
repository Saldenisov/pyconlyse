import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_requests_rpc import UnusableRuntime
from test_saved_numeric import payload


class NumericRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum';self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,data):
        path='/v1/replay/numeric-conversion';timestamp=str(int(time.time()));nonce=uuid.uuid4().hex
        return dict(method='POST',path=path,payload=data,timestamp=timestamp,nonce=nonce,
                    signature=request_mac(self.key,'RPC/POST',path,timestamp,nonce,json_bytes(data)))

    def test_signed_pure_replays(self):
        for operation in ('parse','format'):
            request=self.request(payload(operation));result=self.endpoint.dispatch(request)
            self.assertEqual(result['status'],200);self.assertFalse(result['body']['execution_allowed'])
            self.assertFalse(result['body']['hardware_writes'])
            self.assertEqual(result['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(result['body'])))

    def test_nonce_reuse(self):
        request=self.request(payload());self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_profile_required(self):
        data=payload();data['decimal_separator']=None
        self.assertEqual(self.endpoint.dispatch(self.request(data))['status'],400)


if __name__=='__main__':unittest.main()
