"""University Management System - Flask application."""
import os
import re
import secrets
import sqlite3
from datetime import date

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)

import db

app = Flask(__name__)
app.secret_key = os.environ.get("UNI_SECRET") or secrets.token_hex(32)

DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ---------------------------------------------------------------- infrastructure
def get_db():
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST":
        token = request.form.get("csrf_token", "")
        if not token or not secrets.compare_digest(token, session.get("csrf", "")):
            abort(400, "Invalid or missing CSRF token. Reload the page and try again.")


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(e):
    code = getattr(e, "code", 500)
    msg = getattr(e, "description", "Unexpected error.") if code != 500 else "Something went wrong on the server."
    return render_template("error.html", code=code, message=msg), code


def Q(sql, params=()):
    return db.query(get_db(), sql, params)


def Q1(sql, params=()):
    return db.one(get_db(), sql, params)


# ---------------------------------------------------------------- entity configuration
# Each entity drives the generic list / form / detail / delete pages.
def F(name, label, type="text", required=True, options=None, min=None, max=None, help=None, default=None):
    return dict(name=name, label=label, type=type, required=required, options=options,
                min=min, max=max, help=help, default=default)


OPT = {
    "departments": "SELECT dept_id, dept_name FROM departments ORDER BY dept_name",
    "instructors": "SELECT instructor_id, first_name || ' ' || last_name FROM instructors ORDER BY 2",
    "courses": "SELECT course_id, course_code || ' - ' || course_name FROM courses ORDER BY course_code",
    "semesters": "SELECT semester_id, semester_name FROM semesters ORDER BY start_date DESC",
    "classrooms": "SELECT room_id, building || ' ' || room_number || ' (cap ' || capacity || ')' FROM classrooms ORDER BY 2",
}

