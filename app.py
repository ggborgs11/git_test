"""Small attendance server. Run: python3 app.py"""
import argparse
import getpass
import hashlib
import hmac
import secrets
import time
from http.cookies import SimpleCookie
import csv
import io
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).parent
DB = Path(os.environ.get('ATTENDANCE_DB', str(ROOT / 'data' / 'attendance.db')))
try:
    LOCAL = ZoneInfo(os.environ.get('ATTENDANCE_TIMEZONE', 'Asia/Manila'))
except ZoneInfoNotFoundError:
    raise SystemExit('Timezone data is missing. Run: python -m pip install tzdata') from None
LOCK = threading.Lock()
AUTH_LOCK = threading.Lock()
SESSIONS = {}
LOGIN_ATTEMPTS = {}


def password_file():
    return DB.parent / 'admin-password.json'


def set_admin_password(password):
    if len(password) < 8 or len(password) > 256:
        raise ValueError('Use an admin password of 8–256 characters.')
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    password_file().write_text(json.dumps({'salt': salt, 'hash': digest}))
    password_file().chmod(0o600)
    with AUTH_LOCK:
        SESSIONS.clear()


def check_password(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 256 or not password_file().is_file():
        return False
    saved = json.loads(password_file().read_text())
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(saved['salt']), 600000).hex()
    return hmac.compare_digest(digest, saved['hash'])



