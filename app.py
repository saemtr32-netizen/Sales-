"""Ledger — local sales and financial management. Python 3.10+, no dependencies."""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import threading
import webbrowser
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get('SALES_DB', ROOT / 'data' / 'sales.db'))
SESSIONS = {}
KINDS = ('invoice', 'quotation', 'purchase_order')


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL,clear_salt TEXT NOT NULL,clear_password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS parties(id INTEGER PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('customer','supplier')),email TEXT NOT NULL DEFAULT '',phone TEXT NOT NULL DEFAULT '',address TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,sku TEXT UNIQUE NOT NULL,price INTEGER NOT NULL,cost INTEGER NOT NULL,stock INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,number TEXT UNIQUE NOT NULL,party_id INTEGER NOT NULL REFERENCES parties(id),issued TEXT NOT NULL,due TEXT NOT NULL,total INTEGER NOT NULL,cost INTEGER NOT NULL,tax INTEGER NOT NULL,notes TEXT NOT NULL,received INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS lines(id INTEGER PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,product_id INTEGER NOT NULL REFERENCES products(id),name TEXT NOT NULL,qty INTEGER NOT NULL,price INTEGER NOT NULL,cost INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id),amount INTEGER NOT NULL,paid TEXT NOT NULL,reference TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY,description TEXT NOT NULL,amount INTEGER NOT NULL,paid TEXT NOT NULL);
        ''')
        defaults = {'company':'Your company','address':'','currency':'INR','invoice_next':'1','quotation_next':'1','purchase_order_next':'1','invoice_prefix':'INV-','quotation_prefix':'QUO-','purchase_order_prefix':'PO-'}
        db.executemany('INSERT OR IGNORE INTO settings VALUES (?,?)', defaults.items())


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 260000).hex()


def check_password(password, salt, expected):
    return hmac.compare_digest(password_hash(password, salt), expected)


def required(data, name):
    value = str(data.get(name, '')).strip()
    if not value or len(value) > 2000:
        raise ValueError(f'{name.replace("_", " ").title()} is required (maximum 2000 characters).')
    return value


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 1000000000:
            raise ValueError('Amount must be between 0 and 1,000,000,000.')
        return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        raise ValueError('Enter a valid amount.')


def integer(value, minimum=1):
    result = int(value)
    if str(result) != str(value) or result < minimum or result > 1000000000:
        raise ValueError('Enter a valid whole number.')
    return result


def valid_date(value):
    return date.fromisoformat(str(value)).isoformat()


def rows(db, sql, params=()):
    return [dict(r) for r in db.execute(sql, params)]


def state(db):
    return {'settings':dict(db.execute('SELECT key,value FROM settings').fetchall()),
            'parties':rows(db,'SELECT * FROM parties ORDER BY name'),
            'products':rows(db,'SELECT * FROM products ORDER BY name'),
            'documents':rows(db,'''SELECT d.*,p.name party_name,p.kind party_kind,COALESCE((SELECT SUM(amount) FROM payments WHERE document_id=d.id),0) paid FROM documents d JOIN parties p ON p.id=d.party_id ORDER BY d.id DESC'''),
            'lines':rows(db,'SELECT * FROM lines'), 'payments':rows(db,'SELECT * FROM payments ORDER BY paid,id'),
            'expenses':rows(db,'SELECT * FROM expenses ORDER BY paid DESC')}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Avoid logging query strings, cookies, or request payloads.
        pass

    def session(self):
        cookie = self.headers.get('Cookie', '')
        token = next((v.strip()[8:] for v in cookie.split(';') if v.strip().startswith('session=')), '')
        session = SESSIONS.get(token)
        if not session or session['expires'] < time.time():
            SESSIONS.pop(token, None)
            return None
        return session

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/status':
            with connect() as db:
                return self.send(200, {'setup':not bool(db.execute('SELECT 1 FROM users').fetchone()),'authenticated':bool(self.session())})
        if path.startswith('/api/'):
            if not self.session():
                return self.send(401, {'error':'Please log in.'})
            with connect() as db:
                if path == '/api/state':
                    return self.send(200, state(db))
                if path == '/api/backup':
                    return self.send(200, {'version':1, 'exported':date.today().isoformat(), **state(db)})
            return self.send(404, {'error':'Not found.'})
        files = {'/':('index.html','text/html; charset=utf-8'), '/app.js':('app.js','text/javascript; charset=utf-8'), '/style.css':('style.css','text/css; charset=utf-8')}
        if path not in files:
            return self.send(404, {'error':'Not found.'})
        filename, mime = files[path]
        self.send(200, (ROOT / 'static' / filename).read_bytes(), mime)

    def do_POST(self):
        # Browsers must submit JSON and match this server's origin; no CORS is enabled.
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://' + self.headers.get('Host',''), 'https://' + self.headers.get('Host','')):
            return self.send(403, {'error':'Invalid request origin.'})
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.send(415, {'error':'JSON required.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1000000:
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('JSON object required.')
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                result = self.mutate(db, self.path, data)
            self.send(200, result)
        except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as exc:
            self.send(400, {'error':str(exc)})
        except PermissionError as exc:
            self.send(401, {'error':str(exc)})

    def mutate(self, db, path, data):
        if path == '/api/setup':
            if db.execute('SELECT 1 FROM users').fetchone():
                raise ValueError('An administrator already exists.')
            username = required(data,'username')
            password, clear = required(data,'password'), required(data,'clear_password')
            if min(len(password),len(clear)) < 10:
                raise ValueError('Both passwords must contain at least 10 characters.')
            salt, clear_salt = secrets.token_hex(16), secrets.token_hex(16)
            db.execute('INSERT INTO users VALUES(1,?,?,?,?,?)',(username,salt,password_hash(password,salt),clear_salt,password_hash(clear,clear_salt)))
            return {'ok':True}
        if path == '/api/login':
            # Limit brute-force attempts per client without retaining credentials.
            attempts = getattr(self.server, 'attempts', {})
            self.server.attempts = attempts
            key = self.client_address[0]
            recent = [t for t in attempts.get(key,[]) if t > time.time()-60]
            attempts[key] = recent
            if len(recent) >= 10:
                raise PermissionError('Too many attempts. Try again in one minute.')
            user = db.execute('SELECT * FROM users WHERE username=?',(data.get('username',''),)).fetchone()
            if not user or not check_password(str(data.get('password','')),user['salt'],user['password']):
                recent.append(time.time())
                raise PermissionError('Invalid username or password.')
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = {'user_id':user['id'],'expires':time.time()+8*3600}
            self.session_cookie = f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
            return {'ok':True}
        session = self.session()
        if not session:
            raise PermissionError('Please log in.')
        if path == '/api/logout':
            for token, value in list(SESSIONS.items()):
                if value is session:
                    del SESSIONS[token]
            return {'ok':True}
        if path == '/api/parties':
            kind = required(data,'kind')
            if kind not in ('customer','supplier'):
                raise ValueError('Invalid account type.')
            db.execute('INSERT INTO parties(name,kind,email,phone,address) VALUES(?,?,?,?,?)',(required(data,'name'),kind,str(data.get('email','')),str(data.get('phone','')),str(data.get('address',''))))
        elif path == '/api/products':
            db.execute('INSERT INTO products(name,sku,price,cost,stock) VALUES(?,?,?,?,?)',(required(data,'name'),required(data,'sku'),money(data['price']),money(data['cost']),integer(data['stock'],0)))
        elif path == '/api/documents':
            kind = required(data,'kind')
            if kind not in KINDS:
                raise ValueError('Invalid document type.')
            party = db.execute('SELECT * FROM parties WHERE id=?',(data['party_id'],)).fetchone()
            if not party or party['kind'] != ('supplier' if kind == 'purchase_order' else 'customer'):
                raise ValueError('Choose the correct customer or supplier account.')
            issued, due = valid_date(data['issued']),valid_date(data['due'])
            if due < issued:
                raise ValueError('Due date must be on or after the issue date.')
            items = data['items']
            if not isinstance(items,list) or not 1 <= len(items) <= 100:
                raise ValueError('Add between 1 and 100 line items.')
            lines, quantities, subtotal, cost = [], {}, 0, 0
            for item in items:
                product = db.execute('SELECT * FROM products WHERE id=?',(item['product_id'],)).fetchone()
                if not product:
                    raise ValueError('Product not found.')
                qty, price = integer(item['qty']),money(item['price'])
                quantities[product['id']] = quantities.get(product['id'],0)+qty
                subtotal += qty*price
                cost += qty*product['cost']
                lines.append((product['id'],product['name'],qty,price,product['cost']))
            if kind == 'invoice':
                for pid, qty in quantities.items():
                    if db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()['stock'] < qty:
                        raise ValueError('Insufficient inventory. Receive a purchase order first.')
                    db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,pid))
            settings = dict(db.execute('SELECT key,value FROM settings').fetchall())
            number = settings[kind+'_prefix'] + str(int(settings[kind+'_next'])).zfill(5)
            tax = money(data.get('tax',0))
            cursor = db.execute('INSERT INTO documents(kind,number,party_id,issued,due,total,cost,tax,notes) VALUES(?,?,?,?,?,?,?,?,?)',(kind,number,party['id'],issued,due,subtotal+tax,cost,tax,str(data.get('notes',''))))
            db.executemany('INSERT INTO lines(document_id,product_id,name,qty,price,cost) VALUES(?,?,?,?,?,?)',[(cursor.lastrowid,*line) for line in lines])
            db.execute('UPDATE settings SET value=? WHERE key=?',(str(int(settings[kind+'_next'])+1),kind+'_next'))
        elif path == '/api/receive':
            doc = db.execute('SELECT * FROM documents WHERE id=?',(data['id'],)).fetchone()
            if not doc or doc['kind'] != 'purchase_order' or doc['received']:
                raise ValueError('Only an unreceived purchase order can be received.')
            for line in db.execute('SELECT * FROM lines WHERE document_id=?',(doc['id'],)).fetchall():
                product = db.execute('SELECT * FROM products WHERE id=?',(line['product_id'],)).fetchone()
                stock = product['stock']+line['qty']
                avg = int((Decimal(product['stock']*product['cost']+line['qty']*line['price'])/stock).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                db.execute('UPDATE products SET stock=?,cost=? WHERE id=?',(stock,avg,product['id']))
            db.execute('UPDATE documents SET received=1 WHERE id=?',(doc['id'],))
        elif path == '/api/payments':
            doc = db.execute('SELECT * FROM documents WHERE id=?',(data['document_id'],)).fetchone()
            if not doc or doc['kind'] == 'quotation':
                raise ValueError('Choose an invoice or purchase order.')
            paid = db.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE document_id=?',(doc['id'],)).fetchone()[0]
            amount = money(data['amount'])
            if amount <= 0 or amount > doc['total']-paid:
                raise ValueError('Payment must be positive and cannot exceed the outstanding balance.')
            db.execute('INSERT INTO payments(document_id,amount,paid,reference) VALUES(?,?,?,?)',(doc['id'],amount,valid_date(data['paid']),str(data.get('reference',''))))
        elif path == '/api/expenses':
            amount = money(data['amount'])
            if amount <= 0:
                raise ValueError('Expense must be positive.')
            db.execute('INSERT INTO expenses(description,amount,paid) VALUES(?,?,?)',(required(data,'description'),amount,valid_date(data['paid'])))
        elif path == '/api/settings':
            for key in ('company','address','currency'):
                value = str(data.get(key,''))
                if key != 'address' and not value.strip():
                    raise ValueError(f'{key} is required.')
                if key == 'currency' and (len(value) != 3 or not value.isalpha()):
                    raise ValueError('Use a three-letter currency code.')
                db.execute('UPDATE settings SET value=? WHERE key=?',(value,key))
            for kind in KINDS:
                counter = integer(data[kind+'_next'])
                prefix = str(data[kind+'_prefix']).strip()
                if len(prefix)>30:
                    raise ValueError('Prefixes must be 30 characters or fewer.')
                if db.execute('SELECT 1 FROM documents WHERE number=?',(prefix+str(counter).zfill(5),)).fetchone():
                    raise ValueError('This starting number already exists.')
                db.execute('UPDATE settings SET value=? WHERE key=?',(str(counter),kind+'_next'))
                db.execute('UPDATE settings SET value=? WHERE key=?',(prefix,kind+'_prefix'))
        elif path == '/api/passwords':
            user = db.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
            if not check_password(str(data.get('current_password','')),user['salt'],user['password']):
                raise PermissionError('Current login password is incorrect.')
            for name, salt_col, hash_col in [('password','salt','password'),('clear_password','clear_salt','clear_password')]:
                value = str(data.get(name,''))
                if value:
                    if len(value)<10:
                        raise ValueError('Passwords must contain at least 10 characters.')
                    salt=secrets.token_hex(16)
                    db.execute(f'UPDATE users SET {salt_col}=?,{hash_col}=? WHERE id=?',(salt,password_hash(value,salt),session['user_id']))
            SESSIONS.clear()
        elif path == '/api/clear':
            user=db.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
            if data.get('confirmation') != 'CLEAR ALL DATA' or not check_password(str(data.get('password','')),user['clear_salt'],user['clear_password']):
                raise PermissionError('Clearing password or confirmation is incorrect.')
            for table in ('payments','lines','documents','expenses','products','parties'):
                db.execute(f'DELETE FROM {table}')
            # Keep login, company details, and numbering to avoid reuse of issued numbers.
        else:
            raise ValueError('Unknown action.')
        return {'ok':True}

    def send(self, status, payload, content_type='application/json'):
        body = json.dumps(payload).encode() if content_type == 'application/json' else payload
        self.send_response(status)
        if getattr(self, 'session_cookie', None):
            self.send_header('Set-Cookie', self.session_cookie)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--open-browser', action='store_true', help='Open the local application in your default browser')
    args=parser.parse_args()
    initialize()
    server = ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'Ledger running at http://{args.host}:{args.port}',flush=True)
    if args.open_browser:
        threading.Timer(0.5, webbrowser.open, args=(f'http://127.0.0.1:{args.port}',)).start()
    server.serve_forever()
