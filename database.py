# database.py - إدارة قاعدة البيانات مع فرز ودمج ذكي

import sqlite3
import os
import config


def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        phone TEXT DEFAULT '',
        address TEXT DEFAULT '',
        birth_date TEXT DEFAULT '',
        age TEXT DEFAULT '',
        facebook TEXT DEFAULT '',
        instagram TEXT DEFAULT '',
        person_type TEXT DEFAULT 'unknown',
        family_details TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS uploaded_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        records_count INTEGER DEFAULT 0,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


def get_connection():
    return sqlite3.connect(config.DB_PATH)


def search_person(name_query):
    """بحث عن شخص بالاسم - يرجع كل النتائج"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, full_name, phone, address, birth_date, age,
               facebook, instagram, person_type, family_details, notes
        FROM persons WHERE full_name LIKE ?
        ORDER BY full_name
    """, (f"%{name_query}%",))
    results = c.fetchall()
    conn.close()
    return results


def search_by_phone(phone_query):
    """بحث بالهاتف"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, full_name, phone, address, birth_date, age,
               facebook, instagram, person_type, family_details, notes
        FROM persons WHERE phone LIKE ?
        ORDER BY full_name
    """, (f"%{phone_query}%",))
    results = c.fetchall()
    conn.close()
    return results


def get_person_by_id(person_id):
    """جلب شخص بالرقم"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, full_name, phone, address, birth_date, age,
               facebook, instagram, person_type, family_details, notes
        FROM persons WHERE id = ?
    """, (person_id,))
    result = c.fetchone()
    conn.close()
    return result


def normalize_text(text):
    """تنظيف النص للمقارنة"""
    if not text:
        return ''
    return str(text).strip().lower().replace('-', '').replace(' ', '').replace('_', '')


def persons_are_duplicate(p1, p2):
    """
    التحقق هل شخصين نفس الشخص (مكرر)
    شرط: نفس الاسم + (نفس الرقم أو نفس السكن) + نفس العائلة
    """
    name1 = normalize_text(p1.get('full_name', ''))
    name2 = normalize_text(p2.get('full_name', ''))

    # الأسماء مختلفة تماماً = مو نفس الشخص
    if name1 != name2:
        return False

    phone1 = normalize_text(p1.get('phone', ''))
    phone2 = normalize_text(p2.get('phone', ''))
    addr1 = normalize_text(p1.get('address', ''))
    addr2 = normalize_text(p2.get('address', ''))
    fam1 = normalize_text(p1.get('family_details', ''))
    fam2 = normalize_text(p2.get('family_details', ''))

    # نفس الاسم لكن معلومات مختلفة = شخصين مختلفين
    phone_match = phone1 and phone2 and phone1 == phone2
    addr_match = addr1 and addr2 and addr1 == addr2

    # لو نفس الاسم ونفس الرقم = نفس الشخص
    if phone_match:
        return True

    # لو نفس الاسم ونفس السكن = نفس الشخص (على الأرجح)
    if addr_match:
        return True

    # لو نفس الاسم ونفس العائلة = نفس الشخص
    if fam1 and fam2 and fam1 == fam2:
        return True

    # نفس الاسم بس باقي المعلومات مختلفة = شخصين مختلفين
    if phone1 and phone2 and phone1 != phone2:
        return False
    if addr1 and addr2 and addr1 != addr2:
        return False

    return False


def persons_are_complementary(p1, p2):
    """
    التحقق هل شخصين يكملان بعض (نفس الشخص بمعلومات مختلفة)
    شرط: نفس الاسم + بعض المعلومات متطابقة والباقي مكمل
    """
    name1 = normalize_text(p1.get('full_name', ''))
    name2 = normalize_text(p2.get('full_name', ''))

    if name1 != name2:
        return False

    phone1 = normalize_text(p1.get('phone', ''))
    phone2 = normalize_text(p2.get('phone', ''))

    # لو الأرقام مختلفة = شخصين مختلفين
    if phone1 and phone2 and phone1 != phone2:
        return False

    addr1 = normalize_text(p1.get('address', ''))
    addr2 = normalize_text(p2.get('address', ''))

    # لو السكن مختلف = شخصين مختلفين
    if addr1 and addr2 and addr1 != addr2:
        return False

    return True


def merge_person_data(p1, p2):
    """دمج بيانات شخصين في سجل واحد - يأخذ الأطول/الأكمل"""
    merged = {}
    fields = ['full_name', 'phone', 'address', 'birth_date', 'age',
              'facebook', 'instagram', 'person_type', 'family_details', 'notes']

    for field in fields:
        val1 = p1.get(field, '').strip()
        val2 = p2.get(field, '').strip()

        if not val1 and not val2:
            merged[field] = ''
        elif not val1:
            merged[field] = val2
        elif not val2:
            merged[field] = val1
        elif val1 == val2:
            merged[field] = val1
        else:
            # لو القيمتين موجودتين ومختلفتين - اجمعهم
            if field == 'notes':
                merged[field] = f"{val1} | {val2}"
            else:
                # خذ الأطول (الأكثر تفصيلاً)
                merged[field] = val1 if len(val1) >= len(val2) else val2

    return merged


