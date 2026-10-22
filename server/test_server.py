import unittest,tempfile,threading,json,urllib.request,urllib.error,os,sqlite3
import server
class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();server.DB=os.path.join(cls.temp.name,'test.sqlite');server.initialize();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=cls.http.serve_forever,daemon=True).start();cls.url='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
 def request(self,path,method='GET',data=None,token=None):
  req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})},method=method)
  try:
   with urllib.request.urlopen(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_lifecycle_isolation_conflicts(self):
  status,a=self.request('/auth/register','POST',{'email':'a@example.test','password':'a-strong-test-password'});self.assertEqual(status,200)
  status,b=self.request('/auth/register','POST',{'email':'b@example.test','password':'another-test-password'});self.assertEqual(status,200)
  self.assertEqual(self.request('/state')[0],401)
  state={'version':1,'accounts':[{'id':'a','name':'Conta','opening':0}],'transactions':[],'goals':[],'cards':[],'purchases':[]}
  self.assertEqual(self.request('/state','PUT',{'revision':0,'state':state},a['token'])[0],200)
  self.assertIsNone(self.request('/state',token=b['token'])[1]['state'])
  self.assertEqual(self.request('/state',token=a['token'])[1]['state'],state)
  self.assertEqual(self.request('/state','PUT',{'revision':0,'state':state},a['token'])[0],409)
  self.assertEqual(self.request('/state','PUT',{'revision':1,'state':{'version':1}},a['token'])[0],400)
  self.assertEqual(self.request('/auth/login','POST',{'email':'a@example.test','password':'wrong-password-test'})[0],401)
  self.assertEqual(self.request('/auth/logout','POST',{},a['token'])[0],200)
  self.assertEqual(self.request('/state',token=a['token'])[0],401)
  with sqlite3.connect(server.DB) as c:
   self.assertNotEqual(c.execute('SELECT password FROM users LIMIT 1').fetchone()[0],b'a-strong-test-password')
if __name__=='__main__':unittest.main()
