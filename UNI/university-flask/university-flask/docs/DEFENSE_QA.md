# Possible questions at the project defense

1. **Why SQLite and not MySQL?** Colab has no MySQL server; installing one is slow and is lost when the session ends. SQLite supports all the SQL used here (joins, views, triggers, window function RANK). The SQL is portable; only types/AUTOINCREMENT/triggers syntax would change for MySQL.
2. **How is M:N handled?** Student–Section through `enrollments`; Course–Course (prerequisites) through `course_prerequisites`.
3. **How do you stop a full section?** The app checks seats first; the `trg_enroll_capacity` trigger is a second line of defence in the database.
4. **How are prerequisites validated?** A student needs an enrollment with grade ≥ 60 in each prerequisite course. The app lists the missing ones.
5. **What happens when a student drops a course?** `status` becomes `DROPPED`; the row and grade history stay, and the seat is freed.
6. **Why can't I delete a department/student?** Foreign keys use `ON DELETE RESTRICT`, so records with dependants cannot be deleted and the app shows a clear message.
7. **How do you prevent SQL injection?** Every query uses `?` parameters; the search box is passed as a parameter, and there is a unit test with injection strings.
8. **What is CSRF and how is it handled?** Every POST form carries a random per-session token that is verified before the request is processed.
9. **Why a view for GPA?** It keeps GPA derived (3NF) and reusable by the web app and the SQL reports.
10. **How do you detect schedule conflicts?** Two slots conflict when they share a day and `start_a < end_b AND start_b < end_a`; checked for instructors, rooms (sections) and students (enrollments).
11. **What is not implemented?** Login/roles, MySQL deployment, permanent hosting (the Colab URL is temporary).
12. **How did you test?** 38 automated tests (`python -m unittest discover -s tests`).
