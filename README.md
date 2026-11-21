# Sankalp AI

A web platform for diploma colleges to teach and test programming in a practical way.
See the full documentation (PDF) for the problem, solution and plan.

## Project layout

```
sankalp-ai/
  backend/    FastAPI + SQLAlchemy + Alembic (Python)
  frontend/   React + Vite + Tailwind CSS
```

## Run it on your computer

You need: Python 3.11+, Node.js (LTS), Git.

### 1. Backend

Windows (PowerShell):

```
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
alembic upgrade head
python -m app.scripts.create_super_admin --name "Your Name" --email you@example.com
python -m app.scripts.seed_starter_course
uvicorn app.main:app --reload
```

Mac / Linux:

```
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m app.scripts.create_super_admin --name "Your Name" --email you@example.com
python -m app.scripts.seed_starter_course
uvicorn app.main:app --reload
```

The `create_super_admin` command asks for a password (at least 8 characters).
This is the platform owner account. Run it once.

The `seed_starter_course` command adds the free starter course "C Programming Basics" (14 lessons) and
15 practice problems for it. It is safe to run again: nothing is added twice.

By default `backend/.env.example` uses `JUDGE_BACKEND=local`, which runs student code on your own computer
so you can develop. It is **not safe** for real students. See `deploy/judge0/README.md`.

Before real use, put your own long random value in `SECRET_KEY` inside `backend/.env`:
`python -c "import secrets; print(secrets.token_hex(32))"`

Open http://localhost:8000/api/v1/health. You should see `"status":"ok"`.
API docs are at http://localhost:8000/docs.

On Windows, if PowerShell blocks the activate script, run this once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 2. Frontend (open a second terminal)

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and log in with the super admin account you created.

### 3. Run the tests

```
cd backend && python -m pytest -q
cd frontend && npm test
```

## Using Supabase (PostgreSQL) instead of the local file

1. In Supabase: Project Settings > Database > Connection string > URI.
2. Put it in `backend/.env` as `DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres`
3. Run `alembic upgrade head` again. The tables are created in Supabase.

## Database changes

When you change a model in `backend/app/models/`:

```
alembic revision --autogenerate -m "short description"
alembic upgrade head
```

## How to try Phase 2 (first walk-through)

1. Log in as the platform owner. Open **Colleges** and add your college.
2. Open **People**, choose role "College admin", pick the college, and create the admin.
3. Log out. Log in as that admin. Add a teacher.
4. Log out. Log in as the teacher. Open **Batches** and create a batch.
5. In **People**, paste a list of students (`name, email` per line). Pick the batch. Save the passwords that appear. They are shown only once.
6. Log in as one of the students. They see their batch. Students cannot open People or Colleges.

## How to try Phase 3 (coding problems)

1. Make sure the languages you want are installed (Python needs nothing). Run
   `python -m app.scripts.check_judge` in the `backend` folder to see what works on your computer.
2. Log in as a teacher. Open **Problems > New problem**. Write a statement, add one sample test and a few hidden tests, and save.
3. Log in as a student of the same college. Open **Problems**, pick the problem, write code, press **Run** (your own input) and **Submit** (all tests).
4. The student sees the verdict. Sample tests show input, expected and own output. Hidden tests show only pass or fail.
5. The ticks in the problem list show which problems you solved.

Students can use C, C++, Java (class must be named `Main`) and Python. Code is saved in the browser while you type.

## How to try Phase 4 (courses and lessons)

1. Log in as a student. Open **Courses**. The starter course "C Programming Basics" is there.
2. Open it and press **Start the course**. Read the lesson. Every code example has a **Run** button.
   Change the code, change the **Input**, press **Run**. Press **Reset** to get the original back.
3. Press **Mark as done** at the end of a lesson. The progress bar on the course page goes up.
4. Log in as a teacher. Open the starter course and press **Make my own copy**.
5. In your copy you can rename units, move lessons up and down, add lessons, change the text and add a video link.
   The lesson editor shows a live preview with working examples.
6. Press **Publish** when you are ready. Students of your college can then see your course.
   Until then it is a **draft**: only you and your college admin can see it.

### Writing a lesson with a code example

Lessons are written in Markdown. To make a code example that students can run, write `run` after the language:

````
```c run
#include <stdio.h>
int main(void) {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d\n", a + b);
    return 0;
}
```
```stdin
12 30
```
````

The `stdin` block right after it is optional. It gives the default input. The languages that can run are
`c`, `cpp`, `java` and `python`. A code block without `run` is only shown, not run.

## How to try Phase 5 (assignments and exams)

You need a teacher, a batch with at least one student, and some problems (the starter course adds 15).

**As the teacher**
1. Open **Assessments > New assessment**. Choose the batch. Choose **Exam** or **Assignment**.
2. Set when it opens and closes. For an exam, also set the minutes each student gets.
   (A 60-minute exam inside a 2-hour window: every student can press Start any time in those 2 hours and then has 60 minutes.
   The timer never runs past the closing time.)
3. Pick the problems and give each one marks. Press **Create**. It is a **draft**: students cannot see it yet.
4. Press **Publish to students**.

