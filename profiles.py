"""Validation and persistence for admin-only employee 201 files."""
import base64
import binascii
import json
from datetime import datetime

# Store IDs and telephone numbers as text to preserve leading zeros.
SECTIONS = [
    ('personal', 'Personal information', [
        ('employee_id','Employee ID','text'), ('last_name','Last name','text'),
        ('first_name','First name','text'), ('middle_name','Middle name','text'),
        ('suffix','Suffix','text'), ('nickname','Nickname','text'),
        ('current_address','Current address','textarea'), ('zip_code','ZIP code','text'),
        ('provincial_address','Provincial address','textarea'), ('provincial_zip','Provincial ZIP code','text'),
        ('contact_number','Contact number','tel'), ('cellphone','Cellphone number','tel'),
        ('email','Email address','email'), ('gender','Gender','text'),
        ('birthplace','Place of birth','text'), ('birth_date','Date of birth','date'),
        ('civil_status','Civil status','text'), ('citizenship','Citizenship','text'),
        ('religion','Religion','text'), ('blood_type','Blood type','text'),
        ('height_cm','Height (cm)','number'), ('weight_kg','Weight (kg)','number'),
        ('emergency_name','Emergency contact name','text'), ('emergency_relationship','Relationship','text'),
        ('emergency_address','Emergency contact address','textarea'), ('emergency_phone','Emergency contact number','tel'),
    ]),
    ('education','Educational background', [('education','Schools, courses, qualifications, and years attended','textarea')]),
    ('family','Family background', [('family','Family members, relationships, and contact details','textarea')]),
    ('employment','Employment history', [('employment_history','Previous employers, roles, dates, and reason for leaving','textarea')]),
    ('other','Other information', [('other_information','Training, skills, certifications, and other notes','textarea')]),
    ('work','Work information', [
        ('department','Department','text'), ('position','Position / job title','text'),
        ('hire_date','Date hired','date'), ('employment_status','Employment status','text'),
        ('shift','Shift / schedule','text'), ('supervisor','Supervisor','text'),
        ('work_notes','Work notes','textarea'),
    ]),
]
GOVERNMENT_FIELDS = [('philhealth','PhilHealth number','text'),('sss','SSS number','text'),
                     ('tin','TIN','text'),('pagibig','Pag-IBIG number','text')]
# Optional fields match the user's 201-file example; never expose them in the kiosk.
FIELDS = {key: kind for _,_,fields in SECTIONS for key,_,kind in fields}
FIELDS.update({key:kind for key,_,kind in GOVERNMENT_FIELDS})


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS employee_profiles (
      person_id INTEGER PRIMARY KEY REFERENCES people(id),
      employee_id TEXT UNIQUE,
      details TEXT NOT NULL,
      version INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS employee_images (
      person_id INTEGER NOT NULL REFERENCES people(id),
      kind TEXT NOT NULL CHECK(kind IN ('photo','signature')),
      mime TEXT NOT NULL, content BLOB NOT NULL,
      PRIMARY KEY(person_id,kind));
    ''')


def validate(details):
    if not isinstance(details,dict) or any(key not in FIELDS for key in details):
        raise ValueError('Invalid 201-file fields.')
    cleaned = {}
    for key,value in details.items():
        if not isinstance(value,str):
            raise ValueError('201-file values must be text.')
        value=value.strip()
        limit=10000 if FIELDS[key]=='textarea' else 250
        if len(value)>limit:
            raise ValueError(f'{key} is too long (maximum {limit} characters).')
        if value and FIELDS[key]=='date':
            try:
                if datetime.strptime(value,'%Y-%m-%d').strftime('%Y-%m-%d')!=value:
                    raise ValueError()
            except ValueError:
                raise ValueError(f'{key} must be a valid date (YYYY-MM-DD).') from None
        if value and FIELDS[key]=='number':
            try:
                number=float(value)
                if not 0<number<1000:raise ValueError()
            except ValueError:
                raise ValueError(f'{key} must be a positive number below 1,000.') from None
        cleaned[key]=value
    return cleaned


def validate_image(value):
    if value is None:return None
    if not isinstance(value,str) or len(value)>1400000:
        raise ValueError('Photo and signature must each be PNG or JPEG, up to 1 MB.')
    prefixes={'data:image/png;base64,':'image/png','data:image/jpeg;base64,':'image/jpeg'}
    for prefix,mime in prefixes.items():
        if value.startswith(prefix):
            try:content=base64.b64decode(value[len(prefix):],validate=True)
            except (ValueError,binascii.Error):raise ValueError('Invalid image data.') from None
            if not 0<len(content)<=1024*1024:
                raise ValueError('Each image must be no larger than 1 MB.')
            if mime=='image/png' and not (content.startswith(b'\x89PNG\r\n\x1a\n') and content[12:16]==b'IHDR' and b'IEND' in content[-16:]):
                raise ValueError('Invalid PNG image.')
            if mime=='image/jpeg' and not (content.startswith(b'\xff\xd8\xff') and content.endswith(b'\xff\xd9')):
                raise ValueError('Invalid JPEG image.')
            return mime,content
    raise ValueError('Only PNG and JPEG images are supported.')


def images_from_row(row):
    return {kind:validate_image(row[kind]) for kind in ('photo','signature') if kind in row}


def save_images(db,person_id,images):
    for kind,image in images.items():
        if image is None:
            db.execute('DELETE FROM employee_images WHERE person_id=? AND kind=?',(person_id,kind))
        else:
            mime,content=image
            db.execute('INSERT INTO employee_images(person_id,kind,mime,content) VALUES (?,?,?,?) '
                       'ON CONFLICT(person_id,kind) DO UPDATE SET mime=excluded.mime,content=excluded.content',
                       (person_id,kind,mime,content))


def get(db,person_id):
    person=db.execute('SELECT id,name,barcode FROM people WHERE id=?',(person_id,)).fetchone()
    if not person:raise ValueError('Employee not found.')
    profile=db.execute('SELECT details,version FROM employee_profiles WHERE person_id=?',(person_id,)).fetchone()
    result=dict(person)
    result.update(profile=json.loads(profile['details']) if profile else {},version=profile['version'] if profile else 0)
    result['images']={kind:f'/api/people/{person_id}/image/{kind}?v={result["version"]}'
                      for kind, in db.execute('SELECT kind FROM employee_images WHERE person_id=?',(person_id,))}
    return result