ENTITIES = {
    "departments": dict(
        table="departments", pk="dept_id", singular="Department", plural="Departments", icon="building",
        fields=[F("dept_name", "Department name"), F("building", "Building", required=False),
                F("head_id", "Department head", "select", False, options="instructors")],
        sql="""SELECT d.dept_id AS id, d.dept_name AS name, d.building,
                      (SELECT i.first_name || ' ' || i.last_name FROM instructors i WHERE i.instructor_id = d.head_id) AS head,
                      (SELECT COUNT(*) FROM students s WHERE s.dept_id = d.dept_id) AS students,
                      (SELECT COUNT(*) FROM instructors i WHERE i.dept_id = d.dept_id) AS instructors,
                      (SELECT COUNT(*) FROM courses c WHERE c.dept_id = d.dept_id) AS courses
               FROM departments d""",
        columns=["name", "building", "head", "students", "instructors", "courses"],
        search=["name", "building", "head"],
        related=[("Instructors", "SELECT instructor_id AS id, first_name || ' ' || last_name AS name, email FROM instructors WHERE dept_id = ?", "instructors"),
                 ("Courses", "SELECT course_id AS id, course_code AS code, course_name AS title, credit_hours AS credits FROM courses WHERE dept_id = ?", "courses"),
                 ("Students", "SELECT student_id AS id, first_name || ' ' || last_name AS name, email, status FROM students WHERE dept_id = ?", "students")]),
    "students": dict(
        table="students", pk="student_id", singular="Student", plural="Students", icon="mortarboard",
        fields=[F("first_name", "First name"), F("last_name", "Last name"), F("email", "Email", "email"),
                F("phone", "Phone", required=False), F("birth_date", "Birth date", "date", False),
                F("gender", "Gender", "select", True, options=[("M", "Male"), ("F", "Female")]),
                F("enroll_date", "Admission date", "date", True, default="today"),
                F("status", "Status", "select", True, options=[("ACTIVE", "Active"), ("GRADUATED", "Graduated"), ("SUSPENDED", "Suspended")], default="ACTIVE"),
                F("dept_id", "Department", "select", True, options="departments")],
        sql="""SELECT s.student_id AS id, s.first_name || ' ' || s.last_name AS name, s.email, s.phone,
                      s.gender, s.birth_date, s.enroll_date, s.status, d.dept_name AS department
               FROM students s JOIN departments d ON d.dept_id = s.dept_id""",
        columns=["id", "name", "email", "department", "status"],
        search=["id", "name", "email"],
        related=[("Enrollment history", """SELECT semester_name AS semester, course_code AS code, course_name AS course,
                      credit_hours AS credits, status, grade, letter_grade AS letter
                      FROM v_student_transcript WHERE student_id = ? ORDER BY start_date, course_code""", None)],
        gpa=True),
    "instructors": dict(
        table="instructors", pk="instructor_id", singular="Instructor", plural="Instructors", icon="person-workspace",
        fields=[F("first_name", "First name"), F("last_name", "Last name"), F("email", "Email", "email"),
                F("phone", "Phone", required=False), F("hire_date", "Hire date", "date", True, default="today"),
                F("salary", "Salary", "number", True, min=1), F("dept_id", "Department", "select", True, options="departments")],
        sql="""SELECT i.instructor_id AS id, i.first_name || ' ' || i.last_name AS name, i.email, i.phone,
                      i.hire_date, i.salary, d.dept_name AS department
               FROM instructors i JOIN departments d ON d.dept_id = i.dept_id""",
        columns=["name", "email", "department", "hire_date"],
        search=["name", "email", "department"],
        related=[("Sections taught", """SELECT sec.section_id AS id, c.course_code AS code, c.course_name AS course, sem.semester_name AS semester,
                      sec.days, sec.start_time || '-' || sec.end_time AS time
                      FROM sections sec JOIN courses c ON c.course_id = sec.course_id
                      JOIN semesters sem ON sem.semester_id = sec.semester_id
                      WHERE sec.instructor_id = ? ORDER BY sem.start_date""", "sections")]),
    "courses": dict(
        table="courses", pk="course_id", singular="Course", plural="Courses", icon="book",
        fields=[F("course_code", "Course code", help="e.g. CS101"), F("course_name", "Title"),
                F("credit_hours", "Credit hours", "number", True, min=1, max=6),
                F("dept_id", "Department", "select", True, options="departments")],
        sql="""SELECT c.course_id AS id, c.course_code AS code, c.course_name AS title, c.credit_hours AS credits,
                      d.dept_name AS department,
                      (SELECT GROUP_CONCAT(p2.course_code, ', ') FROM course_prerequisites p
                         JOIN courses p2 ON p2.course_id = p.prereq_id WHERE p.course_id = c.course_id) AS prerequisites
               FROM courses c JOIN departments d ON d.dept_id = c.dept_id""",
        columns=["code", "title", "credits", "department", "prerequisites"],
        search=["code", "title", "department"],
        related=[("Sections", """SELECT sec.section_id AS id, sem.semester_name AS semester, sec.section_no AS no,
                      i.first_name || ' ' || i.last_name AS instructor, sec.days
                      FROM sections sec JOIN semesters sem ON sem.semester_id = sec.semester_id
                      JOIN instructors i ON i.instructor_id = sec.instructor_id
                      WHERE sec.course_id = ? ORDER BY sem.start_date""", "sections")],
        prereq=True),
    "semesters": dict(
        table="semesters", pk="semester_id", singular="Semester", plural="Semesters", icon="calendar3",
        fields=[F("semester_name", "Semester name", help="e.g. Fall 2026"), F("academic_year", "Academic year", help="e.g. 2026/2027"),
                F("start_date", "Start date", "date"), F("end_date", "End date", "date")],
        sql="""SELECT semester_id AS id, semester_name AS name, academic_year AS year, start_date, end_date,
                      (SELECT COUNT(*) FROM sections s WHERE s.semester_id = semesters.semester_id) AS sections
               FROM semesters""",
        columns=["name", "year", "start_date", "end_date", "sections"],
        search=["name", "year"],
        related=[("Sections offered", """SELECT sec.section_id AS id, c.course_code AS code, c.course_name AS course,
                      i.first_name || ' ' || i.last_name AS instructor, sec.days, sec.start_time || '-' || sec.end_time AS time
                      FROM sections sec JOIN courses c ON c.course_id = sec.course_id
                      JOIN instructors i ON i.instructor_id = sec.instructor_id
                      WHERE sec.semester_id = ? ORDER BY c.course_code""", "sections")]),
    "classrooms": dict(
        table="classrooms", pk="room_id", singular="Classroom", plural="Classrooms", icon="door-open",
        fields=[F("building", "Building / location"), F("room_number", "Room number"),
                F("capacity", "Capacity", "number", True, min=1)],
        sql="SELECT room_id AS id, building, room_number AS room, capacity FROM classrooms",
        columns=["building", "room", "capacity"], search=["building", "room"],
        related=[("Sections held in this room", """SELECT sec.section_id AS id, sem.semester_name AS semester, c.course_code AS code,
                      sec.days, sec.start_time || '-' || sec.end_time AS time
                      FROM sections sec JOIN courses c ON c.course_id = sec.course_id
                      JOIN semesters sem ON sem.semester_id = sec.semester_id
                      WHERE sec.room_id = ? ORDER BY sem.start_date""", "sections")]),
    "sections": dict(
        table="sections", pk="section_id", singular="Section", plural="Sections", icon="diagram-3",
        fields=[F("course_id", "Course", "select", True, options="courses"),
                F("semester_id", "Semester", "select", True, options="semesters"),
                F("instructor_id", "Instructor", "select", True, options="instructors"),
                F("room_id", "Classroom", "select", True, options="classrooms"),
                F("section_no", "Section number", "number", True, min=1, default=1),
                F("days", "Days", "text", True, help="Dash-separated: SUN-TUE-THU"),
                F("start_time", "Start time", "time"), F("end_time", "End time", "time"),
                F("max_capacity", "Capacity", "number", True, min=1, default=30)],
        sql="""SELECT sec.section_id AS id, c.course_code AS code, c.course_name AS course, sem.semester_name AS semester,
                      sec.section_no AS no, i.first_name || ' ' || i.last_name AS instructor,
                      r.building || ' ' || r.room_number AS room, sec.days, sec.start_time || '-' || sec.end_time AS time,
                      (SELECT COUNT(*) FROM enrollments e WHERE e.section_id = sec.section_id AND e.status = 'ENROLLED') || '/' || sec.max_capacity AS enrolled
               FROM sections sec JOIN courses c ON c.course_id = sec.course_id
               JOIN semesters sem ON sem.semester_id = sec.semester_id
               JOIN instructors i ON i.instructor_id = sec.instructor_id
               JOIN classrooms r ON r.room_id = sec.room_id""",
        columns=["code", "course", "semester", "no", "instructor", "room", "days", "time", "enrolled"],
        search=["code", "course", "semester", "instructor"],
        related=[("Enrolled students", """SELECT s.student_id AS id, s.first_name || ' ' || s.last_name AS name, e.status, e.enroll_date AS since, e.grade
                      FROM enrollments e JOIN students s ON s.student_id = e.student_id
                      WHERE e.section_id = ? ORDER BY e.status, s.last_name""", "students")]),
}


