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

1. Sign in at `/admin`, open **People & badges**, and use **Add employee** with Last name, First name, and an optional Department. You can also import employees using CSV. In **People & badges**, select **Assign barcode** beside an employee, then enter a barcode or choose **Generate & assign barcode**. CSV imports accept `name,barcode`; a blank barcode leaves the employee unassigned. Existing barcodes must contain 1–20 digits; leading zeros are preserved. Imports are atomic: an invalid or duplicate entry rejects the entire batch.
2. Print badges after assigning barcodes. Employees without barcodes are excluded. The current search filters the badges to print. Badges use Code 39; enable Code 39 on your scanner. Disable transmission of the start/stop asterisks, and configure the scanner to send Enter after each scan. Print at actual size and verify one badge with the physical scanner before printing all 300.
3. At **Scan desk**, scan your badge. No Time In/Out selection is needed. A person who is Out (or has no records) is timed in; a person who is In is timed out. The scanner must send Enter after each scan. The scanner capture field is visually hidden; there is no manual barcode box or Record button. It clears and stays focused on the public screen. Keep the browser window active while scanning. A keyboard-emulating USB scanner sends the barcode followed by Enter. Repeat scans of the same person within 30 seconds are ignored without changing status. Other people can scan immediately. The 30-second window is checked on the server and persists across restarts. Status carries across midnight for overnight shifts; there is no scheduled automatic Time Out. A missed scan can leave the next action incorrect, so review unmatched attendance before using scan-only mode. This version does not include an admin attendance correction tool.
4. In **Attendance records**, choose one day or a whole month, filter by department, select an employee, and sort the scan log by newest first, department, or employee name. Selecting an employee preserves the selected period. The scan desk always shows today's activity and current attendance. Other browsers refresh every 10 seconds.

Attendance uses server timestamps, stored in UTC and displayed in **Asia/Manila**. Set `ATTENDANCE_TIMEZONE` to another IANA timezone before starting if needed. Keep the server clock accurate.

## Employee data

The 201-file screens have been removed. Existing employee details, photos, signatures, barcodes, and attendance data remain stored unchanged. Import employees from People & badges using CSV columns `name,barcode`, with names in `Last name, First name` format. Existing separate surname/given-name fields are used for attendance display; legacy names without those fields remain unchanged.

Attendance records support inclusive **Start date** and **End date** filters in the attendance timezone. Both dates are included, and CSV exports use the same filters. One-day and whole-month views remain available; selecting an employee preserves the chosen range.

## Department and monthly attendance

Department values come from existing stored employee details. Attendance filters and historical records use the employee’s current department; earlier department assignments are not snapshotted. Choose **No department assigned** to see employees without a department. Changing department clears a person selection that no longer belongs to it.

Select an employee and a month to see every calendar day, with the first Time In, last Time Out, and number of scans. A separate scan log lists every matching scan. Days with no records show **No scans**, not an absence designation. Overnight shifts can have their Time Out on the following calendar day; the summary is not a calculation of paid hours.

**Export monthly CSV** exports the selected employee’s daily summary. **Export scan log** exports every matching scan. With all employees selected, the main CSV export contains the filtered and sorted scan log. All dates/times use the configured attendance timezone, defaulting to Asia/Manila. Exports honor department, person, and period filters.

## Update an existing installation

Stop the app with Ctrl+C. Back up the existing `data` folder. Copy the updated `app.py`, `profiles.py`, `attendance.py`, `requirements.txt`, and `static` folder into your existing app folder. Keep your existing `data` folder intact: it contains all people and attendance records. Install requirements and run `py app.py` again. Choose your admin password when prompted.

To change a forgotten password, stop the server and run `py app.py --set-admin-password` on the server computer, then restart. The password is saved as a salted hash in `data/admin-password.json`. Anyone with control of the server computer/files can reset it; this protects browser access, not access to the computer itself.

## Data and backups

Records persist in `data/attendance.db` (ignored by Git). Set `ATTENDANCE_DB` to use another file. Stop the server before copying the database for backup; keep backups private. Restarting the app retains all records. Do not use test/demo registrations in the real database.

## Validate

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
node tests/test_delete_ui.js
node tests/test_edit_ui.js
node tests/test_bulk_ui.js
node --check static/bulk.js
```

Tests cover 300 people, automatic In/Out transitions, the 30-second duplicate window, concurrent scans, restart persistence, atomic import, unknown barcodes, leading zeros, and Manila date boundaries. Access tests cover admin login/logout, session expiry, protected APIs, and the public kiosk. 201-file tests cover creation/editing, legacy database upgrades, employee ID uniqueness, image validation/removal, stale edit protection, profile/image access controls, barcode-free creation, deferred manual/generated assignment, uniqueness, and migration of older databases. Attendance report tests cover department grouping/filtering, employee/month selection, Manila month boundaries, leap months, full-day summaries, matching CSV exports, and access controls. Physical scanner and printer verification require your devices.

In **People & badges**, choose **Delete** beside an employee to permanently remove that employee and their attendance records, details, images, and barcode. An on-page confirmation is required: choose **Delete permanently** to proceed or **Cancel** to keep the employee. Other employees are unchanged. Back up the database before deleting records you may need later.

The **All employees** tab provides a searchable, scrollable directory with a **Delete** button beside each employee. Click **Delete permanently** in the on-page confirmation to permanently delete the selected employee and their attendance records.

To correct a name or assign a department after CSV import, open **All employees → Edit**, change the name and/or department, and choose **Save changes**. Existing barcodes, attendance, images, and other stored employee details are preserved.

For bulk department assignment, open **All employees**, tick multiple employees (or use **Select matching employees** after searching), enter the department once, and choose **Apply department to selected**. The selected count includes employees selected under earlier searches. **Clear selection** unchecks everyone. Only department changes; attendance and other employee details remain intact.

To generate barcodes automatically for multiple employees, open **All employees**, tick employees or choose **Select matching employees**, then click **Auto-assign barcodes**. Each employee without a barcode gets a unique numeric barcode. Existing barcodes are skipped and preserved. Print the resulting badges in **People & badges**.

In **All employees**, **Select all employees** selects the entire directory, including employees hidden by a search. Use it before **Auto-assign barcodes** or bulk department assignment. **Clear selection** unchecks everyone.
