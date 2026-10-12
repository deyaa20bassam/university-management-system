-- University Management System - report queries (SQLite)
-- Same queries the web 'Reports' page runs.

-- 1. Students by department
SELECT d.dept_name AS department, COUNT(s.student_id) AS students FROM departments d LEFT JOIN students s ON s.dept_id = d.dept_id GROUP BY d.dept_id ORDER BY students DESC, d.dept_name;

-- 2. Courses by department
SELECT d.dept_name AS department, c.course_code AS code, c.course_name AS course, c.credit_hours AS credits FROM courses c JOIN departments d ON d.dept_id = c.dept_id ORDER BY d.dept_name, c.course_code;

-- 3. Sections offered in each semester
SELECT sem.semester_name AS semester, COUNT(sec.section_id) AS sections FROM semesters sem LEFT JOIN sections sec ON sec.semester_id = sem.semester_id GROUP BY sem.semester_id ORDER BY sem.start_date;

-- 4. Instructors and the sections they teach
SELECT i.first_name || ' ' || i.last_name AS instructor, c.course_code AS code, sem.semester_name AS semester, sec.days, sec.start_time || '-' || sec.end_time AS time FROM sections sec JOIN instructors i ON i.instructor_id = sec.instructor_id JOIN courses c ON c.course_id = sec.course_id JOIN semesters sem ON sem.semester_id = sec.semester_id ORDER BY instructor, sem.start_date;

-- 5. Students enrolled in CS101 (Fall 2025)
SELECT s.student_id AS id, s.first_name || ' ' || s.last_name AS student, e.grade FROM enrollments e JOIN students s ON s.student_id = e.student_id JOIN sections sec ON sec.section_id = e.section_id JOIN courses c ON c.course_id = sec.course_id JOIN semesters sem ON sem.semester_id = sec.semester_id WHERE c.course_code = 'CS101' AND sem.semester_name = 'Fall 2025' AND e.status = 'ENROLLED' ORDER BY s.student_id;

-- 6. Enrollment count per section
SELECT course_code AS code, semester_name AS semester, section_no AS no, enrolled, max_capacity AS capacity, seats_left FROM v_section_load ORDER BY semester_name, course_code;

-- 7. Student enrollment history and grades (student 1)
SELECT semester_name AS semester, course_code AS code, course_name AS course, status, grade, letter_grade AS letter FROM v_student_transcript WHERE student_id = 1 ORDER BY start_date;

-- 8. Departments ranked by student count
SELECT RANK() OVER (ORDER BY COUNT(s.student_id) DESC) AS rank, d.dept_name AS department, COUNT(s.student_id) AS students FROM departments d LEFT JOIN students s ON s.dept_id = d.dept_id GROUP BY d.dept_id ORDER BY rank, department;

-- 9. Courses with no section in the latest semester
SELECT c.course_code AS code, c.course_name AS course FROM courses c WHERE NOT EXISTS (SELECT 1 FROM sections sec WHERE sec.course_id = c.course_id AND sec.semester_id = (SELECT semester_id FROM semesters ORDER BY start_date DESC LIMIT 1)) ORDER BY c.course_code;

-- 10. Students who have not enrolled in any section
SELECT s.student_id AS id, s.first_name || ' ' || s.last_name AS student, d.dept_name AS department FROM students s JOIN departments d ON d.dept_id = s.dept_id WHERE s.student_id NOT IN (SELECT student_id FROM enrollments) ORDER BY s.student_id;

-- 11. Top 3 students by GPA
SELECT student_name AS student, graded_hours AS hours, gpa FROM v_student_gpa ORDER BY gpa DESC, student_name LIMIT 3;

-- 12. Average grade per course (subquery)
SELECT code, ROUND(avg_grade, 1) AS average FROM (SELECT course_code AS code, AVG(grade) AS avg_grade FROM v_student_transcript WHERE grade IS NOT NULL AND status = 'ENROLLED' GROUP BY course_code) ORDER BY average DESC;

-- 13. View: transcript of student 2
SELECT * FROM v_student_transcript WHERE student_id = 2;

-- 14. View: GPA of every student
SELECT * FROM v_student_gpa ORDER BY gpa DESC;

-- 15. Subquery: students whose GPA is above the average GPA
SELECT student_name, gpa FROM v_student_gpa WHERE gpa > (SELECT AVG(gpa) FROM v_student_gpa) ORDER BY gpa DESC;

-- 16. Failing grades (< 60)
SELECT student_name, course_code, semester_name, grade FROM v_student_transcript WHERE grade < 60 AND status = 'ENROLLED';

-- 17. Transaction: enroll a student and rollback if something goes wrong (run as one block)
BEGIN TRANSACTION;
INSERT INTO enrollments (student_id, section_id) VALUES (8, 12);
-- if the INSERT fails (full section / missing prerequisite) the trigger aborts and nothing is saved;
-- otherwise confirm with COMMIT, or undo with ROLLBACK:
ROLLBACK;