# ---------------------------------------------------------------- validation helpers
def overlap(days_a, s_a, e_a, days_b, s_b, e_b):
    """True when two timetable slots share a day and their times overlap."""
    return bool(set(days_a.split("-")) & set(days_b.split("-"))) and s_a < e_b and s_b < e_a


def section_conflicts(v, ignore_id=None):
    errs = []
    rows = Q("""SELECT sec.*, c.course_code FROM sections sec JOIN courses c ON c.course_id = sec.course_id
                WHERE sec.semester_id = ? AND sec.section_id <> ?""", (v["semester_id"], ignore_id or -1))
    for r in rows:
        if overlap(v["days"], v["start_time"], v["end_time"], r["days"], r["start_time"], r["end_time"]):
            if r["instructor_id"] == v["instructor_id"]:
                errs.append(f"Instructor is already teaching {r['course_code']} at that time.")
            if r["room_id"] == v["room_id"]:
                errs.append(f"Classroom is already booked by {r['course_code']} at that time.")
    return errs


def validate(entity, v, ignore_id=None):
    """Entity specific business rules. Returns a list of error messages."""
    e = []
    if entity in ("students", "instructors") and v.get("email") and not EMAIL_RE.match(v["email"]):
        e.append("Email address is not valid.")
    if entity == "students" and v.get("birth_date") and v["birth_date"] >= date.today().isoformat():
        e.append("Birth date must be in the past.")
    if entity == "courses" and v.get("course_code"):
        v["course_code"] = v["course_code"].upper()
        if not re.match(r"^[A-Z]{2,5}\d{3}$", v["course_code"]):
            e.append("Course code must look like CS101 (2-5 letters + 3 digits).")
    if entity == "semesters" and v.get("start_date") and v.get("end_date") and v["end_date"] <= v["start_date"]:
        e.append("End date must be after the start date.")
    if entity == "sections":
        days = (v.get("days") or "").upper()
        v["days"] = days
        if not days or any(d not in DAYS for d in days.split("-")):
            e.append("Days must be dash-separated from: " + ", ".join(DAYS))
        for k in ("start_time", "end_time"):
            if v.get(k) and not TIME_RE.match(v[k]):
                e.append(f"{k.replace('_', ' ').title()} must be HH:MM.")
        if not e and v["end_time"] <= v["start_time"]:
            e.append("End time must be after start time.")
        if not e:
            room = Q1("SELECT capacity FROM classrooms WHERE room_id = ?", (v["room_id"],))
            if room and v["max_capacity"] > room["capacity"]:
                e.append(f"Section capacity ({v['max_capacity']}) exceeds the classroom capacity ({room['capacity']}).")
            e += section_conflicts(v, ignore_id)
    return e


