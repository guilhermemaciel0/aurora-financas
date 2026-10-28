"""Exercise the client form -> finance model -> JSON -> API contract."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import server


ROOT = Path(__file__).resolve().parents[1]
FORM_FIXTURE = """
import {emptyState, parseMoney, today, validateTransaction} from './src/finance.mjs';
import {makeCard, purchase, pay} from './src/cards.mjs';

const state = emptyState();
state.accounts[0].opening = 100000;
// The shared movement form also contains fields used by account/goal forms.
const form = {
  description: '', amount: '', date: today(), type: 'expense',
  category: 'Alimentação', accountId: 'main', toAccountId: 'reserve',
  name: '', target: ''
};
state.transactions = [
  ['income', 'Receita teste', '1,00'],
  ['expense', 'Despesa teste', '2,50'],
  ['transfer', 'Transferência teste', '0,75']
].map(([type, description, amount], index) => validateTransaction(state, {
  ...form, id: 'sync-form-' + index, type, description, amount: parseMoney(amount)
}));
state.cards = [makeCard('Cartão teste', 10000, 2, 10)];
const cardForm = {
  name: '', limit: '', closing: '2', due: '10', amount: '3,00',
  description: 'Compra teste', parts: '1', date: today(), category: 'Compras',
  accountId: 'main', cardId: state.cards[0].id
};
state.purchases = [purchase(state, {
  ...cardForm, amount: parseMoney(cardForm.amount), parts: Number(cardForm.parts)
})];
state.transactions.push(pay(state, state.cards[0].id,
  state.purchases[0].firstMonth, 'main', 100, today()));
state.goals = [{id: 'goal', name: 'Reserva teste', target: 10000, accountId: 'reserve'}];
console.log(JSON.stringify(state));
"""


class SyncFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = subprocess.run(
            ['node', '--input-type=module', '--eval', FORM_FIXTURE],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=10,
        )
        cls.state = json.loads(fixture.stdout)
        cls.temp = tempfile.TemporaryDirectory(prefix='aurora-sync-forms-')
        server.DB = str(Path(cls.temp.name) / 'test.sqlite3')
        server.initialize()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.http.server_port)
        status, login = cls.request('/auth/register', 'POST', {
            'email': 'sync-forms@example.test',
            'password': 'sync-forms-test-password',
        })
        if status != 200:
            raise RuntimeError('Could not create the isolated test session.')
        cls.token = login['token']

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    @classmethod
    def request(cls, path, method='GET', data=None, authenticated=False):
        headers = {
            'Content-Type': 'application/json',
            'Origin': 'http://localhost:8081',
        }
        if authenticated:
            headers['Authorization'] = 'Bearer ' + cls.token
        request = urllib.request.Request(
            cls.url + path, method=method, headers=headers,
            data=json.dumps(data).encode() if data is not None else None,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def save_fixture(self):
        status, before = self.request('/state', authenticated=True)
        self.assertEqual(status, 200)
        status, saved = self.request('/state', 'PUT', {
            'revision': before['revision'], 'state': self.state,
        }, authenticated=True)
        self.assertEqual(status, 200, saved)
        return saved['revision']

    def test_form_records_round_trip(self):
        # Old local records keep these irrelevant form fields after updating.
        self.assertEqual(self.state['transactions'][0]['target'], '')
        self.assertEqual(self.state['purchases'][0]['limit'], '')
        revision = self.save_fixture()
        status, downloaded = self.request('/state', authenticated=True)
        self.assertEqual(status, 200)
        self.assertEqual(downloaded, {'revision': revision, 'state': self.state})
        # Covers income, expense, transfer, purchase and partial invoice payment.
        self.assertEqual(downloaded['state']['transactions'][0]['amount'], 100)
        self.assertEqual(downloaded['state']['transactions'][-1]['amount'], 100)

    def test_invalid_money_still_rejected_without_overwriting(self):
        revision = self.save_fixture()
        for collection, field in (
            ('accounts', 'opening'), ('transactions', 'amount'),
            ('goals', 'target'), ('cards', 'limit'), ('purchases', 'amount'),
        ):
            for value in ('100', 1.5, True, None, 10**12 + 1):
                with self.subTest(collection=collection, field=field, value=value):
                    invalid = copy.deepcopy(self.state)
                    invalid[collection][0][field] = value
                    status, _ = self.request('/state', 'PUT', {
                        'revision': revision, 'state': invalid,
                    }, authenticated=True)
                    self.assertEqual(status, 400)
        status, downloaded = self.request('/state', authenticated=True)
        self.assertEqual(status, 200)
        self.assertEqual(downloaded, {'revision': revision, 'state': self.state})


if __name__ == '__main__':
    unittest.main()
