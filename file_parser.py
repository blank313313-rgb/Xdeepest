# file_parser.py - تحليل الملفات المختلفة

import pandas as pd
import os
import zipfile
import tempfile
import shutil

try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False

try:
    import py7zr
    HAS_7Z = True
except ImportError:
    HAS_7Z = False


# الخرائط: تحويل أسماء الأعمدة المختلفة إلى أسماء موحدة
COLUMN_MAPPING = {
    # الاسم
    'الاسم': 'full_name', 'اسم': 'full_name', 'الاسم الكامل': 'full_name',
    'الاسم الثلاثي': 'full_name', 'name': 'full_name', 'full_name': 'full_name',
    'الاسم الثنائي': 'full_name', 'اسم الموظف': 'full_name', 'اسم العميل': 'full_name',
    'اسم ثلاثي': 'full_name', 'customer_name': 'full_name', 'employee_name': 'full_name',
    'person_name': 'full_name',

    # الهاتف
    'الهاتف': 'phone', 'رقم الهاتف': 'phone', 'رقم الجوال': 'phone',
    'phone': 'phone', 'mobile': 'phone', 'tel': 'phone', 'telephone': 'phone',
    'رقم': 'phone', 'جوال': 'phone', 'cell': 'phone',

    # العنوان
    'العنوان': 'address', 'عنوان': 'address', 'السكن': 'address',
    'address': 'address', 'location': 'address', 'مكان السكن': 'address',
    'المدينة': 'address', 'city': 'address', 'المنطقة': 'address',

    # تاريخ الميلاد
    'تاريخ الميلاد': 'birth_date', 'المواليد': 'birth_date', 'ميلاد': 'birth_date',
    'birth_date': 'birth_date', 'dob': 'birth_date', 'date_of_birth': 'birth_date',
    'birthday': 'birth_date', 'تاريخ': 'birth_date',

    # العمر
    'العمر': 'age', 'عمر': 'age', 'age': 'age',

    # فيسبوك
    'فيسبوك': 'facebook', 'facebook': 'facebook', 'fb': 'facebook',
    'حساب فيسبوك': 'facebook', 'رابط فيسبوك': 'facebook', 'fb_link': 'facebook',

    # انستقرام
    'انستقرام': 'instagram', 'instagram': 'instagram', 'insta': 'instagram',
    'حساب انستقرام': 'instagram', 'رابط انستقرام': 'instagram', 'ig': 'instagram',

    # النوع (موظف/عميل)
    'النوع': 'person_type', 'نوع': 'person_type', 'person_type': 'person_type',
    'type': 'person_type', 'الصنف': 'person_type', 'التصنيف': 'person_type',

    # العائلة
    'العائلة': 'family_details', 'عائلة': 'family_details', 'العائله': 'family_details',
    'family': 'family_details', 'family_details': 'family_details',
    'تفاصيل العائلة': 'family_details', 'أفراد العائلة': 'family_details',

    # ملاحظات
    'ملاحظات': 'notes', 'ملاحظة': 'notes', 'notes': 'notes',
    'note': 'notes', 'تفاصيل': 'notes', 'details': 'notes',
    'معلومات إضافية': 'notes',
}


def normalize_columns(df):
    """تحويل أسماء الأعمدة إلى أسماء موحدة"""
    new_columns = {}
    for col in df.columns:
        col_clean = str(col).strip().lower()
        matched = False
        for key, value in COLUMN_MAPPING.items():
            if col_clean == key.lower() or col_clean.replace('_', ' ') == key.lower().replace('_', ' '):
                new_columns[col] = value
                matched = True
                break
        if not matched:
            new_columns[col] = col

    return df.rename(columns=new_columns)


