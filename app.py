"""Small attendance server. Run: python3 app.py"""
import argparse
import csv
import io
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
DB = Path(os.environ.get('ATTENDANCE_DB', str(ROOT / 'data' / 'attendance.db')))
LOCAL = ZoneInfo(os.environ.get('ATTENDANCE_TIMEZONE', 'Asia/Manila'))
LOCK = threading.Lock()


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
    def reply(self, status, data, mime='application/json; charset=utf-8'):
        body = json.dumps(data).encode() if mime.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        url = urlparse(self.path)
        try:
            if url.path in ('/api/state', '/api/export'):
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
            files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
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
            if self.path == '/api/people':
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
    args = parser.parse_args()
    initialize()
    print(f'Attendance app: http://{args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
