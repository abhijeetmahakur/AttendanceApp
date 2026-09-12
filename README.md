# Attendance Management System

A Flask web app for recording daily attendance with admin-defined time windows,
registration-number-based student login, automatic email summaries, and 75%
attendance-threshold suggestions.

## Features

- **Admin panel**
  - Register/remove students (registration number, name, email, course).
  - Create class sessions, each with a date and an attendance window
    (open/close time) that the admin controls.
  - Dashboard of students currently below the attendance threshold.
  - Per-session report of who attended / was absent.
  - Full attendance report, filterable by course.
- **Student panel**
  - Login with registration number + password.
  - Mark attendance, but only while the admin's time window for that
    session is open; duplicate marking is blocked.
  - See total classes held, classes attended, and attendance percentage.
  - On marking attendance, automatically receives an email with their
    stats and, if below 75%, how many classes in a row they need to
    attend to get back above the threshold (or, if above, how many they
    can safely skip and stay above it).
- SQLite database, created automatically on first run.

## Setup

```
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:
- Set `SECRET_KEY` to a random string.
- Set `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` to enable
  real email sending (e.g. a Gmail address + an
  [App Password](https://myaccount.google.com/apppasswords)). If left
  blank, emails are simply logged instead of sent, so the app still runs.
- Adjust `ATTENDANCE_THRESHOLD` if 75% isn't the desired cutoff.

## Run

```
python run.py
```

Visit http://127.0.0.1:5000. On first run, a default admin account is
created and printed to the console (`admin` / `admin123` unless overridden
in `.env`) — log in and start adding students and sessions.

## Typical workflow

1. Admin logs in, registers students under **Students** (each gets a
   registration number and a temporary password to share with them).
2. Admin creates a **Class Session** for today with a subject, course,
   date, and the open/close time for marking attendance.
3. Students log in with their registration number during that window and
   click **Mark Attendance**. They get an immediate on-screen summary and
   an emailed one.
4. Admin reviews **Reports** for full-class attendance and to see who's
   falling below the threshold.

## Project layout

```
run.py                 entry point
config.py              configuration from environment / .env
app/
  __init__.py           Flask app factory
  db.py                 SQLite connection + schema init + default admin seed
  schema.sql             table definitions
  models.py             all database queries
  attendance_calc.py    percentage + threshold suggestion math
  mailer.py             attendance summary emails (Flask-Mail)
  auth.py               session-based login helpers/decorators
  auth_routes.py         /login, /logout
  admin_routes.py        /admin/* (students, sessions, reports)
  student_routes.py      /student/* (dashboard, mark attendance)
  templates/, static/    HTML + CSS
```
