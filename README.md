# Ledger — Sales & Finance

A mobile-friendly, self-hosted sales and financial management application. Uses Python 3.10+ and SQLite, with no third-party runtime packages or external services.

## Run

```sh
cd /workspace/Sales-
python3 app.py
```

Open the server in a browser and create your administrator account. Choose separate login and data-clearing passwords (10 characters minimum). No default credentials are shipped. For Windows, install Python 3.10+ and double-click `start-windows.bat`. This is a local Windows browser application; a native `.exe` installer is not included.

The server binds to `127.0.0.1:8000` by default. For a phone on a trusted local network, run `python3 app.py --host 0.0.0.0` and visit the computer's LAN address on port 8000. Allow that port in the Windows firewall only for a private trusted network. Do not expose this HTTP server to the public Internet. For remote access, put it behind an HTTPS reverse proxy; the default is intended for a single local business. Phones use the same database while connected; there is no offline phone sync.

## Workflow

1. Set company details, currency, document prefixes, and next numbers under Settings. Use one currency consistently; changing the label does not convert amounts.
2. Add customer and supplier accounts. Add inventory products with opening quantity, cost, and selling price.
3. Create invoices, quotations, or purchase orders. Invoice and quotation starting numbers are configurable. Document numbers are globally unique, allocated inside a database transaction, and cannot be reused.
4. Invoices reduce stock and snapshot average costs. Quotes do not affect stock. Receive purchase orders once goods arrive; receipt increases stock and updates weighted average cost. Quantities are whole units.
5. Record customer receipts and supplier payments, including partial payments. Overpayments are rejected. Customer and supplier statements list every charge/payment and each outstanding document's payment due date.
6. Print documents, statements, and profit-and-loss reports, or save as PDF through the browser print dialog. A clean A4 invoice template is included. No uploaded template was available during implementation; exact matching remains pending receipt of that file.
7. Record operating expenses. Profit and loss uses invoice revenue excluding tax, historical cost of goods sold, and operating expenses, with optional date filters. Purchase inventory is expensed when sold. This is an operational report, not full double-entry accounting or a tax filing system.

## Security and backups

Passwords are salted with PBKDF2-SHA256 (260,000 iterations). Sessions expire after 8 hours; login attempts are rate-limited. Password changes sign out all sessions. Data clearing requires the separate clearing password plus `CLEAR ALL DATA`; login, settings, and document counters remain intact. Protect the computer and its database with OS account permissions and disk encryption. This release has a single administrator account and no password recovery service.

Data lives in `data/sales.db` (override with `SALES_DB`). For a complete restorable backup, stop the server and copy the `data` folder to a protected location. Restore by stopping the server and replacing that folder with the backup. Settings also provides a readable JSON export of business records; it excludes password hashes and is not an automatic restore format. Keep backups private. Data clearing does not erase copies in backups or guarantee forensic erasure from disk.

Documents are immutable after creation. Returns, cancellations, credit notes, document conversion, stock adjustments, multi-user roles, bank reconciliation, and native Windows packaging are not implemented. Avoid entering erroneous opening balances or documents; validate before saving.

## Validation

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
```

Tests use a temporary SQLite database and a real local HTTP server, leaving business data untouched. No dependency installation, cloud credentials, or network access is required to run the application.
