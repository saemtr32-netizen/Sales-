"""Recover the administrator account using local access to the server database.

Passwords are prompted privately, never accepted as command-line arguments.
This utility does not delete or export business records.
"""
import argparse
import getpass
import os
from pathlib import Path
import sqlite3

import app


def reset_admin(database, username, password, clear_password=''):
    database = Path(database).expanduser().resolve()
    # mode=rw refuses missing files instead of creating an empty installation.
    with sqlite3.connect(database.as_uri() + '?mode=rw', uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        user = db.execute('SELECT * FROM users WHERE id=1').fetchone()
        if not user:
            raise ValueError('No administrator exists. Start the application and create an account.')
        if not password:
            raise ValueError('A new login password is required.')
        if 'credential_version' not in user.keys():
            db.execute('ALTER TABLE users ADD COLUMN credential_version INTEGER NOT NULL DEFAULT 0')
        app.update_account(db, user, username, password, clear_password)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Reset the local Nexvant administrator without deleting business records.')
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument('--database', type=Path, help='Path to the existing sales.db file')
    destination.add_argument('--desktop', action='store_true', help='Use the Windows controller database location')
    args = parser.parse_args(argv)
    if args.desktop:
        from windows.desktop import data_path
        database = data_path()
    else:
        database = args.database or Path(os.environ.get('SALES_DB', app.ROOT / 'data' / 'sales.db'))
    database = database.expanduser().resolve()
    print('Nexvant Engineering — administrator recovery')
    print('Run this tool on the computer that stores your business database.')
    print('Stop the application first. All existing sessions will be signed out.')
    print('Company settings and business records will be kept.')
    print(f'Database: {database}')
    if not database.is_file():
        print('Reset failed: Database not found. Select the existing database with --database.')
        return 1
    try:
        if input('Reset the administrator for this database? Type RESET to continue: ').strip() != 'RESET':
            print('Cancelled. Account unchanged.')
            return 1
        username = input('New username: ').strip()
        password = getpass.getpass('New login password (at least 10 characters): ')
        confirmation = getpass.getpass('Confirm new login password: ')
        if password != confirmation:
            raise ValueError('The new password and its confirmation must match.')
        clear_password = ''
        if input('Also replace the data clearing password? [y/N]: ').strip().lower() == 'y':
            clear_password = getpass.getpass('New data clearing password (different from login): ')
            if clear_password != getpass.getpass('Confirm new data clearing password: '):
                raise ValueError('The clearing password and its confirmation must match.')
            if not clear_password:
                raise ValueError('A new data clearing password is required when replacing it.')
        reset_admin(database, username, password, clear_password)
    except (ValueError, sqlite3.Error) as exc:
        print(f'Reset failed: {exc}')
        return 1
    except (EOFError, KeyboardInterrupt):
        print('\nCancelled. Account unchanged.')
        return 1
    print('Administrator reset. Start the application and sign in with your new credentials.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