**As a student of that batch**
5. Open **Assessments**. For an exam, read the rules and press **Start the exam**. The questions appear only now,
   and the timer starts. Write code, use **Run** to test it, press **Submit**. Your code is also saved on the server while you type.
6. In an exam you will not see verdicts or marks. You see "Answer received". In an assignment you see everything at once.
7. Press **Finish the exam**, or wait for the timer. If time ends with code you saved but never submitted, we submit it for you.

**As the teacher again**
8. Open the assessment and press **Results and marks**. You see every student, the marks for each problem, tab switches (exam only),
   and any answers still being checked.
9. Type a number in **Final marks** to change a student's mark by hand, and add a comment. Press **Save**.
10. Press **Download CSV** to get a spreadsheet. Press **Publish results to students** when you are ready.
    Only then do students see exam marks, verdicts and your comments.

### How marks work

- For each problem the student's **best** answer counts: `marks of the problem x (tests passed / tests in total)`.
  Example: a 10-mark problem where the best answer passes 3 of 4 tests gives 7.5.
- Automatic marks are always worked out fresh from the answers. Your hand-given mark is kept separately and wins.
- Run results never count. Only Submit counts.

### Rules that protect exams

- **Questions are secret** until the student presses Start. An exam's problems are also hidden from the normal Problems page
  for every student of the college until the exam window is over. (An assignment's problems are hidden until it starts.)
- **The server keeps the clock.** Changing the computer's clock does nothing. Answers after the deadline are refused.
- **Results stay hidden** until you publish them. This includes the green tick on the Problems page.
- **Tab switches** are counted and shown to you. Nobody is blocked, because a school computer can switch tabs by accident.
- The AI helper (Phase 6) will be switched off during an exam. The check for this already exists in the backend
  (`user_has_active_exam` in `backend/app/services/assessments.py`).

## Who can do what

| Action | Platform owner | College admin | Teacher | Student |
|---|---|---|---|---|
| Add colleges | yes | | | |
| Create college admins | yes | | | |
| Create teachers | yes | yes | | |
| Create students | yes | yes | yes | |
| Disable or enable an account | yes | yes (own college) | | |
| Give a new password | yes | yes (teachers, students) | yes (students) | |
| Create batches | | yes | yes | |
| See batches | | all in college | own batches | batches they are in |
| Create problems | shared bank (all colleges) | own college | own college | |
| Edit a problem | any | any in own college | only own problems | |
| See hidden test cases | yes | own college | own problems | never |
| Run and submit code | yes | yes | yes | yes |
| Read a submission | any | own college | own college | own only |
| Read published courses | all | own college and shared | own college and shared | own college and shared |
| See draft courses | all | all in own college | own drafts | never |
| Create and edit courses | shared courses | own college | own courses | |
| Make a copy of a course | yes | yes | yes | |
| Mark lessons as done | yes | yes | yes | yes |
| Create assignments and exams | | any batch of own college | own batches | |
| See marks, change marks, export CSV | | own college | own batches | |
| Take an assignment or exam | | | | own batch only |

People can only see and change data of their own college. Asking for another college's data
gives "not found", not "forbidden", so nobody can find out what exists elsewhere.

## Known limits (planned for later)

- Exam answers are judged when they are sent. If 60 students all submit in the same minute, a small judge server will take a while.
  The results page shows how many answers are still being checked and refreshes by itself.
- Saved code is submitted for a student when someone looks (the student's page, or your results page) after their time ended.
  There is no background timer. The marks are the same, only the moment of submitting differs.
- Questions are not shuffled per student. There is no camera or screen monitoring.
- You can change a student's total mark by hand, but not the mark of one problem.
- Students who leave the batch after an exam no longer appear in its results table.
- Times are shown in each person's own time zone. Make sure school computers have the right time zone.
- Judging uses one background task per submission inside the web server. This is fine for a class. For many hundreds of students at once, move to a real job queue.
- Teachers cannot see their students' course progress yet. Phase 7 (reports) adds that. Students see their own progress now.
- Lessons cannot be moved from one unit to another yet. Make a new lesson and paste the text.
- Videos are links that open in a new tab. They are not shown inside the page.
- A lesson example runs in your own judge, so one student pressing Run costs the same as a small submission.
- Problems cannot be deleted yet. Edit them instead (editing replaces the test cases).
- Judge0 itself is not tested here. Use `python -m app.scripts.check_judge` on your server.
- Password reset by email is not built yet. Teachers and admins give a new temporary password instead (button "New password" in People). Email reset needs an email provider, so it comes with deployment.
- Login uses one access token (valid 8 hours). There is no refresh token yet.
- Login attempts are not rate limited yet.

## Status

- Phase 1 (setup): done
- Phase 2 (accounts, roles, batches): done
- Phase 3 (problems, code judge, run and submit): done
- Phase 4 (courses, lessons, progress, starter course): done
- Phase 5 (assignments, exams, marks, CSV export): done
- Phase 6 (AI hint helper, off during exams): next
- Phase 7 (reports and progress dashboards)
- Phase 8 (deployment and a pilot with one class)
