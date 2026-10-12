"""Run:  python -m unittest discover -s tests -v   (from the project folder)"""
import os, re, sys, sqlite3, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["UNI_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
import db, app as appmod   # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        db.init_db().close()                       # fresh DB for every test
        appmod.app.config["TESTING"] = True
        self.c = appmod.app.test_client()
        self.conn = db.connect()

    def tearDown(self):
        self.conn.close()

    def token(self):
        self.c.get("/")
        with self.c.session_transaction() as s:
            return s["csrf"]

    def post(self, url, data=None, follow=True):
        d = dict(data or {}); d["csrf_token"] = self.token()
        return self.c.post(url, data=d, follow_redirects=follow)

    def scalar(self, sql, p=()):
        return self.conn.execute(sql, p).fetchone()[0]


class TestDatabase(Base):
    def test_all_tables_created(self):
        names = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ["departments", "instructors", "students", "courses", "course_prerequisites",
                  "semesters", "classrooms", "sections", "enrollments"]:
            self.assertIn(t, names)

    def test_foreign_keys_valid(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_sample_data_every_table(self):
        for t in ["departments", "instructors", "students", "courses", "course_prerequisites",
                  "semesters", "classrooms", "sections", "enrollments"]:
            self.assertGreater(self.scalar(f"SELECT COUNT(*) FROM {t}"), 0, t)

    def test_duplicate_enrollment_rejected_by_db(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO enrollments (student_id, section_id) VALUES (1, 1)")

    def test_invalid_references_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO enrollments (student_id, section_id) VALUES (999, 1)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO sections (course_id, semester_id, instructor_id, room_id, days, start_time, end_time) VALUES (999,1,1,1,'SUN','08:00','09:00')")

    def test_capacity_trigger(self):          # section 11 has capacity 3 and 3 students
        with self.assertRaisesRegex(sqlite3.IntegrityError, "full"):
            self.conn.execute("INSERT INTO enrollments (student_id, section_id) VALUES (4, 11)")

    def test_prereq_trigger(self):            # student 24 never took CS101
        with self.assertRaisesRegex(sqlite3.IntegrityError, "Prerequisites"):
            self.conn.execute("INSERT INTO enrollments (student_id, section_id) VALUES (24, 6)")

    def test_self_prerequisite_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO course_prerequisites VALUES (1, 1)")

    def test_gpa_view(self):
        gpa = {r[0]: r[1] for r in self.conn.execute("SELECT student_id, gpa FROM v_student_gpa")}
        self.assertEqual(gpa[2], 4.0)   # Sara: 95,91,97,93 -> all A

    def test_student_delete_blocked_when_enrolled(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM students WHERE student_id = 1")


class TestEnrollmentRules(Base):
    def enroll(self, s, sec):
        with appmod.app.test_request_context():
            return appmod.try_enroll(s, sec)

    def test_ok(self):
        ok, msg = self.enroll(8, 12)          # Jood passed CS201 (68)
        self.assertTrue(ok, msg)

    def test_duplicate(self):
        ok, msg = self.enroll(1, 1); self.assertFalse(ok); self.assertIn("already", msg)

    def test_capacity(self):
        ok, msg = self.enroll(4, 11); self.assertFalse(ok); self.assertIn("full", msg)

    def test_prereq(self):
        ok, msg = self.enroll(24, 6); self.assertFalse(ok); self.assertIn("CS101", msg)

    def test_failed_prereq_grade(self):       # student 16 failed BA101 (58)
        ok, msg = self.enroll(16, 9); self.assertFalse(ok); self.assertIn("BA101", msg)

    def test_unknown_student_and_section(self):
        self.assertFalse(self.enroll(999, 1)[0]); self.assertFalse(self.enroll(1, 999)[0])

    def test_schedule_conflict(self):
        # student 5 is in section 13 (SUN-TUE-THU 13:00-14:00, Fall 2026); a new overlapping section is rejected
        self.conn.execute("INSERT INTO sections (course_id,semester_id,instructor_id,room_id,section_no,days,start_time,end_time,max_capacity) VALUES (6,3,7,3,2,'SUN-TUE-THU','13:30','14:30',50)")
        self.conn.commit()
        sid = self.scalar("SELECT MAX(section_id) FROM sections")
        ok, msg = self.enroll(5, sid); self.assertFalse(ok); self.assertIn("conflict", msg)

    def test_drop_then_reenroll_keeps_one_row(self):
        self.post("/enrollments/1/drop")
        self.assertEqual(self.scalar("SELECT status FROM enrollments WHERE enrollment_id = 1"), "DROPPED")
        ok, _ = self.enroll(1, 1); self.assertTrue(ok)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments WHERE student_id=1 AND section_id=1"), 1)

    def test_drop_frees_seat_but_keeps_history(self):
        before = self.scalar("SELECT enrolled FROM v_section_load WHERE section_id = 11")
        self.post("/enrollments/%d/drop" % self.scalar("SELECT enrollment_id FROM enrollments WHERE section_id=11 LIMIT 1"))
        self.assertEqual(self.scalar("SELECT enrolled FROM v_section_load WHERE section_id = 11"), before - 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments WHERE section_id = 11"), before)


class TestWeb(Base):
    def test_all_pages_load(self):
        for url in ["/", "/departments/", "/students/", "/instructors/", "/courses/", "/semesters/",
                    "/classrooms/", "/sections/", "/enrollments/", "/reports/", "/students/1", "/courses/3",
                    "/sections/11", "/departments/1", "/instructors/1", "/semesters/3", "/classrooms/1",
                    "/students/new", "/students/1/edit"]:
            self.assertEqual(self.c.get(url).status_code, 200, url)

    def test_404_and_unknown(self):
        self.assertEqual(self.c.get("/students/9999").status_code, 404)
        self.assertEqual(self.c.get("/nothing/").status_code, 404)

    def test_dashboard_matches_database(self):
        html = self.c.get("/").get_data(as_text=True)
        for key, sql in [("students", "SELECT COUNT(*) FROM students"), ("instructors", "SELECT COUNT(*) FROM instructors"),
                         ("departments", "SELECT COUNT(*) FROM departments"), ("courses", "SELECT COUNT(*) FROM courses"),
                         ("sections", "SELECT COUNT(*) FROM sections")]:
            m = re.search(r'data-stat="%s">(\d+)<' % key, html)
            self.assertEqual(int(m.group(1)), self.scalar(sql), key)

    def test_csrf_required(self):
        self.assertEqual(self.c.post("/students/1/delete").status_code, 400)

    def test_student_crud(self):
        form = dict(first_name="Test", last_name="User", email="test.user@std.uni.edu", gender="M",
                    enroll_date="2026-09-01", status="ACTIVE", dept_id="1")
        r = self.post("/students/new", form); self.assertIn("created successfully", r.get_data(as_text=True))
        sid = self.scalar("SELECT student_id FROM students WHERE email='test.user@std.uni.edu'")
        form["last_name"] = "Changed"
        r = self.post(f"/students/{sid}/edit", form); self.assertIn("updated successfully", r.get_data(as_text=True))
        self.assertEqual(self.scalar("SELECT last_name FROM students WHERE student_id=?", (sid,)), "Changed")
        r = self.post(f"/students/{sid}/delete"); self.assertIn("deleted", r.get_data(as_text=True))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM students WHERE student_id=?", (sid,)), 0)

    def test_duplicate_email_and_validation(self):
        form = dict(first_name="A", last_name="B", email="ahmad.saleh@std.uni.edu", gender="M",
                    enroll_date="2026-09-01", status="ACTIVE", dept_id="1")
        self.assertIn("already exists", self.post("/students/new", form).get_data(as_text=True))
        form.update(email="x@y.com", first_name="")
        self.assertIn("First name is required", self.post("/students/new", form).get_data(as_text=True))
        form.update(email="not-an-email", first_name="A")
        self.assertIn("Email address is not valid", self.post("/students/new", form).get_data(as_text=True))

    def test_delete_blocked_by_constraints(self):
        t = self.post("/departments/1/delete").get_data(as_text=True)
        self.assertIn("Cannot delete", t)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM departments WHERE dept_id=1"), 1)
        self.assertIn("Cannot delete", self.post("/students/1/delete").get_data(as_text=True))

    def test_semester_date_validation(self):
        form = dict(semester_name="Bad", academic_year="2030/2031", start_date="2030-05-01", end_date="2030-01-01")
        self.assertIn("End date must be after", self.post("/semesters/new", form).get_data(as_text=True))

    def test_section_validation(self):
        base = dict(course_id="1", semester_id="3", instructor_id="7", room_id="3", section_no="5",
                    days="MON", start_time="08:00", end_time="09:00", max_capacity="30")
        self.assertIn("created", self.post("/sections/new", base).get_data(as_text=True))
        self.assertIn("exceeds the classroom capacity", self.post("/sections/new", {**base, "section_no": "6", "max_capacity": "999"}).get_data(as_text=True))
        # instructor 1 teaches CS301 SUN-TUE-THU 09:00-10:00 in Fall 2026
        t = self.post("/sections/new", {**base, "section_no": "7", "instructor_id": "1", "days": "SUN", "start_time": "09:30", "end_time": "10:30"}).get_data(as_text=True)
        self.assertIn("Instructor is already teaching", t)
        self.assertIn("Days must be", self.post("/sections/new", {**base, "section_no": "8", "days": "XYZ"}).get_data(as_text=True))

    def test_prerequisite_rules(self):
        self.assertIn("own prerequisite", self.post("/courses/1/prereq/add", {"prereq_id": "1"}).get_data(as_text=True))
        self.assertIn("already exists", self.post("/courses/2/prereq/add", {"prereq_id": "1"}).get_data(as_text=True))
        self.assertIn("circular", self.post("/courses/1/prereq/add", {"prereq_id": "3"}).get_data(as_text=True))
        self.assertIn("Prerequisite added", self.post("/courses/5/prereq/add", {"prereq_id": "3"}).get_data(as_text=True))

    def test_grade_validation(self):
        self.assertIn("between 0 and 100", self.post("/enrollments/1/grade", {"grade": "150"}).get_data(as_text=True))
        self.assertIn("Grade saved", self.post("/enrollments/1/grade", {"grade": "91"}).get_data(as_text=True))

    def test_enroll_from_web(self):
        t = self.post("/enrollments/", {"student_id": "4", "section_id": "11"}).get_data(as_text=True)
        self.assertIn("Section is full", t)
        t = self.post("/enrollments/", {"student_id": "8", "section_id": "12"}).get_data(as_text=True)
        self.assertIn("enrolled successfully", t)

    def test_sql_injection_is_harmless(self):
        for payload in ["' OR '1'='1", "'; DROP TABLE students; --", "%' UNION SELECT * FROM students --"]:
            for url in ["/students/?q=", "/courses/?q=", "/enrollments/?q="]:
                self.assertEqual(self.c.get(url + payload).status_code, 200)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM students"), 24)
        self.assertEqual(len(self.c.get("/students/?q=' OR '1'='1").get_data(as_text=True).split("No records found")), 2)

    def test_search(self):
        t = self.c.get("/students/?q=Sara").get_data(as_text=True)
        self.assertIn("Sara Ali", t); self.assertNotIn("Ahmad Saleh", t)
        self.assertIn("Sara Ali", self.c.get("/students/?q=2").get_data(as_text=True))   # by id


class TestReports(Base):
    def run_report(self, title_part):
        for t, sql in appmod.REPORTS:
            if title_part in t:
                return [dict(r) for r in self.conn.execute(sql).fetchall()]
        self.fail(title_part)

    def test_all_reports_execute(self):
        for _, sql in appmod.REPORTS:
            self.conn.execute(sql).fetchall()

    def test_students_by_department(self):
        r = {x["department"]: x["students"] for x in self.run_report("Students by department")}
        self.assertEqual(r, {"Computer Science": 8 + 1, "Mathematics": 3, "Physics": 4, "Business": 6, "English": 2})

    def test_students_without_enrollment(self):
        self.assertEqual([x["id"] for x in self.run_report("not enrolled")], [23, 24])

    def test_courses_without_section(self):
        codes = {x["code"] for x in self.run_report("no section")}
        self.assertIn("CS410", codes); self.assertNotIn("CS301", codes)

    def test_top3(self):
        top = self.run_report("Top 3")
        self.assertEqual(len(top), 3)
        self.assertEqual([x["gpa"] for x in top], sorted([x["gpa"] for x in top], reverse=True))
        self.assertEqual(top[0]["gpa"], 4.0)

if __name__ == "__main__":
    unittest.main()
