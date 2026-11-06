import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
import app


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        app.DB_PATH = Path(self.temp.name) / 'test.db'
        app.SESSIONS.clear()
        app.initialize()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.call('setup', {'username':'owner','password':'a-login-password','clear_password':'a-clearing-password'})
        self.call('login', {'username':'owner','password':'a-login-password'})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, data=None, expected=200):
        req=urllib.request.Request(self.base+'/api/'+path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type':'application/json'})
        try:
            response=self.client.open(req)
        except urllib.error.HTTPError as error:
            response=error
        self.assertEqual(response.status,expected,response.read().decode() if response.status!=expected else '')
        return json.load(response)

    def seed(self):
        self.call('parties',{'name':'Customer A','kind':'customer'})
        self.call('parties',{'name':'Supplier B','kind':'supplier'})
        self.call('products',{'name':'Widget','sku':'W-1','price':'100','cost':'60','stock':'10'})

    def document(self, kind='invoice', qty='2', price='100', tax='20', expected=200):
        return self.call('documents',{'kind':kind,'party_id':2 if kind=='purchase_order' else 1,'issued':'2026-01-01','due':'2026-02-01','tax':tax,'items':[{'product_id':1,'qty':qty,'price':price}]},expected)

    def test_invoice_payment_costs_and_security(self):
        self.seed()
        self.document()
        state=self.call('state');doc=state['documents'][0]
        self.assertEqual(doc['number'],'INV-00001')
        self.assertEqual(doc['total'],22000)
        self.assertEqual(doc['cost'],12000)
        self.assertEqual(state['products'][0]['stock'],8)
        self.call('payments',{'document_id':doc['id'],'amount':'70','paid':'2026-01-15','reference':'Bank'})
        self.assertEqual(self.call('state')['documents'][0]['paid'],7000)
        self.call('payments',{'document_id':doc['id'],'amount':'151','paid':'2026-01-15'},400)
        self.document(qty='100',expected=400)
        self.assertEqual(len(self.call('state')['documents']),1)
        self.call('clear',{'password':'a-login-password','confirmation':'CLEAR ALL DATA'},401)
        self.assertEqual(len(self.call('state')['documents']),1)
        self.call('clear',{'password':'a-clearing-password','confirmation':'CLEAR ALL DATA'})
        state=self.call('state')
        self.assertEqual(state['documents'],[])
        self.assertEqual(state['products'],[])
        self.assertEqual(state['settings']['invoice_next'],'2')
        self.call('logout',{})
        self.call('state',expected=401)

    def test_purchase_receipt_quote_and_numbering(self):
        self.seed()
        self.document('quotation')
        self.assertEqual(self.call('state')['products'][0]['stock'],10)
        self.call('payments',{'document_id':1,'amount':'1','paid':'2026-01-01'},400)
        self.document('purchase_order','10','80','0')
        self.assertEqual(self.call('state')['products'][0]['stock'],10)
        self.call('receive',{'id':2})
        product=self.call('state')['products'][0]
        self.assertEqual(product['stock'],20)
        self.assertEqual(product['cost'],7000)
        self.call('receive',{'id':2},400)
        self.document()
        self.assertEqual(self.call('state')['documents'][0]['cost'],14000)
        settings=self.call('state')['settings']
        settings['invoice_next']='500'
        settings['quotation_next']='200'
        self.call('settings',settings)
        self.document()
        self.assertEqual(self.call('state')['documents'][0]['number'],'INV-00500')
        settings=self.call('state')['settings'];settings['invoice_next']='500'
        self.call('settings',settings,400)
        self.call('expenses',{'description':'Rent','amount':'100','paid':'2026-01-02'})
        backup=self.call('backup')
        self.assertNotIn('users',backup)
        self.assertEqual(backup['expenses'][0]['amount'],10000)

    def test_validation_password_change_and_atomic_rollback(self):
        self.seed()
        self.call('setup',{'username':'other','password':'some-password','clear_password':'another-password'},400)
        self.call('products',{'name':'Bad','sku':'BAD','price':'NaN','cost':'1','stock':'0'},400)
        self.call('documents',{'kind':'invoice','party_id':1,'issued':'2026-01-01','due':'2026-02-01','items':[{'product_id':1,'qty':'6','price':'100'},{'product_id':1,'qty':'6','price':'100'}]},400)
        self.assertEqual(self.call('state')['products'][0]['stock'],10)
        self.call('passwords',{'current_password':'a-login-password','password':'new-login-password','clear_password':'new-clear-password'})
        self.call('state',expected=401)
        self.call('login',{'username':'owner','password':'a-login-password'},401)
        self.call('login',{'username':'owner','password':'new-login-password'})
        self.call('clear',{'password':'new-clear-password','confirmation':'CLEAR ALL DATA'})

    def test_static_and_cross_origin(self):
        with self.client.open(self.base) as response:
            self.assertIn(b'Ledger',response.read())
            self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
        req=urllib.request.Request(self.base+'/api/clear',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://untrusted.example'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.client.open(req)
        self.assertEqual(error.exception.code,403)


if __name__=='__main__':
    unittest.main()