def parse_form(ent, form):
    """Convert posted strings into typed values; returns (values, errors)."""
    values, errors = {}, []
    for f in ent["fields"]:
        raw = (form.get(f["name"]) or "").strip()
        if raw == "":
            if f["required"]:
                errors.append(f"{f['label']} is required.")
            values[f["name"]] = None
            continue
        if f["type"] == "number" or (f["type"] == "select" and isinstance(f["options"], str)):
            try:
                n = float(raw) if f["name"] == "salary" else int(raw)
            except ValueError:
                errors.append(f"{f['label']} must be a number.")
                values[f["name"]] = None
                continue
            if f["min"] is not None and n < f["min"]:
                errors.append(f"{f['label']} must be at least {f['min']}.")
            if f["max"] is not None and n > f["max"]:
                errors.append(f"{f['label']} must be at most {f['max']}.")
            values[f["name"]] = n
        elif f["type"] == "select" and isinstance(f["options"], list):
            if raw not in [o[0] for o in f["options"]]:
                errors.append(f"{f['label']} has an invalid value.")
            values[f["name"]] = raw
        elif f["type"] == "date":
            try:
                date.fromisoformat(raw)
            except ValueError:
                errors.append(f"{f['label']} must be a valid date.")
            values[f["name"]] = raw
        else:
            values[f["name"]] = raw[:200]
    return values, errors


def friendly_integrity(exc):
    m = str(exc)
    if "UNIQUE" in m:
        return "A record with the same unique value (email, code, name...) already exists."
    if "FOREIGN KEY" in m:
        return "This record is referenced by other records (or references one that does not exist)."
    if "CHECK" in m:
        return "A value is outside the allowed range."
    return "The database rejected this change."


def field_options(ent):
    out = {}
    for f in ent["fields"]:
        if f["type"] == "select":
            if isinstance(f["options"], list):
                out[f["name"]] = f["options"]
            else:
                rows = get_db().execute(OPT[f["options"]]).fetchall()
                out[f["name"]] = [(r[0], r[1]) for r in rows]
    return out


# ---------------------------------------------------------------- dashboard
@app.route("/")
def dashboard():
    stats = Q1("""SELECT (SELECT COUNT(*) FROM students)    AS students,
                          (SELECT COUNT(*) FROM instructors) AS instructors,
                          (SELECT COUNT(*) FROM departments) AS departments,
                          (SELECT COUNT(*) FROM courses)     AS courses,
                          (SELECT COUNT(*) FROM sections)    AS sections,
                          (SELECT COUNT(*) FROM enrollments WHERE status = 'ENROLLED') AS enrollments""")
    recent = Q("""SELECT e.enrollment_id, s.first_name || ' ' || s.last_name AS student, c.course_code, sem.semester_name,
                         e.status, e.enroll_date
                  FROM enrollments e JOIN students s ON s.student_id = e.student_id
                  JOIN sections sec ON sec.section_id = e.section_id JOIN courses c ON c.course_id = sec.course_id
                  JOIN semesters sem ON sem.semester_id = sec.semester_id
                  ORDER BY e.enrollment_id DESC LIMIT 8""")
    per_dept = Q("""SELECT d.dept_name, COUNT(s.student_id) AS n FROM departments d
                    LEFT JOIN students s ON s.dept_id = d.dept_id GROUP BY d.dept_id ORDER BY n DESC""")
    return render_template("dashboard.html", stats=stats, recent=recent, per_dept=per_dept)


