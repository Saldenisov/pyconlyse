"""Signed card replay authenticates before validation andnever accesses runtime."""
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes,request_mac,response_mac
from test_saved_card_replay import fixture


class UnusableRuntime(object):
    def __getattr__(self,name):raise AssertionError('Unexpected runtime access: '+name)


class CardRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'software-test-key-32-bytes-minimum'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,payload):
        path='/v1/replay/card-initializer';stamp=str(int(time.time()));nonce=uuid.uuid4().hex
        return dict(method='POST',path=path,payload=payload,timestamp=stamp,nonce=nonce,
                    signature=request_mac(self.key,'RPC/POST',path,stamp,nonce,json_bytes(payload)))

    def test_all_three_signed_source_bodies(self):
        for sid in ['APP-01','APP-02','APP-04']:
            request=self.request(fixture(sid,11));response=self.endpoint.dispatch(request)
            self.assertEqual(response['status'],200)
            self.assertFalse(response['body']['hardware_writes'])
            self.assertEqual(response['signature'],response_mac(self.key,'RPC/POST',request['path'],request['nonce'],200,json_bytes(response['body'])))

    def test_authentication_and_nonce(self):
        request=self.request(fixture());self.assertEqual(self.endpoint.dispatch(request)['status'],200)
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)
        request=self.request({'invalid':'payload'});request['signature']='0'*64
        self.assertEqual(self.endpoint.dispatch(request)['status'],401)

    def test_body_refuses_after_authentication(self):
        data=fixture('APP-02');data['returns'][-1]=dict(task='invented',error=data['returns'][-1])
        self.assertEqual(self.endpoint.dispatch(self.request(data))['status'],400)


if __name__=='__main__':unittest.main()
