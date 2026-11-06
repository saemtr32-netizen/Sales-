import http.cookiejar
import base64
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
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

    def test_branding_settings_and_logo_validation(self):
        settings = self.call('state')['settings']
        self.assertEqual(settings['company'], 'Nexvant Engineering')
        # A small valid PNG; logo and business fields persist through restarts.
        logo = 'data:image/png;base64,' + base64.b64encode(base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9F8AAAAASUVORK5CYII='
        )).decode()
        self.call('settings', {'logo':logo, 'email':'accounts@nexvant.example',
                               'phone':'12345', 'tax_id':'TEST-TAX',
                               'bank_details':'Example Bank', 'document_terms':'Payment within 30 days.'})
        app.initialize()
        saved = self.call('state')['settings']
        self.assertEqual(saved['logo'], logo)
        self.assertEqual(saved['bank_details'], 'Example Bank')
        self.assertEqual(saved['company'], 'Nexvant Engineering')
        for bad in ('data:image/svg+xml;base64,PHN2Zz4=',
                    'https://untrusted.example/logo.png',
                    'data:image/png;base64,not-base64',
                    'data:image/png;base64,' + base64.b64encode(b'not a PNG').decode(),
                    'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * app.LOGO_LIMIT).decode()):
            self.call('settings', {'logo':bad}, 400)
        self.assertEqual(self.call('state')['settings']['logo'], logo)
        self.call('settings', {'logo':''})
        self.assertEqual(self.call('state')['settings']['logo'], '')

    def test_starting_numbers_and_reserved_numbers_after_clearing(self):
        self.seed()
        self.call('settings', {'invoice_prefix':'NE/INV/', 'invoice_next':'100',
                               'quotation_prefix':'NE/Q/', 'quotation_next':'500'})
        self.document()
        self.document('quotation')
        docs = self.call('state')['documents']
        self.assertEqual({d['number'] for d in docs}, {'NE/INV/00100', 'NE/Q/00500'})
        self.call('clear', {'password':'a-clearing-password', 'confirmation':'CLEAR ALL DATA'})
        self.assertEqual(self.call('state')['documents'], [])
        self.call('settings', {'invoice_next':'100'}, 400)
        self.call('settings', {'quotation_next':'500'}, 400)
        self.assertEqual(self.call('state')['settings']['invoice_next'], '101')
        self.call('settings', {'quotation_prefix':'NE/INV/', 'quotation_next':'101'}, 400)
        self.assertEqual(self.call('state')['settings']['quotation_prefix'], 'NE/Q/')

    def test_existing_documents_migrate_to_reserved_number_registry(self):
        self.seed()
        self.document()
        # Simulate an older database whose issued documents predate the registry.
        with app.connect() as db:
            db.execute('DELETE FROM document_numbers')
        app.initialize()
        app.initialize()  # Migration must be safe to repeat.
        with app.connect() as db:
            numbers = [row['number'] for row in db.execute('SELECT number FROM document_numbers')]
        self.assertEqual(numbers, ['INV-00001'])
        self.assertEqual(self.call('state')['settings']['invoice_next'], '2')
        self.call('clear', {'password':'a-clearing-password', 'confirmation':'CLEAR ALL DATA'})
        self.call('settings', {'invoice_next':'1'}, 400)

    def test_failed_document_rolls_back_number_reservation_and_stock(self):
        self.seed()
        # Tax is checked after stock updates and reservation of the next number.
        self.document(tax='NaN', expected=400)
        state = self.call('state')
        self.assertEqual(state['documents'], [])
        self.assertEqual(state['products'][0]['stock'], 10)
        self.assertEqual(state['settings']['invoice_next'], '1')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM document_numbers').fetchone()[0], 0)
        self.document()
        state = self.call('state')
        self.assertEqual(state['documents'][0]['number'], 'INV-00001')
        self.assertEqual(state['products'][0]['stock'], 8)

    def test_concurrent_invoices_allocate_distinct_numbers(self):
        self.seed()
        barrier = threading.Barrier(4)
        cookie = 'session=' + next(iter(app.SESSIONS))
        payload = json.dumps({'kind':'invoice', 'party_id':1, 'issued':'2026-01-01',
                              'due':'2026-02-01', 'tax':'0',
                              'items':[{'product_id':1, 'qty':'2', 'price':'100'}]}).encode()

        def create_invoice(_):
            # Each caller owns its HTTP client; they share only the test session.
            client = urllib.request.build_opener()
            request = urllib.request.Request(self.base + '/api/documents', data=payload,
                headers={'Content-Type':'application/json', 'Cookie':cookie})
            barrier.wait(timeout=5)
            with client.open(request, timeout=10) as response:
                return response.status, json.load(response)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create_invoice, range(4)))
        self.assertEqual(results, [(200, {'ok':True})] * 4)
        state = self.call('state')
        self.assertEqual({d['number'] for d in state['documents']},
                         {'INV-00001', 'INV-00002', 'INV-00003', 'INV-00004'})
        self.assertEqual(len(state['documents']), 4)
        self.assertEqual(state['settings']['invoice_next'], '5')
        self.assertEqual(state['products'][0]['stock'], 2)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM document_numbers').fetchone()[0], 4)

    def test_different_passwords_and_clearing_rate_limit(self):
        self.call('passwords', {'current_password':'a-login-password',
                               'clear_password':'a-login-password'}, 400)
        self.call('passwords', {'current_password':'a-login-password',
                               'password':'a-clearing-password'}, 400)
        self.call('passwords', {'current_password':'a-login-password',
                               'password':'a-shared-password', 'clear_password':'a-shared-password'}, 400)
        self.seed()
        for _ in range(5):
            self.call('clear', {'password':'wrong-password', 'confirmation':'CLEAR ALL DATA'}, 401)
        result = self.call('clear', {'password':'a-clearing-password', 'confirmation':'CLEAR ALL DATA'}, 401)
        self.assertIn('Too many', result['error'])
        self.assertEqual(len(self.call('state')['products']), 1)

    def test_initial_setup_rejects_identical_passwords(self):
        # Use a separate empty DB without changing the configured account.
        original = app.DB_PATH
        try:
            app.DB_PATH = Path(self.temp.name) / 'fresh.db'
            app.initialize()
            self.call('setup', {'username':'owner', 'password':'same-password',
                                'clear_password':'same-password'}, 400)
            self.assertTrue(self.call('status')['setup'])
        finally:
            app.DB_PATH = original

    def test_oversized_document_is_rejected_without_consuming_number(self):
        self.seed()
        self.document('purchase_order', qty='1000000000', price='1000000000', expected=400)
        self.assertEqual(self.call('state')['documents'], [])
        self.assertEqual(self.call('state')['settings']['purchase_order_next'], '1')
        self.document('purchase_order')
        self.assertEqual(self.call('state')['documents'][0]['number'], 'PO-00001')


if __name__=='__main__':
    unittest.main()