def parse_file(filepath):
    """تحليل ملف وإرجاع قائمة بالأشخاص"""
    ext = os.path.splitext(filepath)[1].lower()
    persons = []

    if ext == '.csv':
        persons = parse_csv(filepath)
    elif ext in ('.xls', '.xlsx'):
        persons = parse_excel(filepath)
    elif ext == '.xlsb':
        persons = parse_xlsb(filepath)
    elif ext == '.txt':
        persons = parse_txt(filepath)
    elif ext == '.zip':
        persons = parse_archive(filepath, 'zip')
    elif ext == '.rar':
        if HAS_RAR:
            persons = parse_archive(filepath, 'rar')
    elif ext == '.7z':
        if HAS_7Z:
            persons = parse_archive(filepath, '7z')
    elif ext in ('.mdb', '.accdb'):
        persons = parse_access(filepath)

    return persons


def parse_csv(filepath):
    """قراءة ملف CSV"""
    try:
        df = pd.read_csv(filepath, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(filepath, encoding='cp1256')  # Arabic Windows
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, encoding='latin1')

    df = normalize_columns(df)
    return df_to_persons(df)


def parse_excel(filepath):
    """قراءة ملف Excel"""
    df = pd.read_excel(filepath, engine='openpyxl' if filepath.endswith('.xlsx') else 'xlrd')
    df = normalize_columns(df)
    return df_to_persons(df)


def parse_xlsb(filepath):
    """قراءة ملف XLSB"""
    df = pd.read_excel(filepath, engine='pyxlsb')
    df = normalize_columns(df)
    return df_to_persons(df)


def parse_txt(filepath):
    """قراءة ملف نصي - محاولة تحديد الفاصل تلقائياً"""
    separators = [',', '\t', '|', ';']
    for sep in separators:
        try:
            df = pd.read_csv(filepath, sep=sep)
            if len(df.columns) > 1:
                df = normalize_columns(df)
                return df_to_persons(df)
        except Exception:
            continue

    # لو ما نجح أي فاصل، قراءة سطر سطر
    persons = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line:
                persons.append({'full_name': line})
    return persons


def parse_archive(filepath, archive_type):
    """فك ضغط الملفات المضغوطة وجمع البيانات"""
    all_persons = []
    temp_dir = tempfile.mkdtemp()

    try:
        if archive_type == 'zip':
            with zipfile.ZipFile(filepath, 'r') as z:
                z.extractall(temp_dir)
        elif archive_type == 'rar':
            with rarfile.RarFile(filepath, 'r') as z:
                z.extractall(temp_dir)
        elif archive_type == '7z':
            with py7zr.SevenZipFile(filepath, 'r') as z:
                z.extractall(temp_dir)

        # معالجة كل ملف مستخرج
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                if ext in ('.csv', '.xls', '.xlsx', '.txt', '.xlsb'):
                    try:
                        persons = parse_file(file_path)
                        all_persons.extend(persons)
                    except Exception:
                        continue
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return all_persons


def parse_access(filepath):
    """قراءة ملف Access (mdb/accdb)"""
    try:
        import subprocess
        # محاولة استخدام mdb-tools لو متاح
        result = subprocess.run(['mdb-tables', filepath], capture_output=True, text=True)
        if result.returncode == 0:
            tables = result.stdout.strip().split()
            all_persons = []
            for table in tables:
                csv_result = subprocess.run(
                    ['mdb-export', filepath, table],
                    capture_output=True, text=True
                )
                if csv_result.returncode == 0:
                    import io
                    df = pd.read_csv(io.StringIO(csv_result.stdout))
                    df = normalize_columns(df)
                    all_persons.extend(df_to_persons(df))
            return all_persons
    except Exception:
        pass

    return []


def df_to_persons(df):
    """تحويل DataFrame إلى قائمة قواميس"""
    persons = []
    required_fields = ['full_name', 'phone', 'address', 'birth_date', 'age',
                       'facebook', 'instagram', 'person_type', 'family_details', 'notes']

    for _, row in df.iterrows():
        person = {}
        for field in required_fields:
            if field in df.columns:
                val = row.get(field)
                person[field] = str(val) if pd.notna(val) and str(val) != 'nan' else ''
            else:
                person[field] = ''

        # تخطي الصفوف اللي ما فيها اسم
        if person.get('full_name', '').strip():
            persons.append(person)

    return persons
