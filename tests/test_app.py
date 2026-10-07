import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
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

    def at(self, barcode, now):
        with patch('app.datetime', wraps=datetime) as clock:
            clock.now.return_value=now
            return app.scan(barcode)

    def test_register_300_people_and_automatic_attendance(self):
        people=app.add_people([{'name':f'Person {i}'} for i in range(300)])
        self.assertTrue(all(p['barcode'] is None for p in people))
        people=[app.assign_barcode(p['id']) for p in people]
        self.assertEqual(len(set(p['barcode'] for p in people)),300)
        barcode=people[0]['barcode'];now=datetime.now(timezone.utc)
        first=self.at(barcode,now)
        self.assertEqual(first['action'],'in');self.assertFalse(first['duplicate'])
        self.assertTrue(self.at(barcode,now+timedelta(seconds=29))['duplicate'])
        second=self.at(barcode,now+timedelta(seconds=30))
        self.assertEqual(second['action'],'out');self.assertFalse(second['duplicate'])
        third=self.at(barcode,now+timedelta(seconds=60))
        self.assertEqual(third['action'],'in')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],3)

    def test_import_is_atomic_and_preserves_leading_zeros(self):
        app.add_people([{'name':'Maria','barcode':'001234'}])
        with self.assertRaises(ValueError):
            app.add_people([{'name':'Juan'},{'name':'Duplicate','barcode':'001234'}])
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM people').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT barcode FROM people').fetchone()[0],'001234')

    def test_unknown_barcode(self):
        with self.assertRaisesRegex(ValueError,'Unknown barcode'):app.scan('999999')

    def test_simultaneous_scans_record_once(self):
        barcode=app.assign_barcode(app.add_people([{'name':'Alex'}])[0]['id'])['barcode']
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:app.scan(barcode),range(8)))
        self.assertEqual(sum(not r['duplicate'] for r in results),1)
        self.assertEqual(sum(r['duplicate'] for r in results),7)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)

    def test_other_people_can_scan_immediately(self):
        people=app.add_people([{'name':'Alex'},{'name':'Maria'}])
        for person in people:self.assertFalse(app.scan(app.assign_barcode(person['id'])['barcode'])['duplicate'])

    def test_duplicate_window_and_status_survive_restart(self):
        barcode=app.assign_barcode(app.add_people([{'name':'Alex'}])[0]['id'])['barcode'];now=datetime.now(timezone.utc)
        first=self.at(barcode,now)
        app.initialize()
        repeated=self.at(barcode,now+timedelta(seconds=10))
        self.assertTrue(repeated['duplicate']);self.assertEqual(repeated['timestamp'],first['timestamp'])
        self.assertEqual(repeated['retry_after'],20)
        app.initialize()
        self.assertEqual(self.at(barcode,now+timedelta(seconds=31))['action'],'out')

    def test_overnight_shift_and_local_date_boundary(self):
        barcode=app.assign_barcode(app.add_people([{'name':'Alex'}])[0]['id'])['barcode']
        self.at(barcode,datetime(2026,10,5,15,59,tzinfo=timezone.utc))
        result=self.at(barcode,datetime(2026,10,5,16,1,tzinfo=timezone.utc))
        self.assertEqual(result['action'],'out')
        self.assertEqual(len(app.snapshot('2026-10-05')['events']),1)
        self.assertEqual(len(app.snapshot('2026-10-06')['events']),1)

if __name__ == '__main__':unittest.main()