# ---------------------------------------------------------------- generic CRUD
def get_entity(name):
    ent = ENTITIES.get(name)
    if not ent:
        abort(404, "Unknown page.")
    return ent


@app.route("/<entity>/")
def list_view(entity):
    ent = get_entity(entity)
    term = request.args.get("q", "").strip()
    sql = f"SELECT * FROM ({ent['sql']})"
    params = []
    if term:
        sql += " WHERE " + " OR ".join(f"CAST({c} AS TEXT) LIKE ?" for c in ent["search"])
        params = [f"%{term}%"] * len(ent["search"])
    rows = Q(sql + " ORDER BY id", params)
    return render_template("list.html", ent=ent, key=entity, rows=rows, term=term)


@app.route("/<entity>/new", methods=["GET", "POST"])
def create_view(entity):
    ent = get_entity(entity)
    return form_view(entity, ent, None)


@app.route("/<entity>/<int:rid>/edit", methods=["GET", "POST"])
def edit_view(entity, rid):
    ent = get_entity(entity)
    if not Q1(f"SELECT 1 AS x FROM {ent['table']} WHERE {ent['pk']} = ?", (rid,)):
        abort(404, f"{ent['singular']} not found.")
    return form_view(entity, ent, rid)


def form_view(entity, ent, rid):
    values, errors = {}, []
    if request.method == "POST":
        values, errors = parse_form(ent, request.form)
        if not errors:
            errors = validate(entity, values, rid)
        if not errors:
            names = [f["name"] for f in ent["fields"]]
            conn = get_db()
            try:
                if rid is None:
                    conn.execute(f"INSERT INTO {ent['table']} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                                 [values[n] for n in names])
                else:
                    conn.execute(f"UPDATE {ent['table']} SET {', '.join(n + ' = ?' for n in names)} WHERE {ent['pk']} = ?",
                                 [values[n] for n in names] + [rid])
                conn.commit()
                flash(f"{ent['singular']} {'created' if rid is None else 'updated'} successfully.", "success")
                return redirect(url_for("list_view", entity=entity))
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                errors = [friendly_integrity(exc)]
        for msg in errors:
            flash(msg, "danger")
    elif rid is not None:
        values = Q1(f"SELECT * FROM {ent['table']} WHERE {ent['pk']} = ?", (rid,))
    else:
        values = {f["name"]: (date.today().isoformat() if f["default"] == "today" else f["default"]) for f in ent["fields"]}
    return render_template("form.html", ent=ent, key=entity, values=values, rid=rid, options=field_options(ent))


@app.route("/<entity>/<int:rid>")
def detail_view(entity, rid):
    ent = get_entity(entity)
    row = Q1(f"SELECT * FROM ({ent['sql']}) WHERE id = ?", (rid,))
    if not row:
        abort(404, f"{ent['singular']} not found.")
    related = [(title, Q(sql, (rid,)), link) for title, sql, link in ent["related"]]
    extra = {}
    if ent.get("gpa"):
        extra["gpa"] = Q1("SELECT gpa, graded_hours FROM v_student_gpa WHERE student_id = ?", (rid,))
    if ent.get("prereq"):
        extra["prereqs"] = Q("""SELECT c.course_id AS id, c.course_code, c.course_name FROM course_prerequisites p
                                JOIN courses c ON c.course_id = p.prereq_id WHERE p.course_id = ?""", (rid,))
        extra["candidates"] = Q("SELECT course_id, course_code, course_name FROM courses WHERE course_id <> ? ORDER BY course_code", (rid,))
    if entity == "sections":
        extra["load"] = Q1("SELECT enrolled, max_capacity FROM v_section_load WHERE section_id = ?", (rid,))
    return render_template("detail.html", ent=ent, key=entity, row=row, related=related, extra=extra, rid=rid)


@app.route("/<entity>/<int:rid>/delete", methods=["POST"])
def delete_view(entity, rid):
    ent = get_entity(entity)
    conn = get_db()
    try:
        cur = conn.execute(f"DELETE FROM {ent['table']} WHERE {ent['pk']} = ?", (rid,))
        conn.commit()
        flash(f"{ent['singular']} deleted." if cur.rowcount else f"{ent['singular']} not found.",
              "success" if cur.rowcount else "warning")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash(f"Cannot delete this {ent['singular'].lower()}: other records depend on it "
              f"(remove or reassign them first).", "danger")
    return redirect(url_for("list_view", entity=entity))


# ---------------------------------------------------------------- prerequisites
@app.route("/courses/<int:cid>/prereq/add", methods=["POST"])
def prereq_add(cid):
    try:
        pid = int(request.form.get("prereq_id", ""))
    except ValueError:
        abort(400, "Choose a course.")
    conn = get_db()
    if pid == cid:
        flash("A course cannot be its own prerequisite.", "danger")
    elif Q1("SELECT 1 AS x FROM course_prerequisites WHERE course_id = ? AND prereq_id = ?", (cid, pid)):
        flash("This prerequisite already exists.", "danger")
    elif Q1("""WITH RECURSIVE up(id) AS (SELECT prereq_id FROM course_prerequisites WHERE course_id = ?
                UNION SELECT p.prereq_id FROM course_prerequisites p JOIN up ON p.course_id = up.id)
                SELECT 1 AS x FROM up WHERE id = ?""", (pid, cid)):
        flash("This would create a circular prerequisite chain.", "danger")
    else:
        try:
            conn.execute("INSERT INTO course_prerequisites (course_id, prereq_id) VALUES (?, ?)", (cid, pid))
            conn.commit()
            flash("Prerequisite added.", "success")
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            flash(friendly_integrity(exc), "danger")
    return redirect(url_for("detail_view", entity="courses", rid=cid))


@app.route("/courses/<int:cid>/prereq/<int:pid>/remove", methods=["POST"])
def prereq_remove(cid, pid):
    conn = get_db()
    conn.execute("DELETE FROM course_prerequisites WHERE course_id = ? AND prereq_id = ?", (cid, pid))
    conn.commit()
    flash("Prerequisite removed.", "success")
    return redirect(url_for("detail_view", entity="courses", rid=cid))


# ---------------------------------------------------------------- enrollment logic
def try_enroll(student_id, section_id):
    """Validate every enrollment rule, then insert/reactivate inside one transaction.
    Returns (ok, message)."""
    conn = get_db()
    stu = Q1("SELECT student_id, status FROM students WHERE student_id = ?", (student_id,))
    sec = Q1("SELECT * FROM sections WHERE section_id = ?", (section_id,))
    if not stu:
        return False, "Student does not exist."
    if not sec:
        return False, "Section does not exist."
    if stu["status"] != "ACTIVE":
        return False, f"Student is {stu['status'].lower()} and cannot enroll."
    existing = Q1("SELECT enrollment_id, status FROM enrollments WHERE student_id = ? AND section_id = ?", (student_id, section_id))
    if existing and existing["status"] == "ENROLLED":
        return False, "Student is already enrolled in this section."
    load = Q1("SELECT enrolled, max_capacity FROM v_section_load WHERE section_id = ?", (section_id,))
    if load["enrolled"] >= load["max_capacity"]:
        return False, f"Section is full ({load['enrolled']}/{load['max_capacity']})."
    missing = Q("""SELECT c.course_code FROM course_prerequisites p JOIN courses c ON c.course_id = p.prereq_id
                   WHERE p.course_id = ? AND NOT EXISTS (
                       SELECT 1 FROM enrollments e JOIN sections s2 ON s2.section_id = e.section_id
                       WHERE e.student_id = ? AND s2.course_id = p.prereq_id AND e.status = 'ENROLLED' AND e.grade >= 60)""",
                (sec["course_id"], student_id))
    if missing:
        return False, "Missing prerequisites: " + ", ".join(m["course_code"] for m in missing) + " (passed with grade >= 60)."
    for r in Q("""SELECT s.*, c.course_code FROM enrollments e JOIN sections s ON s.section_id = e.section_id
                  JOIN courses c ON c.course_id = s.course_id
                  WHERE e.student_id = ? AND e.status = 'ENROLLED' AND s.semester_id = ?""", (student_id, sec["semester_id"])):
        if overlap(sec["days"], sec["start_time"], sec["end_time"], r["days"], r["start_time"], r["end_time"]):
            return False, f"Schedule conflict with {r['course_code']}."
    try:
        if existing:   # re-enroll after a drop
            conn.execute("UPDATE enrollments SET status = 'ENROLLED', grade = NULL, enroll_date = date('now') WHERE enrollment_id = ?",
                         (existing["enrollment_id"],))
        else:
            conn.execute("INSERT INTO enrollments (student_id, section_id) VALUES (?, ?)", (student_id, section_id))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return False, str(exc) if "ABORT" in str(exc) or "full" in str(exc) else friendly_integrity(exc)
    return True, "Student enrolled successfully."


@app.route("/enrollments/", methods=["GET", "POST"])
def enrollments():
    if request.method == "POST":
        try:
            sid, secid = int(request.form["student_id"]), int(request.form["section_id"])
        except (KeyError, ValueError):
            abort(400, "Choose a student and a section.")
        ok, msg = try_enroll(sid, secid)
        flash(msg, "success" if ok else "danger")
        return redirect(url_for("enrollments"))
    term = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    sql = """SELECT e.enrollment_id AS id, e.student_id, s.first_name || ' ' || s.last_name AS student,
                    c.course_code AS code, sem.semester_name AS semester, e.status, e.enroll_date, e.grade
             FROM enrollments e JOIN students s ON s.student_id = e.student_id
             JOIN sections sec ON sec.section_id = e.section_id JOIN courses c ON c.course_id = sec.course_id
             JOIN semesters sem ON sem.semester_id = sec.semester_id WHERE 1 = 1"""
    params = []
    if term:
        sql += " AND (s.first_name || ' ' || s.last_name LIKE ? OR c.course_code LIKE ? OR CAST(s.student_id AS TEXT) = ?)"
        params += [f"%{term}%", f"%{term}%", term]
    if status in ("ENROLLED", "DROPPED"):
        sql += " AND e.status = ?"
        params.append(status)
    rows = Q(sql + " ORDER BY e.enrollment_id DESC LIMIT 200", params)
    students = Q("SELECT student_id, first_name || ' ' || last_name AS name FROM students WHERE status = 'ACTIVE' ORDER BY name")
    sections = Q("SELECT section_id, course_code, semester_name, section_no, instructor, enrolled, max_capacity FROM v_section_load ORDER BY semester_name, course_code")
    return render_template("enrollments.html", rows=rows, students=students, sections=sections, term=term, status=status)


@app.route("/enrollments/<int:eid>/drop", methods=["POST"])
def enrollment_drop(eid):
    conn = get_db()
    cur = conn.execute("UPDATE enrollments SET status = 'DROPPED' WHERE enrollment_id = ? AND status = 'ENROLLED'", (eid,))
    conn.commit()
    flash("Enrollment dropped (history kept)." if cur.rowcount else "Nothing to drop.", "success" if cur.rowcount else "warning")
    return redirect(request.referrer or url_for("enrollments"))


@app.route("/enrollments/<int:eid>/grade", methods=["POST"])
def enrollment_grade(eid):
    raw = request.form.get("grade", "").strip()
    conn = get_db()
    try:
        grade = None if raw == "" else float(raw)
        if grade is not None and not 0 <= grade <= 100:
            raise ValueError
    except ValueError:
        flash("Grade must be a number between 0 and 100.", "danger")
        return redirect(request.referrer or url_for("enrollments"))
    cur = conn.execute("UPDATE enrollments SET grade = ? WHERE enrollment_id = ? AND status = 'ENROLLED'", (grade, eid))
    conn.commit()
    flash("Grade saved." if cur.rowcount else "Only active enrollments can be graded.", "success" if cur.rowcount else "warning")
    return redirect(request.referrer or url_for("enrollments"))


# ---------------------------------------------------------------- reports
REPORTS = [
    ("Students by department", "SELECT d.dept_name AS department, COUNT(s.student_id) AS students FROM departments d LEFT JOIN students s ON s.dept_id = d.dept_id GROUP BY d.dept_id ORDER BY students DESC, d.dept_name"),
    ("Courses by department", "SELECT d.dept_name AS department, c.course_code AS code, c.course_name AS course, c.credit_hours AS credits FROM courses c JOIN departments d ON d.dept_id = c.dept_id ORDER BY d.dept_name, c.course_code"),
    ("Sections offered in each semester", "SELECT sem.semester_name AS semester, COUNT(sec.section_id) AS sections FROM semesters sem LEFT JOIN sections sec ON sec.semester_id = sem.semester_id GROUP BY sem.semester_id ORDER BY sem.start_date"),
    ("Instructors and the sections they teach", "SELECT i.first_name || ' ' || i.last_name AS instructor, c.course_code AS code, sem.semester_name AS semester, sec.days, sec.start_time || '-' || sec.end_time AS time FROM sections sec JOIN instructors i ON i.instructor_id = sec.instructor_id JOIN courses c ON c.course_id = sec.course_id JOIN semesters sem ON sem.semester_id = sec.semester_id ORDER BY instructor, sem.start_date"),
    ("Students enrolled in CS101 (Fall 2025)", "SELECT s.student_id AS id, s.first_name || ' ' || s.last_name AS student, e.grade FROM enrollments e JOIN students s ON s.student_id = e.student_id JOIN sections sec ON sec.section_id = e.section_id JOIN courses c ON c.course_id = sec.course_id JOIN semesters sem ON sem.semester_id = sec.semester_id WHERE c.course_code = 'CS101' AND sem.semester_name = 'Fall 2025' AND e.status = 'ENROLLED' ORDER BY s.student_id"),
    ("Enrollment count per section", "SELECT course_code AS code, semester_name AS semester, section_no AS no, enrolled, max_capacity AS capacity, seats_left FROM v_section_load ORDER BY semester_name, course_code"),
    ("Student enrollment history and grades (student 1)", "SELECT semester_name AS semester, course_code AS code, course_name AS course, status, grade, letter_grade AS letter FROM v_student_transcript WHERE student_id = 1 ORDER BY start_date"),
    ("Departments ranked by student count", "SELECT RANK() OVER (ORDER BY COUNT(s.student_id) DESC) AS rank, d.dept_name AS department, COUNT(s.student_id) AS students FROM departments d LEFT JOIN students s ON s.dept_id = d.dept_id GROUP BY d.dept_id ORDER BY rank, department"),
    ("Courses with no section in the latest semester", "SELECT c.course_code AS code, c.course_name AS course FROM courses c WHERE NOT EXISTS (SELECT 1 FROM sections sec WHERE sec.course_id = c.course_id AND sec.semester_id = (SELECT semester_id FROM semesters ORDER BY start_date DESC LIMIT 1)) ORDER BY c.course_code"),
    ("Students who have not enrolled in any section", "SELECT s.student_id AS id, s.first_name || ' ' || s.last_name AS student, d.dept_name AS department FROM students s JOIN departments d ON d.dept_id = s.dept_id WHERE s.student_id NOT IN (SELECT student_id FROM enrollments) ORDER BY s.student_id"),
    ("Top 3 students by GPA", "SELECT student_name AS student, graded_hours AS hours, gpa FROM v_student_gpa ORDER BY gpa DESC, student_name LIMIT 3"),
    ("Average grade per course (subquery)", "SELECT code, ROUND(avg_grade, 1) AS average FROM (SELECT course_code AS code, AVG(grade) AS avg_grade FROM v_student_transcript WHERE grade IS NOT NULL AND status = 'ENROLLED' GROUP BY course_code) ORDER BY average DESC"),
]


@app.route("/reports/")
def reports():
    results = []
    for title, sql in REPORTS:
        rows = Q(sql)
        results.append((title, rows))
    return render_template("reports.html", results=results)


if __name__ == "__main__":
    if not os.path.exists(db.DB_PATH):
        db.init_db().close()
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
