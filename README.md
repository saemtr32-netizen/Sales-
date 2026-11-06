# Nexvant Engineering — Sales & Finance

A mobile-friendly sales, purchasing and financial management workspace for Nexvant Engineering. The server uses Python 3.10+ and SQLite, without third-party runtime packages. Android and Windows share the same records when connected to the same server.

## Downloads

- [Android development APK](downloads/NexvantEngineering-Android.apk?raw=true) — Android 8.0+, connects to your running business server. Compilation and APK signatures are verified; installation and native features still need device testing.
- [Windows launcher and complete source ZIP](downloads/NexvantEngineering-Windows-and-Source.zip?raw=true) — extract, install Python 3.10+ with Tcl/Tk, then double-click `start-windows.bat`. This package contains source and a launcher, not a prebuilt Windows executable.
- [Download checksums](downloads/SHA256SUMS.txt)

For a standalone Windows executable, manually run **Build Windows desktop application** under this repository's Actions tab and download its artifact, or follow [the Windows build instructions](windows/README.md). A successful Windows workflow run is needed before claiming the executable has been built and tested.

## Start on a computer

```sh
cd /workspace/Sales-
python3 app.py
```

Create your administrator account on first use. Choose **different login and data-clearing passwords**, at least 10 characters each. No default account is shipped. The server listens on `127.0.0.1:8000` by default.

On **Windows**, install Python 3.10+ including Tcl/Tk and double-click `start-windows.bat`. A desktop control window starts the local application and opens your browser. It provides Start, Open application, Stop and optional phone access. See [Windows instructions](windows/README.md) for building a portable executable that includes Python, or using the manual GitHub Actions build. A Windows executable must be built and tested on Windows; this repository's Linux validation does not establish that the `.exe` has been built.

## Android phones

See [Android instructions](android/README.md) for the native Android client, APK build/install instructions and server configuration. Android connects to the business server rather than keeping a separate offline database. Keep the Windows PC/server awake and running.

For a trusted private Wi-Fi network, enable phone access in the Windows controller. Alternatively:

```sh
python3 app.py --host 0.0.0.0
```

Use the PC's private IPv4 address and port 8000 in the Android connection screen, with its explicit local HTTP option. Limit the firewall rule to private networks. For remote access use an HTTPS reverse proxy and its HTTPS URL. Do not expose the raw HTTP server publicly or forward port 8000 through your router. Android requires Android 8.0 or newer and a current Android System WebView.

## Set up Nexvant documents

Under **Settings**:

- Enter the business name, address, contact details, tax ID, currency, bank details and document terms.
- Select a PNG, JPEG or WebP logo (up to 700 KiB), then save company settings. It appears in the workspace and printable documents/reports. A simple NE monogram is used until a logo is selected.
- Set each document prefix and **next invoice / quotation / purchase order number**. For example, prefix `NE/INV/` with next number `100` produces `NE/INV/00100`. A preview shows the next number. The setting affects future documents; already-issued numbers remain reserved even after business data is cleared.

A branded A4 invoice/quotation/order layout is included with contact details, logo, itemized amounts, tax, payment due date, bank details and terms. The chat logo's original image bytes were not available to the checkout, so it has not been substituted with a recreated logo: select the original file in Settings. An invoice template file was not available; exact matching remains pending that template.

## Business workflow

1. Add customer and supplier accounts.
2. Add inventory products with opening whole-unit quantity, unit cost and selling price.
3. Create invoices, quotations or purchase orders. Invoices reduce stock and snapshot historical unit costs. Quotations do not change stock. Receiving a purchase order increases stock once and updates weighted average cost.
4. Record full or partial customer receipts and supplier payments. Overpayments are rejected.
5. Open **Statement** for any customer/supplier to view every charge/payment, running balance, outstanding documents and each payment due date. Print or save as PDF. Overdue balances are highlighted.
6. Record operating expenses. Open **Reports** for date-filtered profit and loss and printable account statements. Revenue excludes tax; cost of goods sold uses the cost captured on invoices; operating expenses reduce profit. Inventory purchases are expensed when sold rather than deducted again in full.
7. Use Print / save PDF on invoices, quotations, purchase orders and statements. Android uses its native print/PDF dialog; desktop browsers use their print dialog.

This is an operational finance tool for a single business and administrator, not statutory tax filing or full double-entry accounting. Currency settings change the label, not historical amounts. Documents are immutable after creation. Returns, credit notes, cancellations, partial purchase receipts, automatic quotation conversion, multi-user roles and offline phone synchronization are not implemented.

## Passwords, clearing and backups

Passwords use salted PBKDF2-SHA256 (260,000 iterations); sessions expire after eight hours. Login attempts and incorrect clearing attempts are rate-limited. Password changes sign out existing sessions. There is no password recovery service.

**Clear all business data** requires a signed-in session, the separate clearing password and the exact phrase `CLEAR ALL DATA`. It deletes parties, stock, documents, payments and expenses while keeping the account, business settings and issued-number registry. Clearing does not erase copies in backups or guarantee forensic erasure.

Direct Python server data is stored in `data/sales.db`. The Windows controller uses `%LOCALAPPDATA%\NexvantEngineering\data\sales.db` and offers to copy an existing repository database on first launch. `SALES_DB` overrides either location. Existing company details and records are preserved during schema upgrades; only the original placeholder company name is replaced with Nexvant Engineering.

For a restorable backup, stop the server and copy its entire data directory to a private location. Restore while the server is stopped. **Export business records** produces readable JSON without password hashes; it is not an automatic database restore format. Protect the computer and backups using OS account permissions and disk encryption.

## Development checks

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
python3 -m unittest discover -s windows -p 'test_desktop.py' -v
python3 windows/desktop.py --smoke-test
```

HTTP tests and desktop smoke checks use temporary SQLite databases and local servers, leaving business records untouched. The mobile/desktop browser workflow is additionally verified using Playwright and Chromium when available. Android build and address-policy checks are documented in `android/README.md`. Windows executable and Android device testing are separate from source-level checks; see platform documentation for the exact validation performed.

For the optional browser check, install Playwright and Chromium in your development environment, then run `python3 tests/browser_smoke.py --artifacts-dir /tmp/nexvant-browser-check`. It exercises real forms, purchasing, inventory, payments, statements, PDF contents, mobile layouts and the Android bridge hooks against a disposable database.
