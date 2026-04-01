from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import date

app = Flask(__name__)

# ─── DATABASE CONFIG ─────────────────────────────────
# Apna MySQL password yahan daalein:
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'skyap@123',
    'database': 'student_ms'
}

def get_db():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"DB Error: {e}")
        return None

def init_db():
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS student_ms")
        cur.execute("USE student_ms")
        cur.execute("""CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_no VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            phone VARCHAR(15),
            class VARCHAR(20),
            section VARCHAR(5),
            dob DATE,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS marks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            subject VARCHAR(50),
            exam_type VARCHAR(30),
            marks_obtained FLOAT,
            total_marks FLOAT,
            exam_date DATE,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            att_date DATE,
            status ENUM('Present','Absent','Late') DEFAULT 'Present',
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE KEY uq_att (student_id, att_date)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS fees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            fee_type VARCHAR(50),
            amount DECIMAL(10,2),
            paid_amount DECIMAL(10,2) DEFAULT 0,
            due_date DATE,
            paid_date DATE,
            status ENUM('Pending','Partial','Paid') DEFAULT 'Pending',
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )""")
        conn.commit()
        cur.close(); conn.close()
        print("✅ Database ready!")
    except Error as e:
        print(f"Init error: {e}")

# ─── PAGES ───────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

# ─── STATS ───────────────────────────────────────────
@app.route('/api/stats')
def stats():
    conn = get_db()
    if not conn: return jsonify({'error': 'DB failed'}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) as c FROM students")
    total = cur.fetchone()['c']
    today = date.today().isoformat()
    cur.execute("SELECT COUNT(*) as c FROM attendance WHERE att_date=%s AND status='Present'", (today,))
    present = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM fees WHERE status!='Paid'")
    pending = cur.fetchone()['c']
    cur.execute("SELECT AVG(marks_obtained/total_marks*100) as a FROM marks WHERE total_marks>0")
    avg_row = cur.fetchone()
    avg = round(avg_row['a'] or 0, 1)
    cur.execute("SELECT class, COUNT(*) as cnt FROM students GROUP BY class ORDER BY class")
    classes = cur.fetchall()
    cur.execute("""SELECT s.name, ROUND(AVG(m.marks_obtained/m.total_marks*100),1) as avg
        FROM students s JOIN marks m ON s.id=m.student_id
        WHERE m.total_marks>0 GROUP BY s.id ORDER BY avg DESC LIMIT 5""")
    top = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({'total': total, 'present': present, 'pending': pending,
                    'avg': avg, 'classes': classes, 'top': top})

# ─── STUDENTS ────────────────────────────────────────
@app.route('/api/students', methods=['POST'])
def add_student():
    return jsonify({"success": True})
    conn = get_db(); cur = conn.cursor(dictionary=True)
    s = request.args.get('search',''); c = request.args.get('class','')
    q = "SELECT * FROM students WHERE 1=1"; p = []
    if s:
        q += " AND (name LIKE %s OR roll_no LIKE %s OR email LIKE %s)"
        p += [f'%{s}%']*3
    if c: q += " AND class=%s"; p.append(c)
    q += " ORDER BY created_at DESC"
    cur.execute(q, p)
    rows = cur.fetchall()
    for r in rows:
        r['dob'] = str(r['dob']) if r.get('dob') else ''
        r['created_at'] = str(r['created_at']) if r.get('created_at') else ''
    cur.close(); conn.close()
    return jsonify(rows)

@app.route('/api/students', methods=['POST'])
def add_student():
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO students (roll_no,name,email,phone,class,section,dob,address) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (d['roll_no'],d['name'],d.get('email',''),d.get('phone',''),d.get('class',''),d.get('section',''),d.get('dob') or None,d.get('address','')))
        conn.commit()
        return jsonify({'success': True, 'id': cur.lastrowid})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/students/<int:sid>', methods=['GET'])
def get_student(sid):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM students WHERE id=%s", (sid,))
    s = cur.fetchone()
    if s:
        s['dob'] = str(s['dob']) if s.get('dob') else ''
        s['created_at'] = str(s['created_at']) if s.get('created_at') else ''
    cur.close(); conn.close()
    return jsonify(s)

@app.route('/api/students/<int:sid>', methods=['PUT'])
def update_student(sid):
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE students SET roll_no=%s,name=%s,email=%s,phone=%s,class=%s,section=%s,dob=%s,address=%s WHERE id=%s",
            (d['roll_no'],d['name'],d.get('email',''),d.get('phone',''),d.get('class',''),d.get('section',''),d.get('dob') or None,d.get('address',''),sid))
        conn.commit(); return jsonify({'success': True})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/students/<int:sid>', methods=['DELETE'])
