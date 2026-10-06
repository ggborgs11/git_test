import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import app

class AttendanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = app.DB
        app.DB = Path(self.temp.name) / 'test.db'
        app.initialize()

    def tearDown(self):
        app.DB = self.previous
        self.temp.cleanup()

    def test_register_300_people_and_attendance(self):
        people = app.add_people([{'name': f'Person {i}'} for i in range(300)])
        self.assertEqual(len(set(p['barcode'] for p in people)), 300)
        person = people[0]
        app.scan(person['barcode'], 'in')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            app.scan(person['barcode'], 'in')
        app.scan(person['barcode'], 'out')
        with self.assertRaisesRegex(ValueError, 'already out'):
            app.scan(person['barcode'], 'out')
        state = app.snapshot(app.datetime.now(app.LOCAL).strftime('%Y-%m-%d'))
        self.assertEqual(len(state['events']), 2)
        self.assertEqual(len(state['people']), 300)
        self.assertEqual(next(p for p in state['people'] if p['id']==person['id'])['status'], 'out')

    def test_import_is_atomic_and_preserves_leading_zeros(self):
        app.add_people([{'name': 'Maria', 'barcode': '001234'}])
        with self.assertRaises(ValueError):
            app.add_people([{'name': 'Juan'}, {'name': 'Duplicate', 'barcode': '001234'}])
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM people').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT barcode FROM people').fetchone()[0], '001234')

    def test_unknown_barcode_and_out_without_in(self):
        person = app.add_people([{'name':'Alex'}])[0]
        with self.assertRaises(ValueError): app.scan('999999', 'in')
        with self.assertRaises(ValueError): app.scan(person['barcode'], 'out')
        with self.assertRaises(ValueError): app.scan(person['barcode'], 'invalid')

    def test_simultaneous_scans_record_once(self):
        barcode = app.add_people([{'name':'Alex'}])[0]['barcode']
        def attempt(_):
            try: app.scan(barcode, 'in'); return True
            except ValueError: return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)

    def test_local_date_boundary(self):
        person=app.add_people([{'name':'Alex'}])[0]
        with app.connect() as db:
            db.execute('INSERT INTO events(person_id, action, timestamp) VALUES (?,?,?)',
                       (person['id'],'in','2026-10-05T16:00:00+00:00'))
        self.assertEqual(len(app.snapshot('2026-10-06')['events']),1)
        self.assertEqual(len(app.snapshot('2026-10-05')['events']),0)

if __name__ == '__main__': unittest.main()
