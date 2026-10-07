import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import app
import profiles
from test_auth import HTTPFixture

# A harmless 1x1 PNG fixture, not an employee photograph.
IMAGE='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jP1sAAAAASUVORK5CYII='

class ProfileFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=app.DB
        app.DB=Path(self.temp.name)/'db.sqlite';app.initialize()
    def tearDown(self):
        app.DB=self.previous;self.temp.cleanup()
    def get(self,person_id):
        with app.connect() as db:return profiles.get(db,person_id)

class ProfileDataTests(ProfileFixture):
    def test_create_reopen_edit_and_keep_attendance(self):
        person=app.add_people([{'name':'Test Person','barcode':'000001','profile':{'employee_id':'0012','sss':'00001234','education':'School A'},'photo':IMAGE,'signature':IMAGE}])[0]
        app.scan(person['barcode']);record=self.get(person['id'])
        self.assertEqual(record['profile']['employee_id'],'0012')
        self.assertEqual(record['profile']['sss'],'00001234')
        self.assertEqual(set(record['images']),{'photo','signature'})
        updated=app.update_person(person['id'],{**record,'name':'Updated Person','profile':{**record['profile'],'department':'Production'}})
        self.assertEqual(updated['version'],2)
        self.assertEqual(updated['barcode'],'000001')
        self.assertEqual(updated['profile']['department'],'Production')
        self.assertEqual(set(updated['images']),{'photo','signature'})
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
        app.initialize();self.assertEqual(self.get(person['id'])['profile']['sss'],'00001234')
        app.update_person(person['id'],{**updated,'photo':None})
        self.assertEqual(set(self.get(person['id'])['images']),{'signature'})
    def test_legacy_database_upgrade_preserves_data(self):
        # Simulate a database from a pre-201 version.
        app.DB.unlink()
        with sqlite3.connect(app.DB) as db:
            db.executescript("CREATE TABLE people(id INTEGER PRIMARY KEY,name TEXT NOT NULL,barcode TEXT UNIQUE NOT NULL); CREATE TABLE events(id INTEGER PRIMARY KEY,person_id INTEGER NOT NULL REFERENCES people(id),action TEXT NOT NULL,timestamp TEXT NOT NULL);")
            db.execute('INSERT INTO people VALUES(1,?,?)',('Legacy Person','000001'))
            db.execute('INSERT INTO events VALUES(1,1,?,?)',('in','2026-10-01T01:00:00+00:00'))
        app.initialize();app.initialize();record=self.get(1)
        self.assertEqual(record['version'],0);self.assertEqual(record['profile'],{})
        record=app.update_person(1,{**record,'profile':{'department':'Assembly'}})
        self.assertEqual(record['version'],1)
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
    def test_duplicates_and_invalid_profiles_rollback_full_import(self):
        app.add_people([{'name':'Existing','profile':{'employee_id':'001'}}])
        with self.assertRaisesRegex(ValueError,'Employee ID'):
            app.add_people([{'name':'New A'},{'name':'New B','profile':{'employee_id':'001'}}])
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM people').fetchone()[0],1)
        second=app.add_people([{'name':'Another','profile':{'employee_id':'002'}}])[0]
        record=self.get(second['id'])
        with self.assertRaisesRegex(ValueError,'Employee ID'):
            app.update_person(second['id'],{**record,'name':'Should roll back','profile':{'employee_id':'001'}})
        self.assertEqual(self.get(second['id'])['name'],'Another')
        self.assertEqual(self.get(second['id'])['version'],1)
        for profile in [{'birth_date':'2026-02-30'},{'unexpected':'value'},{'height_cm':'nan'},{'weight_kg':'-1'},{'sss':123}]:
            with self.assertRaises(ValueError):profiles.validate(profile)
    def test_stale_updates_and_barcode_changes_rejected(self):
        person=app.add_people([{'name':'Person'}])[0];record=self.get(person['id'])
        app.update_person(person['id'],{**record,'profile':{'position':'Operator'}})
        with self.assertRaisesRegex(ValueError,'another session'):app.update_person(person['id'],record)
        record=self.get(person['id'])
        with self.assertRaisesRegex(ValueError,'barcode'):app.update_person(person['id'],{**record,'barcode':'999999'})
    def test_image_validation(self):
        self.assertEqual(profiles.validate_image(IMAGE)[0],'image/png')
        for image in ['data:image/svg+xml;base64,PHN2Zz4=','data:image/png;base64,aGVsbG8=','data:image/jpeg;base64,%%%','x'*1400001]:
            with self.assertRaises(ValueError):profiles.validate_image(image)

class ProfileAccessTests(HTTPFixture):
    # Reuse the authenticated HTTP fixture, without rerunning inherited tests here.
    def test_profile_endpoints_require_admin_and_never_leak_to_kiosk(self):
        person=app.add_people([{'name':'Test Person','barcode':'000001','profile':{'sss':'PRIVATE-ID','emergency_phone':'PRIVATE-PHONE'},'photo':IMAGE}])[0]
        url=f'/api/people/{person["id"]}'
        for path in [url,url+'/image/photo',url+'/image/signature']:
            self.assertEqual(self.request(path)[0],401)
        self.assertEqual(self.request(url,{'name':'Intruder'})[0],401)
        app.scan(person['barcode'])
        for path in ['/api/desk','/']:
            content=self.request(path)[1]
            self.assertNotIn(b'PRIVATE-ID',content);self.assertNotIn(b'PRIVATE-PHONE',content)
        self.request('/api/login',{'password':'test-fixture-password'},self.browser)
        status,body=self.request(url,browser=self.browser);self.assertEqual(status,200)
        record=json.loads(body);self.assertEqual(record['profile']['sss'],'PRIVATE-ID')
        self.assertEqual(self.request(url+'/image/photo',browser=self.browser)[0],200)
        record['profile']['department']='Testing'
        self.assertEqual(self.request(url,record,self.browser)[0],200)
        self.assertEqual(self.request(url,record,self.browser)[0],400)
        self.assertNotIn(b'PRIVATE-ID',self.request('/api/state',browser=self.browser)[1])
        self.request('/api/logout',{},self.browser)
        self.assertEqual(self.request(url+'/image/photo',browser=self.browser)[0],401)