def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS people (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, barcode TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES people(id),
          action TEXT NOT NULL CHECK(action IN ('in','out')), timestamp TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_person ON events(person_id, id);
        ''')


def add_people(rows):
    if not rows or len(rows) > 1000:
        raise ValueError('Provide between 1 and 1,000 people.')
    with LOCK, connect() as db:
        result = []
        for row in rows:
            name = str(row.get('name', '')).strip()
            barcode = str(row.get('barcode', '')).strip()
            if not name or len(name) > 100:
                raise ValueError('Each name must contain 1–100 characters.')
            if not barcode:
                next_id = db.execute('SELECT COALESCE(MAX(id), 0)+1 FROM people').fetchone()[0]
                number = next_id
                barcode = f'{number:06d}'
                while db.execute('SELECT 1 FROM people WHERE barcode=?', (barcode,)).fetchone():
                    number += 1
                    barcode = f'{number:06d}'
            if not barcode.isascii() or not barcode.isdigit() or not 1 <= len(barcode) <= 20:
                raise ValueError('Barcodes must contain 1–20 digits. Leading zeros are preserved.')
            try:
                cursor = db.execute('INSERT INTO people(name, barcode) VALUES (?,?)', (name, barcode))
            except sqlite3.IntegrityError:
                raise ValueError(f'Barcode {barcode} is already registered.') from None
            result.append({'id': cursor.lastrowid, 'name': name, 'barcode': barcode})
        return result


def scan(barcode, action):
    if action not in ('in', 'out'):
        raise ValueError('Choose Time In or Time Out.')
    with LOCK, connect() as db:
        person = db.execute('SELECT * FROM people WHERE barcode=?', (barcode,)).fetchone()
        if not person:
            raise ValueError('Unknown barcode. Register this person first.')
        last = db.execute('SELECT * FROM events WHERE person_id=? ORDER BY id DESC LIMIT 1', (person['id'],)).fetchone()
        if action == 'out' and (not last or last['action'] == 'out'):
            raise ValueError(f"{person['name']} is already out. Record Time In first.")
        if action == 'in' and last and last['action'] == 'in':
            raise ValueError(f"{person['name']} is already in. Duplicate scan ignored.")
        timestamp = datetime.now(timezone.utc).isoformat()
        db.execute('INSERT INTO events(person_id,action,timestamp) VALUES (?,?,?)', (person['id'], action, timestamp))
        return {'name': person['name'], 'action': action, 'timestamp': timestamp}


def snapshot(day):
    datetime.strptime(day, '%Y-%m-%d')
    with connect() as db:
        people = [dict(row) for row in db.execute('''SELECT p.*, COALESCE((SELECT action FROM events
            WHERE person_id=p.id ORDER BY id DESC LIMIT 1),'out') AS status FROM people p ORDER BY name COLLATE NOCASE''')]
        start = datetime.strptime(day, '%Y-%m-%d').replace(tzinfo=LOCAL)
        from datetime import timedelta
        end = start + timedelta(days=1)
        events = [dict(row) for row in db.execute('''SELECT e.id,p.name,p.barcode,e.action,e.timestamp
            FROM events e JOIN people p ON p.id=e.person_id WHERE timestamp>=? AND timestamp<? ORDER BY e.id DESC''',
            (start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()))]
    return {'people': people, 'events': events, 'timezone': str(LOCAL), 'today': datetime.now(LOCAL).strftime('%Y-%m-%d')}


class Handler(BaseHTTPRequestHandler):
    def authenticated(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie['clockwork_admin'].value if 'clockwork_admin' in cookie else ''
        except Exception:
            return False
        with AUTH_LOCK:
            expiry = SESSIONS.get(token, 0)
            if expiry <= time.time():
                SESSIONS.pop(token, None)
                return False
            return True

    def reply(self, status, data, mime='application/json; charset=utf-8', cookie=None):
        body = json.dumps(data).encode() if mime.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        url = urlparse(self.path)
        try:
            if url.path == '/api/desk':
                state = snapshot(datetime.now(LOCAL).strftime('%Y-%m-%d'))
                return self.reply(200, {'total': len(state['people']),
                    'inside': sum(p['status'] == 'in' for p in state['people']),
                    'scans': len(state['events']), 'events': state['events'][:8],
                    'timezone': state['timezone'], 'today': state['today']})
            if url.path in ('/api/state', '/api/export'):
                if not self.authenticated():
                    return self.reply(401, {'error': 'Admin login required.'})
                day = parse_qs(url.query).get('date', [datetime.now(LOCAL).strftime('%Y-%m-%d')])[0]
                state = snapshot(day)
                if url.path == '/api/state':
                    return self.reply(200, state)
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Name', 'Barcode', 'Action', f'Time ({LOCAL})'])
                for event in reversed(state['events']):
                    name = event['name']
                    if name.startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
                        name = "'" + name
                    writer.writerow([name, event['barcode'], 'Time In' if event['action']=='in' else 'Time Out',
                                     datetime.fromisoformat(event['timestamp']).astimezone(LOCAL).strftime('%Y-%m-%d %H:%M:%S')])
                return self.reply(200, output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8')
            if url.path in ('/admin', '/admin/'):
                filename = 'index.html' if self.authenticated() else 'login.html'
                return self.reply(200, (ROOT / 'static' / filename).read_bytes(), 'text/html; charset=utf-8')
            files = {'/': ('kiosk.html', 'text/html'), '/login.js': ('login.js', 'text/javascript'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
            if url.path not in files:
                return self.reply(404, {'error': 'Not found'})
            filename, mime = files[url.path]
            return self.reply(200, (ROOT / 'static' / filename).read_bytes(), mime + '; charset=utf-8')
        except ValueError as error:
            self.reply(400, {'error': str(error)})

    def do_POST(self):
        # Browser writes must originate from this server; no cross-origin writes.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.reply(403, {'error': 'Cross-origin requests are not allowed.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 200000:
                raise ValueError('Request is empty or too large.')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Use JSON requests.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object.')
            if self.path == '/api/login':
                address = self.client_address[0]
                with AUTH_LOCK:
                    now = time.time()
                    attempts, deadline = LOGIN_ATTEMPTS.get(address, (0, now + 300))
                    if now >= deadline:
                        attempts, deadline = 0, now + 300
                    if attempts >= 5:
                        return self.reply(429, {'error': 'Too many attempts. Try again in five minutes.'})
                    LOGIN_ATTEMPTS[address] = (attempts + 1, deadline)
                if not check_password(data.get('password')):
                    return self.reply(401, {'error': 'Incorrect admin password.'})
                token = secrets.token_urlsafe(32)
                with AUTH_LOCK:
                    LOGIN_ATTEMPTS.pop(address, None)
                    for old in list(SESSIONS):
                        if SESSIONS[old] <= time.time():
                            del SESSIONS[old]
                    SESSIONS[token] = time.time() + 3600
                return self.reply(200, {'ok': True}, cookie=f'clockwork_admin={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=3600')
            if self.path == '/api/logout':
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                if 'clockwork_admin' in cookie:
                    with AUTH_LOCK:
                        SESSIONS.pop(cookie['clockwork_admin'].value, None)
                return self.reply(200, {'ok': True}, cookie='clockwork_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
            if self.path == '/api/people':
                if not self.authenticated():
                    return self.reply(401, {'error': 'Admin login required.'})
                rows = data.get('people')
                if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                    raise ValueError('Expected a list of people.')
                return self.reply(201, {'people': add_people(rows)})
            if self.path == '/api/scan':
                return self.reply(201, scan(str(data.get('barcode', '')).strip(), data.get('action')))
            self.reply(404, {'error': 'Not found'})
        except (ValueError, TypeError) as error:
            self.reply(400, {'error': str(error)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--set-admin-password', action='store_true', help='Change the admin password and exit')
    args = parser.parse_args()
    initialize()
    if args.set_admin_password or not password_file().is_file():
        print('Set your admin password (at least 8 characters). It will not appear as you type.', flush=True)
        while True:
            try:
                password = getpass.getpass('Admin password: ')
                confirmation = getpass.getpass('Confirm password: ')
                if password != confirmation:
                    print('Passwords do not match. Try again.')
                    continue
                set_admin_password(password)
                break
            except ValueError as error:
                print(error)
            except (EOFError, KeyboardInterrupt):
                raise SystemExit('Admin password setup cancelled.') from None
        if args.set_admin_password:
            raise SystemExit('Admin password updated. Restart the server to sign out existing sessions.')
    print(f'Attendance app: http://{args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
