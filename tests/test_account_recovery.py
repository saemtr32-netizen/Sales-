import contextlib
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import app
import reset_account


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original = app.DB_PATH
        self.database = Path(self.directory.name) / 'sales.db'
        app.DB_PATH = self.database
        # Model an existing installation created before credential versioning.
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL,clear_salt TEXT NOT NULL,clear_password TEXT NOT NULL)')
            salt, clear_salt = '01'*16, '02'*16
            db.execute('INSERT INTO users VALUES(1,?,?,?,?,?)',
                       ('owner',salt,app.password_hash('a-login-password',salt),
                        clear_salt,app.password_hash('a-clearing-password',clear_salt)))

    def tearDown(self):
        app.DB_PATH = self.original
        self.directory.cleanup()

    def user(self):
        with sqlite3.connect(self.database) as db:
            db.row_factory = sqlite3.Row
            return dict(db.execute('SELECT * FROM users WHERE id=1').fetchone())

    def test_existing_database_upgrade_is_repeatable_and_preserves_credentials(self):
        before = self.user()
        app.initialize()
        app.initialize()
        after = self.user()
        self.assertEqual(after.pop('credential_version'),0)
        self.assertEqual(before,after)

    def test_legacy_account_recovery_and_invalid_reset_rollback(self):
        before = self.user()
        with self.assertRaises(ValueError):
            reset_account.reset_admin(self.database,'new-owner','a-clearing-password')
        self.assertEqual(self.user(),before)
        reset_account.reset_admin(self.database,'new-owner','a-new-login-password')
        user = self.user()
        self.assertEqual(user['username'],'new-owner')
        self.assertEqual(user['credential_version'],1)
        self.assertEqual(user['clear_password'],before['clear_password'])
        self.assertTrue(app.check_password('a-new-login-password',user['salt'],user['password']))

    def test_recovery_command_prompts_privately_and_can_be_cancelled(self):
        before = self.user()
        output = io.StringIO()
        with patch('builtins.input',return_value='CANCEL'), contextlib.redirect_stdout(output):
            self.assertEqual(reset_account.main(['--database',str(self.database)]),1)
        self.assertEqual(before,self.user())
        with patch('builtins.input',side_effect=['RESET','new-owner','n']), \
             patch('getpass.getpass',side_effect=['a-new-login-password']*2) as passwords, \
             contextlib.redirect_stdout(output):
            self.assertEqual(reset_account.main(['--database',str(self.database)]),0)
        self.assertEqual(passwords.call_count,2)
        self.assertNotIn('a-new-login-password',output.getvalue())
        self.assertEqual(self.user()['username'],'new-owner')

    def test_missing_database_is_not_created(self):
        missing = Path(self.directory.name) / 'missing.db'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(reset_account.main(['--database',str(missing)]),1)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
