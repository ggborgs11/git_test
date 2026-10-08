import csv
import io
import json
from datetime import datetime,timezone
import app
import attendance
from test_auth import HTTPFixture

class ReportTests(HTTPFixture):
    def setUp(self):
        super().setUp()
        self.people=app.add_people([
            {'name':'Alice','barcode':'000001','profile':{'department':'Assembly'}},
            {'name':'Bob','barcode':'000002','profile':{'department':'Quality'}},
            {'name':'Carol','barcode':'000003'},
            {'name':'No scans','profile':{'department':'Assembly'}},
        ])
        with app.connect() as db:
            for person,action,stamp in [
                (1,'in','2026-09-30T16:00:00+00:00'), # October 1 Manila
                (1,'out','2026-10-01T09:00:00+00:00'),
                (1,'in','2026-10-15T00:00:00+00:00'),
                (1,'out','2026-10-15T09:00:00+00:00'),
                (1,'out','2026-10-31T16:00:00+00:00'), # November 1, excluded
                (2,'in','2026-10-01T01:00:00+00:00'),
                (3,'in','2026-10-01T02:00:00+00:00')]:
                db.execute('INSERT INTO events(person_id,action,timestamp) VALUES (?,?,?)',(person,action,stamp))
    def report(self,query):
        with app.connect() as db:return attendance.report(db,app.LOCAL,query)
    def test_month_per_person_and_manila_boundaries(self):
        result=self.report({'month':'2026-10','person':'1'})
        self.assertEqual(len(result['records']),4)
        self.assertEqual(len(result['days']),31)
        self.assertEqual(result['days'][0]['scans'],2)
        self.assertEqual(result['days'][1]['scans'],0)
        self.assertIsNone(result['days'][1]['first_in'])
        self.assertEqual(result['days'][14]['scans'],2)
        self.assertEqual(result['days'][-1]['date'],'2026-10-31')
        self.assertEqual(result['employee']['name'],'Alice')
        self.assertEqual(len(self.report({'month':'2024-02','person':'1'})['days']),29)
    def test_department_filters_and_group_sort(self):
        result=self.report({'date':'2026-10-01','department':'Assembly'})
        self.assertEqual({r['name'] for r in result['records']},{'Alice'})
        self.assertEqual(len(result['records']),2)
        self.assertEqual([r['name'] for r in self.report({'date':'2026-10-01','department':''})['records']],['Carol'])
        grouped=self.report({'date':'2026-10-01','sort':'department'})['records']
        self.assertEqual([r['department'] for r in grouped],['','Assembly','Assembly','Quality'])
        self.assertEqual({p['name'] for p in result['people']},{'Alice','Bob','Carol','No scans'})
        self.assertEqual(self.report({'month':'2026-10','person':'4'})['records'],[])
    def test_surname_sort_uses_profile_and_preserves_saved_names(self):
        with app.connect() as db:
            db.execute('UPDATE employee_profiles SET details=? WHERE person_id=1',
                       (json.dumps({'last_name':'Zulu','first_name':'Alice','department':'Assembly'}),))
            db.execute('UPDATE employee_profiles SET details=? WHERE person_id=2',
                       (json.dumps({'last_name':'Dela Cruz','first_name':'Bob','department':'Quality'}),))
        result=self.report({'date':'2026-10-01','sort':'last_name'})
        self.assertEqual([r['name'] for r in result['records']],['Carol','Dela Cruz, Bob','Zulu, Alice','Zulu, Alice'])
        exported=list(csv.reader(io.StringIO(attendance.export_csv(result,app.LOCAL).decode('utf-8-sig'))))
        self.assertEqual(exported[2][1],'Dela Cruz, Bob')
        self.assertEqual(next(p for p in app.employee_list() if p['id']==2)['sort_name'],'Dela Cruz, Bob')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT name FROM people WHERE id=2').fetchone()['name'],'Bob')
        self.assertEqual(attendance.name_fields('Dalida, Obet',{})['sort_name'],'Dalida, Obet')
        self.assertEqual(attendance.name_fields('Dela Cruz Juan',{})['sort_name'],'Dela Cruz Juan')

    def test_filtered_exports_and_summary(self):
        result=self.report({'month':'2026-10','department':'Assembly','person':'1'})
        raw=list(csv.reader(io.StringIO(attendance.export_csv(result,app.LOCAL).decode('utf-8-sig'))))
        self.assertEqual(len(raw),5);self.assertTrue(all(row[1]=='Alice' and row[2]=='Assembly' for row in raw[1:]))
        self.assertEqual(raw[1][0],'2026-10-15')
        summary=list(csv.reader(io.StringIO(attendance.export_csv(result,app.LOCAL,True).decode('utf-8-sig'))))
        self.assertEqual(len(summary),32);self.assertEqual(summary[1][3],'00:00:00');self.assertEqual(summary[1][4],'17:00:00')
        self.assertEqual(summary[2][3:],["","","0"])
        with self.assertRaises(ValueError):attendance.export_csv(self.report({'date':'2026-10-01'}),app.LOCAL,True)
    def test_invalid_filters_and_export_formula_cells(self):
        for query in [{'month':'2026-13'},{'month':'9999-12'},{'date':'9999-12-31'},{'date':'2026-02-30'},{'date':'2026-10-01','month':'2026-10'},
                      {'person':'999'},{'person':'bad'},{'sort':'sql'},{'department':'Quality','person':'1'}]:
            with self.assertRaises(ValueError):self.report(query)
        self.assertEqual(attendance.safe_cell('=SUM(1,2)'),"'=SUM(1,2)")
        self.assertEqual(attendance.safe_cell(' @formula'),"' @formula")
    def test_report_and_exports_are_admin_only(self):
        for path in ['/api/attendance?month=2026-10&person=1','/api/attendance/export?month=2026-10&person=1&format=summary']:
            self.assertEqual(self.request(path)[0],401)
        self.request('/api/login',{'password':'test-fixture-password'},self.browser)
        status,body=self.request('/api/attendance?month=2026-10&person=1',browser=self.browser)
        self.assertEqual(status,200);self.assertEqual(len(json.loads(body)['days']),31)
        status,body=self.request('/api/attendance/export?month=2026-10&department=Assembly&person=1&format=summary',browser=self.browser)
        self.assertEqual(status,200);self.assertIn(b'Alice,Assembly',body);self.assertNotIn(b'Bob',body)
        self.assertEqual(self.request('/api/attendance?month=invalid',browser=self.browser)[0],400)
        self.request('/api/logout',{},self.browser)
        self.assertEqual(self.request('/api/attendance?month=2026-10',browser=self.browser)[0],401)
