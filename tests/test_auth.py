import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import http.cookiejar
from pathlib import Path
from http.server import ThreadingHTTPServer
import app


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = app.DB
        app.DB = Path(self.temp.name) / 'attendance.db'
        app.initialize()
        app.set_admin_password('test-fixture-password')
        app.LOGIN_ATTEMPTS.clear()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        app.DB = self.previous
        self.temp.cleanup()

    def request(self, path, body=None, browser=None, origin=None):
        headers = {'Content-Type':'application/json'}
        if origin: headers['Origin'] = origin
        request=urllib.request.Request(self.base+path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            response=(browser or urllib.request.build_opener()).open(request)
        except urllib.error.HTTPError as response:
            return response.code, response.read()
        with response:
            return response.status, response.read()

    def test_public_screen_does_not_expose_admin_data_or_controls(self):
        app.add_people([{'name':'Private directory entry'}])
        status, html = self.request('/')
        self.assertEqual(status, 200)
        self.assertNotIn(b'<nav',html)
        self.assertNotIn(b'person-form',html)
        self.assertNotIn(b'records-body',html)
        self.assertNotIn(b'People & badges',html)
        self.assertIn(b'scan-form',html)
        for path in ['/api/state','/api/state?date=2026-10-06','/api/export']:
            self.assertEqual(self.request(path)[0],401)
        self.assertEqual(self.request('/api/people',{'people':[{'name':'Intruder'}]})[0],401)
        state=json.loads(self.request('/api/desk')[1])
        self.assertEqual(state['total'],1)
        self.assertNotIn('people',state)
        self.assertNotIn('Private directory entry',json.dumps(state))

    def test_login_admin_operations_and_logout(self):
        self.assertIn(b'Admin login',self.request('/admin')[1])
        self.assertEqual(self.request('/api/login',{'password':'wrong-password'},self.browser)[0],401)
        self.assertEqual(self.request('/api/login',{'password':'test-fixture-password'},self.browser)[0],200)
        self.assertIn(b'People & badges',self.request('/admin',browser=self.browser)[1])
        self.assertEqual(self.request('/api/people',{'people':[{'name':'Alex','barcode':'000001'}]},self.browser)[0],201)
        # Kiosk scanning works without an admin cookie.
        self.assertEqual(self.request('/api/scan',{'barcode':'000001'})[0],201)
        status,body=self.request('/api/scan',{'barcode':'000001','action':'out'})
        self.assertEqual(status,200)
        self.assertTrue(json.loads(body)['duplicate'])
        self.assertEqual(json.loads(body)['action'],'in')
        self.assertEqual(self.request('/api/state',browser=self.browser)[0],200)
        self.assertIn(b'Alex',self.request('/api/export',browser=self.browser)[1])
        self.assertEqual(self.request('/api/logout',{},self.browser)[0],200)
        self.assertEqual(self.request('/api/state',browser=self.browser)[0],401)
        self.assertIn(b'Admin login',self.request('/admin',browser=self.browser)[1])

    def test_cross_origin_and_expired_session(self):
        self.assertEqual(self.request('/api/login',{'password':'test-fixture-password'},origin='http://other.example')[0],403)
        self.request('/api/login',{'password':'test-fixture-password'},self.browser)
        with app.AUTH_LOCK:
            for token in app.SESSIONS: app.SESSIONS[token]=0
        self.assertEqual(self.request('/api/state',browser=self.browser)[0],401)

    def test_rate_limit_and_recent_events_only(self):
        for _ in range(5):
            self.assertEqual(self.request('/api/login',{'password':'invalid'})[0],401)
        self.assertEqual(self.request('/api/login',{'password':'test-fixture-password'})[0],429)
        app.add_people([{'name':'Alex','barcode':'000001'}])
        from datetime import datetime, timedelta, timezone
        base=datetime.now(timezone.utc)-timedelta(minutes=10)
        with app.connect() as db:
            for index in range(10):
                db.execute('INSERT INTO events(person_id,action,timestamp) VALUES (?,?,?)',
                           (1,'in' if index%2==0 else 'out',(base+timedelta(seconds=index*31)).isoformat()))
        state=json.loads(self.request('/api/desk')[1])
        self.assertEqual(state['scans'],10)
        self.assertEqual(len(state['events']),8)
        self.assertEqual(state['inside'],0)

if __name__ == '__main__': unittest.main()
