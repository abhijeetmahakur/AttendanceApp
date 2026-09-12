# Attendance Management System

A Flask web app for a college department: attendance (manual and QR-code),
leave requests, exam eligibility, teacher/admin accounts scoped by subject,
WhatsApp + email notices, holidays, timetables, and student self-signup —
built around a single SQLite database.

## Features

- **Accounts & roles**
  - A super admin manages teacher accounts; each teacher can be scoped to
    the subjects/sections they actually teach.
  - Students are pre-loaded onto the roster (individually or via CSV
    import) and self-service sign up with their registration number,
    subject to teacher approval — this is what keeps the roster free of
    spam accounts.
- **Attendance**
  - Manual attendance windows (admin opens a time window; students mark
    themselves present while it's open) and QR-code attendance (a
    one-time, time-limited code a teacher displays in class).
  - Duplicate marking is blocked at both the application and database
    level.
  - Live 75%-threshold suggestions ("attend the next N classes" / "you can
    skip N more"), a separate 33% exam-eligibility threshold, and
    subject-wise breakdowns.
  - Excel and PDF export of attendance data, per student or by class/section.
  - An admin statistics dashboard with charts (overall, by subject, by
    student, monthly trend) and filters.
- **Leave management**
  - Students apply for leave (with an optional attachment); admins
    approve/reject with a reason. Status changes notify the student.
- **Notices & communication**
  - Holiday calendar and class timetable, visible to both admin and
    students.
  - Holiday/substitution/general notices sent by email and WhatsApp
    together.
  - Absentee alerts: a teacher can message a saved WhatsApp group (a
    class rep, a parents' group) the roll numbers of everyone absent
    from a session.
  - Email and WhatsApp both degrade gracefully (logging instead of
    sending) when SMTP/Twilio credentials aren't configured, so the app
    runs end to end without either.
- SQLite database, schema and migrations applied automatically on startup.

## Setup

```
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:
- Set `SECRET_KEY` to a random string.
- Set `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` to enable
  real email (e.g. a Gmail address + an
  [App Password](https://myaccount.google.com/apppasswords)). Leave blank
  to have emails logged instead of sent.
- Set `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_WHATSAPP_FROM`
  to enable real WhatsApp messages. Leave blank to have them logged
  instead of sent.
- Adjust `ATTENDANCE_THRESHOLD` / `EXAM_ELIGIBILITY_THRESHOLD` if 75% / 33%
  aren't the desired cutoffs.

## Run

```
python run.py
```

Visit http://127.0.0.1:5000. On first run, a default super admin account is
created and printed to the console (`admin` / `admin123` unless overridden
in `.env`) — log in, create teacher accounts and/or students, and go.

## Deployment

This app stores data in a local SQLite file and (optionally) local disk for
leave attachments. That only survives restarts/redeploys on a host with a
**real, persistent disk** — most "serverless" platforms (Vercel included)
run your code in a fresh, throwaway filesystem on every request, which
silently loses data written to a local file. Pick a host that gives you an
actual persistent volume: **Render**, Railway, and Fly.io all support this
for Python apps.

**Render** (a `render.yaml` Blueprint is included in this repo):
1. Push this repo to GitHub.
2. On Render: **New** → **Blueprint**, point it at the repo. It reads
   `render.yaml` and creates a web service with a 1GB persistent disk
   mounted at `/data`.
3. Render will prompt for the secret environment variables (mail,
   Twilio, S3, admin credentials) — anything not filled in just falls
   back to the same "log instead of send" / local-disk behavior as
   local development.
4. **Free plan has no persistent disk.** The Blueprint requests the paid
   `starter` plan specifically because that's what actually fixes the
   data-loss problem — a free-plan deploy would have the exact same
   "data vanishes on redeploy" issue as running this on Vercel.

The app runs under `waitress` (a pure-Python, cross-platform production
WSGI server — see `requirements.txt`/`render.yaml`) rather than Flask's
built-in development server, which isn't meant for production traffic.

**Leave-request attachments** can optionally be moved off local disk
entirely onto S3-compatible cloud storage (Cloudflare R2, AWS S3,
Backblaze B2, ...) by setting the `S3_*` variables in `.env` — see
`app/storage.py`. This is worth doing even on a host with a persistent
disk, since it keeps large uploaded files out of your database's disk
budget and gives you a proper backup/versioning story independent of
the app server.

## Project layout

```
run.py                    entry point
config.py                 configuration from environment / .env
render.yaml               Render Blueprint (persistent disk + env vars)
app/
  __init__.py              Flask app factory, context processors
  db.py                    SQLite connection + schema init + migrations
  schema.sql               table definitions
  models.py                all database queries
  attendance_calc.py       attendance %, threshold suggestions, eligibility
  leave_calc.py            leave-request date/type helpers
  qr_calc.py               QR code generation
  stats_calc.py            attendance matrix -> chart-ready aggregates
  reports_export.py        Excel/PDF report generation
  roster_import.py         CSV roster import + matching logic
  mailer.py                email sending (Flask-Mail)
  whatsapp.py              WhatsApp sending (Twilio API)
  storage.py               leave-attachment storage (S3-compatible or local disk)
  validators.py            password / registration-number / roll-number rules
  auth.py                  session-based login helpers/decorators
  auth_routes.py           /login, /logout, /signup
  admin_routes.py          /admin/* (students, sessions, QR, leaves,
                           stats, teachers, WhatsApp groups, holidays,
                           timetable, notices, exports)
  student_routes.py        /student/* (dashboard, attendance, QR scan,
                           leave, notifications, holidays, timetable)
  templates/, static/      HTML + CSS + JS
```
