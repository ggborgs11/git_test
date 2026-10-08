"""Admin attendance filters, monthly daily summaries, and CSV exports."""
import csv
import io
import json
import re
from calendar import monthrange
from datetime import datetime, timedelta, timezone


def report(db, local, query):
    day=query.get('date');month=query.get('month')
    if 'month' in query and not month:month=datetime.now(local).strftime('%Y-%m')
    if day and month:raise ValueError('Choose either a date or a month.')
    if month:
        if not re.fullmatch(r'\d{4}-\d{2}',month):raise ValueError('Use a month in YYYY-MM format.')
        start=datetime.strptime(month+'-01','%Y-%m-%d').replace(tzinfo=local)
        try:end=start+timedelta(days=monthrange(start.year,start.month)[1])
        except OverflowError:raise ValueError('Date range is outside the supported calendar.') from None
    else:
        day=day or datetime.now(local).strftime('%Y-%m-%d')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):raise ValueError('Use a date in YYYY-MM-DD format.')
        start=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=local)
        try:end=start+timedelta(days=1)
        except OverflowError:raise ValueError('Date range is outside the supported calendar.') from None
    people=[]
    for row in db.execute('SELECT p.id,p.name,p.barcode,f.details FROM people p LEFT JOIN employee_profiles f ON f.person_id=p.id ORDER BY p.name COLLATE NOCASE'):
        details=json.loads(row['details']) if row['details'] else {}
        people.append({'id':row['id'],'name':row['name'],'barcode':row['barcode'],'department':details.get('department','').strip()})
    by_id={p['id']:p for p in people}
    department=query.get('department')
    selected=None
    if query.get('person'):
        if not query['person'].isdigit():raise ValueError('Invalid employee selection.')
        selected=by_id.get(int(query['person']))
        if not selected:raise ValueError('Selected employee not found.')
        if department is not None and selected['department']!=department:
            raise ValueError('Selected employee is not in the selected department.')
    sort=query.get('sort','time')
    if sort not in ('time','department','person'):raise ValueError('Invalid attendance sort.')
    records=[]
    sql='SELECT id,person_id,action,timestamp FROM events WHERE timestamp>=? AND timestamp<?'
    args=[start.astimezone(timezone.utc).isoformat(),end.astimezone(timezone.utc).isoformat()]
    if selected:sql+=' AND person_id=?';args.append(selected['id'])
    for row in db.execute(sql+' ORDER BY timestamp DESC,id DESC',args):
        person=by_id[row['person_id']]
        if department is not None and person['department']!=department:continue
        stamp=datetime.fromisoformat(row['timestamp']).astimezone(local)
        records.append({'id':row['id'],'person_id':person['id'],'name':person['name'],'barcode':person['barcode'],
                        'department':person['department'],'action':row['action'],'timestamp':row['timestamp'],'date':stamp.strftime('%Y-%m-%d')})
    # Stable grouping retains newest-first order within each employee.
    if sort=='department':records.sort(key=lambda r:(r['department'].casefold(),r['name'].casefold(),r['person_id']))
    elif sort=='person':records.sort(key=lambda r:(r['name'].casefold(),r['person_id']))
    days=[]
    if month and selected:
        grouped={}
        for record in records:grouped.setdefault(record['date'],[]).append(record)
        current=start
        while current<end:
            date=current.strftime('%Y-%m-%d');scans=grouped.get(date,[])
            ins=[r['timestamp'] for r in scans if r['action']=='in'];outs=[r['timestamp'] for r in scans if r['action']=='out']
            days.append({'date':date,'first_in':min(ins) if ins else None,'last_out':max(outs) if outs else None,'scans':len(scans)})
            current+=timedelta(days=1)
    return {'records':records,'days':days,'people':people,'departments':sorted({p['department'] for p in people},key=str.casefold),
            'employee':selected,'timezone':str(local),'today':datetime.now(local).strftime('%Y-%m-%d'),
            'period':month or day,'mode':'month' if month else 'day','sort':sort}


def safe_cell(value):
    text=str(value or '')
    if text.startswith(('\t','\r','\n')) or text.lstrip().startswith(('=','+','-','@')):return "'"+text
    return text


def export_csv(data,local,summary=False):
    output=io.StringIO();writer=csv.writer(output)
    def clock(stamp):return datetime.fromisoformat(stamp).astimezone(local).strftime('%H:%M:%S') if stamp else ''
    if summary:
        if data['mode']!='month' or not data['employee']:raise ValueError('A monthly summary requires an employee selection.')
        person=data['employee']
        writer.writerow(['Date','Name','Department',f'First Time In ({local})',f'Last Time Out ({local})','Scans'])
        for day in data['days']:writer.writerow([day['date'],safe_cell(person['name']),safe_cell(person['department']),clock(day['first_in']),clock(day['last_out']),day['scans']])
    else:
        writer.writerow(['Date','Name','Department','Barcode','Action',f'Time ({local})'])
        for record in data['records']:writer.writerow([record['date'],safe_cell(record['name']),safe_cell(record['department']),record['barcode'] or '',
                                                       'Time In' if record['action']=='in' else 'Time Out',clock(record['timestamp'])])
    return output.getvalue().encode('utf-8-sig')
