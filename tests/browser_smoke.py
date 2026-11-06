"""Optional desktop/mobile browser workflow. Uses an isolated temporary database.

Install Playwright and Chromium separately, then run:
    python3 tests/browser_smoke.py --artifacts-dir /tmp/nexvant-browser-check
The standard-library unittest suite does not require these browser dependencies.
"""
import argparse
import base64
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]


def run(artifacts):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("Optional check needs Playwright: python3 -m pip install playwright; python3 -m playwright install chromium")
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexvant-browser-") as temp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        environment = dict(os.environ, SALES_DB=str(Path(temp) / "browser.db"))
        with open(Path(temp) / "server.log", "w+") as log:
            server = subprocess.Popen([sys.executable, "app.py", "--port", str(port)], cwd=ROOT, env=environment, stdout=log, stderr=log)
            base = f"http://127.0.0.1:{port}"
            try:
                deadline = time.monotonic() + 20
                while True:
                    if server.poll() is not None:
                        log.seek(0)
                        raise RuntimeError("Test server exited: " + log.read())
                    try:
                        with urllib.request.urlopen(base + "/api/status", timeout=.5) as response:
                            assert json.load(response)["setup"] is True
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Test server did not become ready")
                        time.sleep(.1)
                with sync_playwright() as pw:
                    executable = shutil.which("chromium") or shutil.which("chromium-browser")
                    launch = {"headless": True}
                    if executable:
                        launch["executable_path"] = executable
                    browser = pw.chromium.launch(**launch)
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 1000})
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(base)
                        page.locator('[name=username]').fill('owner')
                        page.locator('[name=password]').fill('a-login-password')
                        page.locator('[name=clear_password]').fill('a-clearing-password')
                        page.get_by_role('button', name='Create account').click()
                        page.get_by_role('button', name='Sign in').wait_for()
                        page.locator('[name=username]').fill('owner')
                        page.locator('[name=password]').fill('a-login-password')
                        page.get_by_role('button', name='Sign in').click()
                        page.get_by_role('heading', name='Business overview').wait_for()

                        def navigate(key):
                            page.locator(f'[data-page="{key}"]').first.click()

                        def modal_fill(name, value):
                            page.locator(f'#modal [name="{name}"]').fill(str(value))

                        def save(name):
                            page.locator('#toast').evaluate('(el) => {el.textContent = "";}')
                            page.get_by_role('button', name=name, exact=True).click()
                            page.wait_for_function("() => !document.querySelector('#modal').open")
                            page.wait_for_function("() => document.querySelector('#toast').textContent === 'Saved successfully.'")

                        # Real form submissions for account and product creation.
                        for kind, name in [('customer', 'Acme <script>alert(1)</script>'), ('supplier', 'Supply Co')]:
                            navigate('customers' if kind == 'customer' else 'suppliers')
                            page.get_by_role('button', name='Add ' + kind).click()
                            modal_fill('name', name)
                            modal_fill('email', 'accounts@example.com')
                            modal_fill('address', 'Industrial estate')
                            save('Create account')
                        navigate('inventory')
                        page.get_by_role('button', name='Add product').click()
                        for name, value in {'name': 'Control panel', 'sku': 'NE-CP-01', 'price': '100', 'cost': '60', 'stock': '10'}.items():
                            modal_fill(name, value)
                        save('Add product')
                        navigate('settings')
                        for name, value in {'company': 'Nexvant Engineering', 'email': 'accounts@nexvant.example', 'tax_id': 'GST123', 'bank_details': 'Bank name\nAccount 12345', 'document_terms': 'Payment due within agreed terms.', 'invoice_next': '100', 'quotation_next': '200'}.items():
                            page.locator(f'[name="{name}"]').fill(value)
                        logo = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
                        page.locator('#logo-file').set_input_files({'name': 'test-logo.png', 'mimeType': 'image/png', 'buffer': logo})
                        page.locator('#logo-preview img').wait_for()
                        assert '00100' in page.locator('[data-number-preview=invoice]').inner_text()
                        page.get_by_role('button', name='Save company & numbering').click()
                        page.wait_for_function("() => document.querySelector('.brand img') !== null")

                        def new_document(kind, quantity, price, tax):
                            navigate(kind)
                            page.locator(f'[data-action="new-{kind}"]').click()
                            modal_fill('issued', '2026-01-01')
                            modal_fill('due', '2026-02-01')
                            modal_fill('qty', quantity)
                            modal_fill('price', price)
                            modal_fill('tax', tax)
                            save('Create document')
                            page.locator('[data-action=document]').first.wait_for()

                        new_document('invoice', '2', '100', '20')
                        assert '00100' in page.locator('[data-action=document]').first.inner_text()
                        page.locator('[data-action=payment]').click()
                        modal_fill('amount', '70')
                        modal_fill('paid', '2026-01-15')
                        save('Record payment')
                        page.locator('[data-action=document]').click()
                        document = page.locator('#modal .document')
                        assert '150.00' in document.inner_text()
                        assert '01 Feb 2026' in document.inner_text()
                        assert 'GST123' in document.inner_text()
                        assert document.locator('script').count() == 0
                        page.evaluate('window.print = () => {window.__printed = true;}')
                        page.get_by_role('button', name='Print / save PDF').click()
                        page.wait_for_function('() => window.__printed === true')
                        assert page.locator('dialog[open]').count() == 0
                        assert 'Bank name' in page.locator('#print-area').inner_text()
                        page.emulate_media(media='print')
                        page.pdf(path=str(artifacts / 'invoice.pdf'), prefer_css_page_size=True)
                        page.emulate_media(media='screen')
                        if shutil.which('pdftotext'):
                            pdf_text = subprocess.check_output(['pdftotext', str(artifacts / 'invoice.pdf'), '-'], text=True)
                            assert 'Nexvant Engineering' in pdf_text and '150.00' in pdf_text and '01 Feb 2026' in pdf_text
                        navigate('customers')
                        page.get_by_role('button', name='Statement').click()
                        statement = page.locator('#modal .document').inner_text()
                        assert 'Payment' in statement and '150.00' in statement and '01 Feb 2026' in statement
                        page.get_by_role('button', name='Close dialog').click()
                        new_document('quotation', '1', '100', '0')
                        assert '00200' in page.locator('[data-action=document]').inner_text()
                        new_document('purchase_order', '10', '80', '0')
                        page.locator('[data-action=receive]').click()
                        save('Receive goods')
                        assert page.locator('[data-action=receive]').count() == 0
                        navigate('inventory')
                        assert '18 units' in page.locator('.content').inner_text()
                        navigate('expenses')
                        page.get_by_role('button', name='Record expense').click()
                        modal_fill('description', 'Operating expense')
                        modal_fill('amount', '50')
                        modal_fill('paid', '2026-01-02')
                        save('Record expense')
                        navigate('reports')
                        profit = page.locator('#profit-report').inner_text()
                        assert 'INR 200.00' in profit and 'INR 120.00' in profit and 'INR 30.00' in profit
                        page.get_by_role('button', name='Print profit & loss').click()
                        assert '30.00' in page.locator('#print-area').inner_text()

                        # Native client hooks: printing and Save As receive the intended data.
                        page.evaluate('window.NexvantAndroid = {printDocument: () => {window.__nativePrint = true}, saveBackup: (json, name) => {window.__backup = {data: JSON.parse(json), name}}}')
                        page.get_by_role('button', name='Print profit & loss').click()
                        page.wait_for_function('() => window.__nativePrint === true')
                        navigate('settings')
                        page.get_by_role('button', name='Export business records').click()
                        page.wait_for_function('() => window.__backup !== undefined')
                        backup = page.evaluate('window.__backup')
                        assert backup['name'].startswith('nexvant-records-') and len(backup['data']['documents']) == 3
                        assert 'users' not in backup['data']
                        navigate('dashboard')
                        page.locator('#toast').evaluate('(el) => el.style.display = "none"')
                        page.screenshot(path=str(artifacts / 'dashboard-desktop.png'), full_page=True)
                        page.set_viewport_size({'width': 375, 'height': 812})
                        for key in ['dashboard', 'settings', 'invoice', 'inventory', 'customers', 'reports']:
                            navigate(key)
                            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Mobile page overflow: {key}'
                            assert page.get_by_role('button', name='Sign out').is_visible()
                            if key in ['dashboard', 'settings']:
                                page.screenshot(path=str(artifacts / f'{key}-mobile.png'), full_page=True)
                        navigate('quotation')
                        page.get_by_role('button', name='Create quotation').click()
                        assert '00201' in page.locator('#document-form .notice').inner_text()
                        assert page.locator('#document-form [name=product_id]').is_visible()
                        assert page.evaluate('document.querySelector("#modal").scrollWidth <= document.querySelector("#modal").clientWidth'), 'Mobile form overflow'
                        assert errors == [], errors
                        print('PASS: setup/login; customer/supplier/product forms; logo upload; number settings; invoice; partial payment; statement due dates; safe text; PDF contents; quotation; PO receipt/stock; P&L; native hooks; desktop/mobile layouts.')
                        print('Artifacts:', artifacts)
                    finally:
                        browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts-dir', type=Path, default=Path(tempfile.gettempdir()) / 'nexvant-browser-check')
    args = parser.parse_args()
    run(args.artifacts_dir.resolve())
