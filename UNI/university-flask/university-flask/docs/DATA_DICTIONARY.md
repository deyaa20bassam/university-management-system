# Data Dictionary (SQLite)

| Table | Column | Type | Key / Constraint | Purpose |
|---|---|---|---|---|
| **departments** | dept_id | INTEGER | PK, autoincrement | Department id |
| | dept_name | TEXT | NOT NULL, UNIQUE | Name |
| | building | TEXT | | Location |
| | head_id | INTEGER | FK → instructors (SET NULL) | Department head |
| **instructors** | instructor_id | INTEGER | PK | Instructor id |
| | first_name, last_name | TEXT | NOT NULL | Name |
| | email | TEXT | NOT NULL, UNIQUE | Contact |
| | phone, hire_date | TEXT | | Contact / hire date |
| | salary | REAL | CHECK > 0 | Salary |
| | dept_id | INTEGER | FK → departments (RESTRICT) | Home department |
| **students** | student_id | INTEGER | PK | Student id |
| | first_name, last_name, email | TEXT | NOT NULL, email UNIQUE | Identity |
| | phone, birth_date | TEXT | | Optional details |
| | gender | TEXT | CHECK M/F | |
| | enroll_date | TEXT | NOT NULL | Admission date |
| | status | TEXT | CHECK ACTIVE/GRADUATED/SUSPENDED | Academic status |
| | dept_id | INTEGER | FK → departments | Major department |
| **courses** | course_id | INTEGER | PK | Course id |
| | course_code | TEXT | NOT NULL, UNIQUE | e.g. CS101 |
| | course_name | TEXT | NOT NULL | Title |
| | credit_hours | INTEGER | CHECK 1..6 | Credits |
| | dept_id | INTEGER | FK → departments | Owning department |
| **course_prerequisites** | course_id, prereq_id | INTEGER | composite PK, both FK → courses (CASCADE), CHECK course_id <> prereq_id | Resolves M:N "course requires course" |
| **semesters** | semester_id | INTEGER | PK | |
| | semester_name | TEXT | NOT NULL, UNIQUE | e.g. Fall 2026 |
| | academic_year | TEXT | NOT NULL | e.g. 2026/2027 |
| | start_date, end_date | TEXT | NOT NULL, CHECK end > start | Dates |
| **classrooms** | room_id | INTEGER | PK | |
| | building, room_number | TEXT | NOT NULL, UNIQUE together | Location |
| | capacity | INTEGER | CHECK > 0 | Seats |
| **sections** | section_id | INTEGER | PK | One offering of a course |
| | course_id, semester_id, instructor_id, room_id | INTEGER | FKs (RESTRICT) | Who/what/when/where |
| | section_no | INTEGER | UNIQUE with course + semester | |
| | days, start_time, end_time | TEXT | NOT NULL, CHECK end > start | Timetable |
| | max_capacity | INTEGER | CHECK > 0 | Seat limit |
| **enrollments** | enrollment_id | INTEGER | PK | |
| | student_id, section_id | INTEGER | FKs (RESTRICT), UNIQUE together | Resolves M:N Student–Section |
| | enroll_date | TEXT | NOT NULL | |
| | status | TEXT | CHECK ENROLLED/DROPPED | Drop keeps history |
| | grade | REAL | CHECK 0..100, NULL = in progress | |

Views: `v_student_transcript`, `v_student_gpa`, `v_section_load`. Triggers: `trg_enroll_capacity`, `trg_enroll_prereq`.

## Normalization (3NF)
- Every table has a single-valued primary key; all columns are atomic (1NF).
- Non-key columns depend on the whole key (2NF): composite-key tables (`course_prerequisites`) hold only key columns; `enrollments` uses a surrogate key.
- No transitive dependencies (3NF): department name is not repeated in students/courses, instructor details are not repeated in sections, GPA and letter grades are computed in views instead of stored.

## ER diagram review
The original `.erdplus` file was **not available to me** (only the earlier schema we built together from your diagram), so this schema follows that design. Additions beyond the nine entities' basic attributes (recommended, not claimed as original): `semesters.academic_year`, `enrollments.status`, `sections.days/start_time/end_time`.
