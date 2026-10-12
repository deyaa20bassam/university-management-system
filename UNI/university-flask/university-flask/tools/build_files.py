"""Generates queries.sql (from app.REPORTS) and the Colab notebook (embeds every project file with %%writefile)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import app

# ---------------- queries.sql
out = ["-- University Management System - report queries (SQLite)", "-- Same queries the web 'Reports' page runs.", ""]
for i, (title, sql) in enumerate(app.REPORTS, 1):
    out += [f"-- {i}. {title}", sql.strip() + ";", ""]
out += ["""-- 13. View: transcript of student 2
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
"""]
open("queries.sql", "w", encoding="utf-8").write("\n".join(out))

# ---------------- notebook
files = ["db.py", "app.py", "schema.sql", "sample_data.sql", "queries.sql", "static/css/app.css", "static/js/app.js",
         "tests/test_app.py"] + sorted("templates/" + f for f in os.listdir("templates"))
cells = []
def md(t): cells.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)})
def code(t): cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)})

md("""
# University Management System — Flask + SQLite on Google Colab
شغّل الخلايا **بالترتيب** (Runtime ← Run all). الخلايا من 1 إلى 3 بتجهّز المشروع، وخلية 4 بتشغّل الموقع.

> **قاعدة البيانات:** SQLite (جاهزة داخل Python). MySQL ما استخدمتها لأن إعداد سيرفر MySQL داخل Colab مش موثوق (بيحتاج تثبيت سيرفر وبينحذف مع الجلسة).
""")
md("## 1) Install dependencies")
code("!pip -q install flask\nimport flask; print('Flask', flask.__version__)")
md("## 2) Create the project folder and files\nكل خلية تحت بتكتب ملف من ملفات المشروع (`%%writefile`).")
code("import os\nos.makedirs('/content/university_app', exist_ok=True)\nfor d in ['templates', 'static/css', 'static/js', 'tests']:\n    os.makedirs(f'/content/university_app/{d}', exist_ok=True)\n%cd /content/university_app")
for f in files:
    body = open(f, encoding="utf-8").read()
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": ("%%writefile " + f + "\n" + body).splitlines(True)})
md("## 3) Create the database, verify tables, run the tests")
code("""
import db, sqlite3
conn = db.init_db()                     # runs schema.sql + sample_data.sql
import pandas as pd
print(pd.read_sql_query("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name", conn).to_string(index=False))
for t in ['departments','instructors','students','courses','course_prerequisites','semesters','classrooms','sections','enrollments']:
    print(f"{t:22}", conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], "rows")
print("Foreign key problems:", conn.execute("PRAGMA foreign_key_check").fetchall())
conn.close()
""")
code("!python -m unittest discover -s tests -v 2>&1 | tail -50")
md("""
## 4) Run the website
بعد التشغيل بيظهر الموقع داخل الدفتر (iframe). إذا بدك تفتحه بتبويب جديد استخدم السطر الثاني.
- الرابط مؤقت وخاص بجلستك فقط (بيشتغل طول ما الدفتر شغال)، وهو **مش نشر دائم**.
- ما بنستخدم ngrok ولا أي كلمات سر.
""")
code("""
import threading, importlib
from werkzeug.serving import make_server
import app as uni_app
importlib.reload(uni_app)

try: server.shutdown()                 # restart safely if this cell is re-run
except Exception: pass
server = make_server("0.0.0.0", 5000, uni_app.app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()

from google.colab import output
output.serve_kernel_port_as_iframe(5000, height=800)      # show inside the notebook
# output.serve_kernel_port_as_window(5000)                  # or: open in a new browser tab
""")
md("## 5) Stop the server / export the project for submission")
code("server.shutdown(); print('server stopped')")
code("""
import shutil
from google.colab import files
shutil.make_archive('/content/university_project', 'zip', '/content/university_app')
files.download('/content/university_project.zip')        # schema.sql, sample_data.sql, queries.sql, app.py ... + university.db
""")
md("""
### ملاحظات
- ملفات Colab مؤقتة: لما تنتهي الجلسة بتنمسح. نزّل الـ ZIP (خلية 5) أو احفظ الدفتر على GitHub (`File ← Save a copy in GitHub`).
- لتشغيل نفس المشروع على جهازك: فك الـ ZIP، `pip install flask`، `python app.py`، وافتح http://127.0.0.1:5000
""")
nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"colab": {"provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"}, "language_info": {"name": "python"}}, "cells": cells}
for i, c in enumerate(cells): c["id"] = f"c{i:03d}"
json.dump(nb, open("University_Flask_Colab.ipynb", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("queries.sql + notebook written;", len(cells), "cells")
