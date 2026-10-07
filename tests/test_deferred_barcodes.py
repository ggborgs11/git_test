import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import app
import profiles
import test_profiles
IMAGE=test_profiles.IMAGE
from test_auth import HTTPFixture

class DeferredBarcodeDataTests(test_profiles.ProfileFixture):
    def test_multiple_profiles_without_barcode_then_assign_and_scan(self):
        people=app.add_people([{'name':'Employee A'},{'name':'Employee B'}])
        self.assertTrue(all(p['barcode'] is None for p in people))
        for invalid in ['',None,'None']:
            with self.assertRaises(ValueError):app.scan(invalid)
        first=app.assign_barcode(people[0]['id'],'001234')
        second=app.assign_barcode(people[1]['id'])
        self.assertNotEqual(first['barcode'],second['barcode'])
        self.assertEqual(app.scan('001234')['action'],'in')
        record=self.get(first['id'])
        app.update_person(first['id'],{'name':'Updated','profile':{'department':'Assembly'},'version':record['version']})
        self.assertEqual(self.get(first['id'])['barcode'],'001234')
        with self.assertRaises(ValueError):app.assign_barcode(first['id'],'888888')
    def test_unique_assignments_and_concurrent_assignment(self):
        a,b=app.add_people([{'name':'A'},{'name':'B'}])
        app.assign_barcode(a['id'],'000001')
        with self.assertRaises(ValueError):app.assign_barcode(b['id'],'000001')
        self.assertIsNone(self.get(b['id'])['barcode'])
        def attempt(_):
            try:return app.assign_barcode(b['id'])['barcode']
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(attempt,range(8)))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertNotEqual(self.get(b['id'])['barcode'],'000001')
    def test_pre_nullable_database_preserves_all_relationships(self):
        app.DB.unlink()
        with sqlite3.connect(app.DB) as db:
            db.executescript('CREATE TABLE people(id INTEGER PRIMARY KEY,name TEXT NOT NULL,barcode TEXT UNIQUE NOT NULL); CREATE TABLE events(id INTEGER PRIMARY KEY,person_id INTEGER NOT NULL REFERENCES people(id),action TEXT NOT NULL,timestamp TEXT NOT NULL);')
            profiles.initialize(db)
            db.execute('INSERT INTO people VALUES(7,?,?)',('Legacy Employee','000007'))
            db.execute('INSERT INTO events VALUES(42,7,?,?)',('in','2026-10-01T01:00:00+00:00'))
            db.execute('INSERT INTO employee_profiles VALUES(7,?,?,3)',('0007',json.dumps({'employee_id':'0007','sss':'000123'})))
            profiles.save_images(db,7,{'photo':profiles.validate_image(IMAGE)})
        app.initialize();app.initialize()
        record=self.get(7)
        self.assertEqual(record['barcode'],'000007');self.assertEqual(record['version'],3)
        self.assertEqual(record['profile']['sss'],'000123');self.assertIn('photo',record['images'])
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT id FROM events').fetchone()[0],42)
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')),[])
            self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertIsNone(app.add_people([{'name':'New employee'}])[0]['barcode'])

class DeferredBarcodeAccessTests(HTTPFixture):
    def test_admin_creates_then_assigns_later(self):
        self.assertEqual(self.request('/api/employees',{'name':'Employee'})[0],401)
        self.assertEqual(self.request('/api/employees')[0],401)
        self.assertEqual(self.request('/api/people/1/barcode',{'barcode':'001234'})[0],401)
        self.assertNotIn(b'person-form',self.request('/admin/201')[1])
        self.request('/api/login',{'password':'test-fixture-password'},self.browser)
        status,body=self.request('/api/employees',{'name':'Employee','profile':{'employee_id':'001'}},self.browser)
        self.assertEqual(status,201);person=json.loads(body)['people'][0];self.assertIsNone(person['barcode'])
        self.assertEqual(self.request('/api/employees',{'name':'Bypass','barcode':'999999'},self.browser)[0],400)
        self.assertIn(b'person-form',self.request('/admin/201',browser=self.browser)[1])
        self.assertNotIn(b'new-barcode',self.request('/admin/201',browser=self.browser)[1])
        self.assertNotIn(b'person-form',self.request('/admin',browser=self.browser)[1])
        status,body=self.request(f'/api/people/{person["id"]}/barcode',{'barcode':'001234'},self.browser)
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['barcode'],'001234')
        self.assertEqual(self.request('/api/scan',{'barcode':'001234'})[0],201)
        self.request('/api/logout',{},self.browser)
        self.assertEqual(self.request('/api/employees',browser=self.browser)[0],401)