def smart_import(persons_list):
    """
    فرز ودمج ذكي عند استيراد بيانات جديدة:
    1. دمج السجلات المكملة لبعض (نفس الشخص بمعلومات مختلفة)
    2. حذف المكررين (نفس الشخص نفس المعلومات)
    3. دمج مع القاعدة الموجودة
    """
    conn = get_connection()
    c = conn.cursor()

    # تنظيف القائمة الواردة
    cleaned = []
    for p in persons_list:
        name = p.get('full_name', '').strip()
        if name:
            # تنظيف القيم الفارغة
            for key in p:
                if p[key] is None or str(p[key]) == 'nan':
                    p[key] = ''
            cleaned.append(p)

    # المرحلة 1: دمج داخل القائمة الواردة
    merged_list = []
    used_indices = set()

    for i in range(len(cleaned)):
        if i in used_indices:
            continue

        current = cleaned[i].copy()

        for j in range(i + 1, len(cleaned)):
            if j in used_indices:
                continue

            if persons_are_complementary(current, cleaned[j]):
                # دمج السجلين
                current = merge_person_data(current, cleaned[j])
                if persons_are_duplicate(current, cleaned[j]):
                    used_indices.add(j)  # حذف المكرر
                else:
                    used_indices.add(j)  # دمج المكمل

        merged_list.append(current)
        used_indices.add(i)

    # المرحلة 2: دمج مع القاعدة الموجودة
    new_count = 0
    merged_count = 0

    for person in merged_list:
        name = normalize_text(person.get('full_name', ''))

        # البحث عن شخص مطابق في القاعدة
        c.execute("SELECT id, full_name, phone, address, birth_date, age, facebook, instagram, person_type, family_details, notes FROM persons")
        existing = c.fetchall()

        matched_id = None
        for row in existing:
            existing_person = {
                'full_name': row[1], 'phone': row[2], 'address': row[3],
                'birth_date': row[4], 'age': row[5], 'facebook': row[6],
                'instagram': row[7], 'person_type': row[8], 'family_details': row[9], 'notes': row[10]
            }

            if persons_are_complementary(person, existing_person):
                matched_id = row[0]
                # دمج البيانات
                merged_data = merge_person_data(person, existing_person)
                c.execute('''UPDATE persons SET phone=?, address=?, birth_date=?, age=?,
                    facebook=?, instagram=?, person_type=?, family_details=?, notes=? WHERE id=?''',
                    (merged_data['phone'], merged_data['address'], merged_data['birth_date'],
                     merged_data['age'], merged_data['facebook'], merged_data['instagram'],
                     merged_data['person_type'], merged_data['family_details'], merged_data['notes'],
                     matched_id))
                merged_count += 1
                break

        if matched_id is None:
            # شخص جديد - إضافته
            c.execute('''INSERT INTO persons 
                (full_name, phone, address, birth_date, age, facebook, instagram, person_type, family_details, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (person.get('full_name', ''), person.get('phone', ''), person.get('address', ''),
                 person.get('birth_date', ''), person.get('age', ''), person.get('facebook', ''),
                 person.get('instagram', ''), person.get('person_type', 'unknown'),
                 person.get('family_details', ''), person.get('notes', '')))
            new_count += 1

    conn.commit()
    conn.close()

    return {
        'total_imported': len(persons_list),
        'after_dedup': len(merged_list),
        'new': new_count,
        'merged': merged_count,
        'duplicates_removed': len(persons_list) - len(merged_list)
    }


def insert_person(data):
    """إضافة شخص واحد يدوياً مع تحقق من التكرار"""
    conn = get_connection()
    c = conn.cursor()

    name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()

    # تحقق هل الشخص موجود
    if name:
        c.execute("SELECT id FROM persons WHERE full_name = ?", (name,))
        existing = c.fetchone()
        if existing:
            # الشخص موجود - دمج البيانات
            c.execute("SELECT full_name, phone, address, birth_date, age, facebook, instagram, person_type, family_details, notes FROM persons WHERE id = ?", (existing[0],))
            row = c.fetchone()
            existing_person = {
                'full_name': row[0], 'phone': row[1], 'address': row[2],
                'birth_date': row[3], 'age': row[4], 'facebook': row[5],
                'instagram': row[6], 'person_type': row[7], 'family_details': row[8], 'notes': row[9]
            }
            merged = merge_person_data(data, existing_person)
            c.execute('''UPDATE persons SET phone=?, address=?, birth_date=?, age=?,
                facebook=?, instagram=?, person_type=?, family_details=?, notes=? WHERE id=?''',
                (merged['phone'], merged['address'], merged['birth_date'],
                 merged['age'], merged['facebook'], merged['instagram'],
                 merged['person_type'], merged['family_details'], merged['notes'],
                 existing[0]))
            conn.commit()
            conn.close()
            return existing[0], True  # True = تم الدمج

    c.execute('''INSERT INTO persons 
        (full_name, phone, address, birth_date, age, facebook, instagram, person_type, family_details, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (data.get('full_name', ''), data.get('phone', ''), data.get('address', ''),
         data.get('birth_date', ''), data.get('age', ''), data.get('facebook', ''),
         data.get('instagram', ''), data.get('person_type', 'unknown'),
         data.get('family_details', ''), data.get('notes', '')))
    conn.commit()
    pid = c.lastrowid
    conn.close()
    return pid, False  # False = شخص جديد


def log_upload(filename, records_count):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO uploaded_files (filename, records_count) VALUES (?, ?)',
        (filename, records_count))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM persons')
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM persons WHERE person_type = 'employee'")
    employees = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM persons WHERE person_type = 'client'")
    clients = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM persons WHERE person_type = 'unknown'")
    unknown = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM uploaded_files')
    files = c.fetchone()[0]
    conn.close()
    return {'total': total, 'employees': employees, 'clients': clients, 'unknown': unknown, 'files': files}


def delete_person(person_id):
    """حذف شخص"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM persons WHERE id = ?', (person_id,))
    conn.commit()
    conn.close()
