# Cavite Nagano Seiko Inc. attendance

A simple barcode attendance web app for a 300-person team. Uses Python 3.12+ and SQLite. Windows also needs the `tzdata` package.

## Run

1. Install Python 3.12 or newer from https://www.python.org/downloads/.
2. Download this repository using **Code → Download ZIP** and extract it.
3. Open a terminal in the extracted folder (on Windows, type `cmd` in the folder address bar and press Enter).
4. Install timezone data (required on Windows):

```bat
py -m pip install -r requirements.txt
```

5. Start the app:

```bat
py app.py
```

On macOS/Linux, use `python3 app.py` instead. Keep the terminal open while using the app. On the first run, choose and confirm an admin password of at least 8 characters. The password will not appear as you type.

Open `http://127.0.0.1:8000` in the browser on the same computer. For a trusted local network, run `python3 app.py --host 0.0.0.0` and open the server computer's LAN address on port 8000. The main page is a public scan station with no navigation tabs. Open `http://127.0.0.1:8000/admin` to sign in and manage people or export records. Admin sessions expire after one hour. Click **Log out** before leaving a shared computer; closing a tab does not log you out. The public screen displays today’s latest eight scans, names, barcodes, and attendance totals. Scanning is intentionally public. Keep the app on a trusted network; use HTTPS before Internet deployment.

## Use

1. Sign in at `/admin`, then open **People & badges**, add people individually or upload CSV with `name,barcode` headers. Omit barcode values to generate unique numbers. Existing barcodes must contain 1–20 digits; leading zeros are preserved. Imports are atomic: an invalid or duplicate entry rejects the entire batch.
2. Print badges. The current search filters the badges to print. Badges use Code 39; enable Code 39 on your scanner. Disable transmission of the start/stop asterisks, and configure the scanner to send Enter after each scan. Print at actual size and verify one badge with the physical scanner before printing all 300.
3. At **Scan desk**, scan your badge. No Time In/Out selection is needed. A person who is Out (or has no records) is timed in; a person who is In is timed out. The scanner must send Enter after each scan. The scanner capture field is visually hidden; there is no manual barcode box or Record button. It clears and stays focused on the public screen. Keep the browser window active while scanning. A keyboard-emulating USB scanner sends the barcode followed by Enter. Repeat scans of the same person within 30 seconds are ignored without changing status. Other people can scan immediately. The 30-second window is checked on the server and persists across restarts. Status carries across midnight for overnight shifts; there is no scheduled automatic Time Out. A missed scan can leave the next action incorrect, so review unmatched attendance before using scan-only mode. This version does not include an admin attendance correction tool.
4. Select a date in **Attendance records** and export CSV. The scan desk always shows today's activity and current attendance. Other browsers refresh every 10 seconds.

Attendance uses server timestamps, stored in UTC and displayed in **Asia/Manila**. Set `ATTENDANCE_TIMEZONE` to another IANA timezone before starting if needed. Keep the server clock accurate.

## Employee 201 files

Sign in at `/admin` and open **People & badges**. **Add a person** now includes a 201 file with six sections: personal information, educational background, family background, employment history, other information, and work information. Only the full name is required. Education, family, employment history, and other information are free-text sections. Names can be typed directly or generated from first/middle/last name and suffix.

Personal information includes employee ID, addresses, contact details, birth details, emergency contact, PhilHealth/SSS/TIN/Pag-IBIG numbers, photo, and signature. Employee IDs are optional but must be unique when supplied; IDs and phone numbers are stored as text to preserve leading zeros. Employee ID is separate from the attendance barcode.

Upload PNG or JPEG photos/signatures up to 1 MB each. Profiles and images are available only after admin login; they are not included in the public kiosk, badge printing, or attendance CSV exports. The public kiosk still shows employee names and barcodes as before.

To view or edit an existing employee, choose **201 file** beside their name. Save with **Save 201 file**. Existing barcodes are read-only so attendance stays attached to the same person. Concurrent edits are checked: if another admin saved first, reopen the file before saving. **New person** starts a new record. CSV imports still accept `name,barcode`; complete their 201 files afterward.

Existing installations upgrade their database automatically on startup, adding separate profile/image tables while retaining people and attendance. Profile details and images are stored in the same `data/attendance.db` file; include it in private backups. The server owner can access the database directly, so admin login controls browser access rather than encrypting the file.

## Update an existing installation

Stop the app with Ctrl+C. Back up the existing `data` folder. Copy the updated `app.py`, `profiles.py`, `requirements.txt`, and `static` folder into your existing app folder. Keep your existing `data` folder intact: it contains all people and attendance records. Install requirements and run `py app.py` again. Choose your admin password when prompted.

To change a forgotten password, stop the server and run `py app.py --set-admin-password` on the server computer, then restart. The password is saved as a salted hash in `data/admin-password.json`. Anyone with control of the server computer/files can reset it; this protects browser access, not access to the computer itself.

## Data and backups

Records persist in `data/attendance.db` (ignored by Git). Set `ATTENDANCE_DB` to use another file. Stop the server before copying the database for backup; keep backups private. Restarting the app retains all records. Do not use test/demo registrations in the real database.

## Validate

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
```

Tests cover 300 people, automatic In/Out transitions, the 30-second duplicate window, concurrent scans, restart persistence, atomic import, unknown barcodes, leading zeros, and Manila date boundaries. Access tests cover admin login/logout, session expiry, protected APIs, and the public kiosk. 201-file tests cover creation/editing, legacy database upgrades, employee ID uniqueness, image validation/removal, stale edit protection, and profile/image access controls. Physical scanner and printer verification require your devices.
