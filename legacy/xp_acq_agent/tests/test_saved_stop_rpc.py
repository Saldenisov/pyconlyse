"""Signed stop replay remains stateless and never enters live runtime."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_requests_rpc import UnusableRuntime
from test_saved_stop import payload


class StopRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum';self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,data):
        path='/v1/replay/stop-trace';timestamp=str(int(time.time()));nonce=uuid.uuid4().hex
        return dict(method='POST',path=path,payload=data,timestamp=timestamp,nonce=nonce,
            signature=request_mac(self.key,'RPC/POST',path,timestamp,nonce,json_bytes(data)))

    def test_signed_trace_and_reset(self):
        for facet in ('runtime_trace','reset'):
            request=self.request(payload(facet));result=self.endpoint.dispatch(request)
            self.assertEqual(result['status'],200);self.assertFalse(result['body']['result']['physical_stop_qualified'])
            self.assertEqual(result['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(result['body'])))

    def test_nonce_reuse_refused(self):
        request=self.request(payload());self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_invalid_join_refused(self):
        data=payload();data['schedule']=[dict(kind='outer_tcp_read')]
        self.assertEqual(self.endpoint.dispatch(self.request(data))['status'],400)


if __name__=='__main__':unittest.main()