def delete_student(sid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id=%s", (sid,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'success': True})

# ─── MARKS ───────────────────────────────────────────
def get_grade(o, t):
    if not t: return 'N/A'
    p = o/t*100
    return 'A+' if p>=90 else 'A' if p>=80 else 'B+' if p>=70 else 'B' if p>=60 else 'C' if p>=50 else 'D' if p>=40 else 'F'

@app.route('/api/marks', methods=['GET'])
def get_marks():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    sid = request.args.get('student_id','')
    if sid:
        cur.execute("SELECT m.*,s.name,s.roll_no FROM marks m JOIN students s ON m.student_id=s.id WHERE m.student_id=%s ORDER BY m.exam_date DESC", (sid,))
    else:
        cur.execute("SELECT m.*,s.name,s.roll_no FROM marks m JOIN students s ON m.student_id=s.id ORDER BY m.exam_date DESC LIMIT 200")
    rows = cur.fetchall()
    for r in rows:
        r['exam_date'] = str(r['exam_date']) if r.get('exam_date') else ''
        r['grade'] = get_grade(r['marks_obtained'], r['total_marks'])
        r['pct'] = round(r['marks_obtained']/r['total_marks']*100,1) if r['total_marks'] else 0
    cur.close(); conn.close(); return jsonify(rows)

@app.route('/api/marks', methods=['POST'])
def add_marks():
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO marks (student_id,subject,exam_type,marks_obtained,total_marks,exam_date) VALUES (%s,%s,%s,%s,%s,%s)",
            (d['student_id'],d['subject'],d['exam_type'],d['marks_obtained'],d['total_marks'],d.get('exam_date') or None))
        conn.commit(); return jsonify({'success': True})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/marks/<int:mid>', methods=['DELETE'])
def delete_mark(mid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM marks WHERE id=%s", (mid,))
    conn.commit(); cur.close(); conn.close(); return jsonify({'success': True})

# ─── ATTENDANCE ──────────────────────────────────────
@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    att_date = request.args.get('date', date.today().isoformat())
    sid = request.args.get('student_id','')
    if sid:
        cur.execute("SELECT a.*,s.name,s.roll_no FROM attendance a JOIN students s ON a.student_id=s.id WHERE a.student_id=%s ORDER BY a.att_date DESC", (sid,))
  else:
    cur.execute("""SELECT s.id,s.name,s.roll_no,s.class,s.section,
        COALESCE(a.status,'Not Marked') as status FROM students s
        LEFT JOIN attendance a ON s.id=a.student_id AND a.att_date=%s
        ORDER BY s.class,s.roll_no""", (att_date,))
    rows = cur.fetchall()
    for r in rows:
        if r.get('att_date'): r['att_date'] = str(r['att_date'])
    cur.close(); conn.close(); return jsonify(rows)

@app.route('/api/attendance', methods=['POST'])
def mark_attendance():
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        for rec in d['records']:
            cur.execute("INSERT INTO attendance (student_id,att_date,status) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE status=%s",
                (rec['student_id'],d['date'],rec['status'],rec['status']))
        conn.commit(); return jsonify({'success': True})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/attendance/summary')
def att_summary():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT s.id,s.name,s.roll_no,s.class,
        COUNT(a.id) as total, SUM(a.status='Present') as present,
        SUM(a.status='Absent') as absent, SUM(a.status='Late') as late,
        ROUND(SUM(a.status='Present')/NULLIF(COUNT(a.id),0)*100,1) as pct
        FROM students s LEFT JOIN attendance a ON s.id=a.student_id
        GROUP BY s.id ORDER BY pct DESC""")
    rows = cur.fetchall(); cur.close(); conn.close(); return jsonify(rows)
# ─── FEES ────────────────────────────────────────────
@app.route('/api/fees', methods=['GET'])
def get_fees():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    sid = request.args.get('student_id',''); st = request.args.get('status','')
    q = "SELECT f.*,s.name,s.roll_no FROM fees f JOIN students s ON f.student_id=s.id WHERE 1=1"; p = []
    if sid: q += " AND f.student_id=%s"; p.append(sid)
    if st:  q += " AND f.status=%s"; p.append(st)
    q += " ORDER BY f.due_date DESC"
    cur.execute(q, p); rows = cur.fetchall()
    for r in rows:
        r['due_date']  = str(r['due_date'])  if r.get('due_date')  else ''
        r['paid_date'] = str(r['paid_date']) if r.get('paid_date') else ''
        r['balance']   = float(r['amount']) - float(r['paid_amount'])
    cur.close(); conn.close(); return jsonify(rows)

@app.route('/api/fees', methods=['POST'])
def add_fee():
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO fees (student_id,fee_type,amount,paid_amount,due_date,paid_date,status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (d['student_id'],d['fee_type'],d['amount'],d.get('paid_amount',0),d.get('due_date') or None,d.get('paid_date') or None,d.get('status','Pending')))
        conn.commit(); return jsonify({'success': True})
    except Error as e: return jsonify({'error': str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/fees/<int:fid>', methods=['PUT'])
def update_fee(fid):
    d = request.json; conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE fees SET paid_amount=%s,paid_date=%s,status=%s WHERE id=%s",
        (d['paid_amount'],d.get('paid_date') or None,d['status'],fid))
    conn.commit(); cur.close(); conn.close(); return jsonify({'success': True})

@app.route('/api/fees/<int:fid>', methods=['DELETE'])
def delete_fee(fid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM fees WHERE id=%s", (fid,))
    conn.commit(); cur.close(); conn.close(); return jsonify({'success': True})
@app.route("/export")
def export():
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM students")
    data = cur.fetchall()

    cur.close()
    conn.close()

    if not data:
        return "No data found ❌"

    df = pd.DataFrame(data)

    file_path = "students.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

import os

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
