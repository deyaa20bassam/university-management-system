# University Management System

A relational database system for university management, integrated with a web application built using Flask, SQLite, and Bootstrap to manage university data efficiently.

| | |
|---|---|
| **Author** | _DEYYA BASSAM_ |
| **Student ID** | _183198_ |
| **Course** | _DATA BASE_ |
| **University** | _JUST_ |
| **Date** | _12/10/2026_ |

---

## 1. What the project does

The system manages the academic data of a university:

- **Departments, instructors, students, courses, semesters, classrooms and sections** – add, edit, view, search and delete.
- **Course prerequisites** – a course can require other courses (no self-prerequisite, no duplicates, no circular chains).
- **Enrollment** – students are enrolled in sections with rules checked automatically (see section 4).
- **Grades, transcripts and GPA** – grades are stored per enrollment; GPA is calculated by a database view.
- **Dashboard and 12 reports** – live statistics and SQL reports (joins, aggregates, subqueries, a window function).

## 2. Technologies

| Part | Technology |
|---|---|
| Database | SQLite 3 (SQL scripts) |
| Backend | Python 3 + Flask |
| Frontend | HTML5, CSS3, Bootstrap 5, a little JavaScript |
| Database design | ERDPlus |
| Tests | Python `unittest` |
| Environment | Google Colab and VS Code |

> **Why SQLite?** A MySQL server is not reliably available in Google Colab, so SQLite was used. The SQL is mostly standard; only data types, `AUTOINCREMENT` and trigger syntax are SQLite-specific.

## 3. Database design

- **ER diagram:** `docs/erd.png` (created in ERDPlus)
- **Nine tables:** `departments`, `instructors`, `students`, `courses`, `course_prerequisites`, `semesters`, `classrooms`, `sections`, `enrollments`
- **Many-to-many relationships** are resolved with associative tables:
  - Student ↔ Section through `enrollments`
  - Course ↔ Course (prerequisites) through `course_prerequisites`
- **Constraints:** primary keys, foreign keys with `ON DELETE` / `ON UPDATE` rules, `NOT NULL`, `UNIQUE`, `CHECK`, and indexes on frequently searched columns.
- **Views:** `v_student_transcript`, `v_student_gpa`, `v_section_load`
- **Triggers:** `trg_enroll_capacity` and `trg_enroll_prereq` (a safety net in the database itself)
- **Normalization:** designed to Third Normal Form (3NF) – see `docs/DATA_DICTIONARY.md`.

## 4. Business rules

| Rule | Where it is enforced |
|---|---|
| A student cannot enroll twice in the same section | `UNIQUE (student_id, section_id)` + application check |
| A section cannot exceed its capacity | trigger + application check |
| Prerequisites must be passed (grade ≥ 60) | trigger + application check |
| A student cannot have two overlapping classes | application check |
| An instructor or classroom cannot be double-booked | application check when saving a section |
| Section capacity cannot exceed the classroom capacity | application check |
| Records with dependants cannot be deleted | foreign keys (`RESTRICT`) |
| Dropping a course keeps the history | `status = 'DROPPED'` instead of deleting the row |

## 5. Project structure

```
university-flask/
├── app.py               Flask application: routes and business rules
├── db.py                Database connection helpers
├── schema.sql           Tables, indexes, views, triggers
├── sample_data.sql      Fictional sample data (24 students, 15 sections, 73 enrollments)
├── queries.sql          The report queries and extra SQL examples
├── templates/           HTML pages (Jinja2 + Bootstrap)
├── static/              CSS and JavaScript
├── tests/test_app.py    38 automated tests
├── tools/               Helper scripts
├── docs/                ER diagram, data dictionary, defense Q&A, screenshots
└── University_Flask_Colab.ipynb   Notebook that builds and runs everything in Colab
```

## 6. How to run

### On your computer (Windows, macOS, Linux)
```bash
pip install flask
python app.py
```
Open **http://127.0.0.1:5000** in a browser. Stop the server with `Ctrl + C`.
The database file `university.db` is created automatically the first time. To reset the data, delete `university.db` and start the app again.

### On Google Colab
1. Open https://colab.research.google.com → **File → Upload notebook** → choose `University_Flask_Colab.ipynb`.
2. **Runtime → Run all**. The site appears under the cell titled "Run the website".

## 7. Tests

```bash
python -m unittest discover -s tests -v
```
The 38 tests cover: table creation, foreign keys, duplicate enrollment, invalid references, capacity limit, prerequisites, CRUD from the web interface, dashboard numbers versus the database, reports, CSRF protection and SQL-injection attempts.

## 8. Security

- All SQL uses parameters (`?`) – no user input is concatenated into queries.
- Forms are protected with a CSRF token.
- Input is validated on the server; database errors are shown as friendly messages.



## 9. Limitations and future work

- No login or user roles.
- SQLite instead of a client/server database such as MySQL or Oracle.
- The Colab link is temporary; this is not a production deployment.
- Possible improvements: authentication, pagination, export to PDF/Excel, a MySQL version.
