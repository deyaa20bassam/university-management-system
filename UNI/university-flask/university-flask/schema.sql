-- University Management System - schema (SQLite)
-- Run order is dependency-safe. departments.head_id is a FK to instructors, which
-- is allowed because SQLite only checks FKs when rows are written.
PRAGMA foreign_keys = ON;

CREATE TABLE departments (
    dept_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_name TEXT NOT NULL UNIQUE,
    building  TEXT,
    head_id   INTEGER,
    FOREIGN KEY (head_id) REFERENCES instructors(instructor_id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE instructors (
    instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT,
    hire_date     TEXT NOT NULL DEFAULT (date('now')),
    salary        REAL CHECK (salary > 0),
    dept_id       INTEGER NOT NULL,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE students (
    student_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    phone       TEXT,
    birth_date  TEXT,
    gender      TEXT CHECK (gender IN ('M','F')),
    enroll_date TEXT NOT NULL DEFAULT (date('now')),
    status      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','GRADUATED','SUSPENDED')),
    dept_id     INTEGER NOT NULL,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE courses (
    course_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code  TEXT NOT NULL UNIQUE,
    course_name  TEXT NOT NULL,
    credit_hours INTEGER NOT NULL CHECK (credit_hours BETWEEN 1 AND 6),
    dept_id      INTEGER NOT NULL,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Prerequisite: associative table resolving the M:N "course requires course"
CREATE TABLE course_prerequisites (
    course_id INTEGER NOT NULL,
    prereq_id INTEGER NOT NULL,
    PRIMARY KEY (course_id, prereq_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (prereq_id) REFERENCES courses(course_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (course_id <> prereq_id)
);

CREATE TABLE semesters (
    semester_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    semester_name TEXT NOT NULL UNIQUE,
    academic_year TEXT NOT NULL,
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    CHECK (end_date > start_date)
);

CREATE TABLE classrooms (
    room_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    building    TEXT NOT NULL,
    room_number TEXT NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    UNIQUE (building, room_number)
);

CREATE TABLE sections (
    section_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL,
    semester_id   INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    room_id       INTEGER NOT NULL,
    section_no    INTEGER NOT NULL DEFAULT 1 CHECK (section_no > 0),
    days          TEXT NOT NULL,
    start_time    TEXT NOT NULL,
    end_time      TEXT NOT NULL,
    max_capacity  INTEGER NOT NULL DEFAULT 30 CHECK (max_capacity > 0),
    CHECK (end_time > start_time),
    FOREIGN KEY (course_id)     REFERENCES courses(course_id)         ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (semester_id)   REFERENCES semesters(semester_id)     ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (room_id)       REFERENCES classrooms(room_id)        ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (course_id, semester_id, section_no)
);

-- Enrollment: associative table Student <-> Section. Dropping keeps the row
-- (status = 'DROPPED') so history is never lost.
CREATE TABLE enrollments (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL,
    section_id    INTEGER NOT NULL,
    enroll_date   TEXT NOT NULL DEFAULT (date('now')),
    status        TEXT NOT NULL DEFAULT 'ENROLLED' CHECK (status IN ('ENROLLED','DROPPED')),
    grade         REAL CHECK (grade BETWEEN 0 AND 100),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (section_id) REFERENCES sections(section_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (student_id, section_id)
);

-- Indexes for commonly searched / joined columns
CREATE INDEX idx_students_dept   ON students(dept_id);
CREATE INDEX idx_students_name   ON students(last_name, first_name);
CREATE INDEX idx_instr_dept      ON instructors(dept_id);
CREATE INDEX idx_courses_dept    ON courses(dept_id);
CREATE INDEX idx_sections_course ON sections(course_id);
CREATE INDEX idx_sections_sem    ON sections(semester_id);
CREATE INDEX idx_sections_instr  ON sections(instructor_id);
CREATE INDEX idx_enr_student     ON enrollments(student_id);
CREATE INDEX idx_enr_section     ON enrollments(section_id);

-- ---------------------------------------------------------------- views
CREATE VIEW v_student_transcript AS
SELECT s.student_id,
       s.first_name || ' ' || s.last_name AS student_name,
       e.enrollment_id, e.status, sec.section_id,
       sem.semester_name, sem.start_date,
       c.course_code, c.course_name, c.credit_hours, e.grade,
       CASE WHEN e.status = 'DROPPED' THEN 'Dropped'
            WHEN e.grade IS NULL THEN 'In Progress'
            WHEN e.grade >= 90 THEN 'A' WHEN e.grade >= 80 THEN 'B'
            WHEN e.grade >= 70 THEN 'C' WHEN e.grade >= 60 THEN 'D' ELSE 'F' END AS letter_grade,
       CASE WHEN e.status = 'DROPPED' OR e.grade IS NULL THEN NULL
            WHEN e.grade >= 90 THEN 4 WHEN e.grade >= 80 THEN 3
            WHEN e.grade >= 70 THEN 2 WHEN e.grade >= 60 THEN 1 ELSE 0 END AS grade_points
FROM enrollments e
JOIN students  s   ON s.student_id    = e.student_id
JOIN sections  sec ON sec.section_id  = e.section_id
JOIN courses   c   ON c.course_id     = sec.course_id
JOIN semesters sem ON sem.semester_id = sec.semester_id;

CREATE VIEW v_student_gpa AS
SELECT student_id, student_name,
       SUM(credit_hours) AS graded_hours,
       ROUND(1.0 * SUM(grade_points * credit_hours) / SUM(credit_hours), 2) AS gpa
FROM v_student_transcript
WHERE grade_points IS NOT NULL
GROUP BY student_id, student_name;

CREATE VIEW v_section_load AS
SELECT sec.section_id, c.course_code, c.course_name, sem.semester_name, sec.section_no,
       i.first_name || ' ' || i.last_name AS instructor,
       sec.max_capacity,
       COUNT(e.enrollment_id) AS enrolled,
       sec.max_capacity - COUNT(e.enrollment_id) AS seats_left
FROM sections sec
JOIN courses c     ON c.course_id     = sec.course_id
JOIN semesters sem ON sem.semester_id = sec.semester_id
JOIN instructors i ON i.instructor_id = sec.instructor_id
LEFT JOIN enrollments e ON e.section_id = sec.section_id AND e.status = 'ENROLLED'
GROUP BY sec.section_id;

-- ---------------------------------------------------------------- triggers
-- Database-level safety net (the web app validates first and shows friendly messages).
CREATE TRIGGER trg_enroll_capacity
BEFORE INSERT ON enrollments
WHEN NEW.status = 'ENROLLED'
BEGIN
    SELECT RAISE(ABORT, 'Section is full')
    WHERE (SELECT COUNT(*) FROM enrollments WHERE section_id = NEW.section_id AND status = 'ENROLLED')
       >= (SELECT max_capacity FROM sections WHERE section_id = NEW.section_id);
END;

CREATE TRIGGER trg_enroll_prereq
BEFORE INSERT ON enrollments
WHEN NEW.status = 'ENROLLED'
BEGIN
    SELECT RAISE(ABORT, 'Prerequisites not satisfied')
    WHERE EXISTS (
        SELECT 1 FROM course_prerequisites p
        JOIN sections s ON s.course_id = p.course_id
        WHERE s.section_id = NEW.section_id
          AND NOT EXISTS (
                SELECT 1 FROM enrollments e
                JOIN sections s2 ON s2.section_id = e.section_id
                WHERE e.student_id = NEW.student_id AND s2.course_id = p.prereq_id
                  AND e.status = 'ENROLLED' AND e.grade >= 60));
END;
