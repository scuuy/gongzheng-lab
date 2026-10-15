"""HTTP boundary checks without native solver dependencies."""
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from gongzheng.server import Handler

class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def request(self,method,path,body=None,headers=None):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        c.request(method,path,body,headers or {});r=c.getresponse();status=r.status;data=r.read();c.close();return status,data

    def test_artifact_path_traversal_denied(self):
        self.assertEqual(self.request('GET','/artifacts/../../LICENSE')[0],403)
        self.assertEqual(self.request('GET','/../LICENSE')[0],403)

    def test_foreign_origin_cannot_start_run(self):
        self.assertEqual(self.request('POST','/api/run','{}',{'Origin':'https://other.example'})[0],403)

    def test_non_object_and_unhashable_values_rejected(self):
        for body in ['[]','null','{"case":[]}','{"case":"normal","action":{}}']:
            with self.subTest(body=body):
                self.assertEqual(self.request('POST','/api/run',body)[0],400)

    def test_arbitrary_commands_or_unknown_cases_rejected(self):
        self.assertEqual(self.request('POST','/api/run',json.dumps({'case':'normal','action':'shell'}))[0],400)
        self.assertEqual(self.request('GET','/api/saved?case=unknown')[0],400)
