"""Pure aggregation of an attendance matrix (one row per student/session-held
pair, see models.attendance_matrix) into the shapes the admin statistics
page and its charts need: per-student, per-subject, and per-month rollups."""

from collections import defaultdict
from dataclasses import dataclass, field

from .attendance_calc import classify_status


@dataclass
class Bucket:
    total: int = 0
    attended: int = 0
    label: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def missed(self):
        return self.total - self.attended

    @property
    def percentage(self):
        if self.total == 0:
            return 0.0
        return round((self.attended / self.total) * 100, 2)


def build_stats(matrix_rows, threshold=75.0):
    """Returns a dict with overall totals plus by_student / by_subject /
    by_month buckets (each a list of dicts), computed from the raw matrix."""
    by_student = defaultdict(Bucket)
    by_subject = defaultdict(Bucket)
    by_month = defaultdict(Bucket)
    overall = Bucket(label="Overall")

    for row in matrix_rows:
        overall.total += 1
        overall.attended += row["attended"]

        sb = by_student[row["student_id"]]
        sb.total += 1
        sb.attended += row["attended"]
        sb.label = row["name"]
        sb.extra = {
            "reg_no": row["reg_no"], "roll_no": row["roll_no"],
            "registration_no": row["registration_no"], "course": row["course"],
        }

        subj = by_subject[row["subject"]]
        subj.total += 1
        subj.attended += row["attended"]
        subj.label = row["subject"]

        month = row["session_date"][:7] if row["session_date"] else "unknown"
        mb = by_month[month]
        mb.total += 1
        mb.attended += row["attended"]
        mb.label = month

    def to_rows(buckets, sort_key):
        rows = []
        for bucket in buckets.values():
            pct = bucket.percentage
            rows.append({
                "label": bucket.label,
                "total": bucket.total,
                "attended": bucket.attended,
                "missed": bucket.missed,
                "percentage": pct,
                "status": classify_status(pct, threshold) if bucket.total > 0 else "safe",
                **bucket.extra,
            })
        rows.sort(key=sort_key)
        return rows

    student_rows = to_rows(by_student, lambda r: r["label"].lower())
    subject_rows = to_rows(by_subject, lambda r: r["label"].lower())
    month_rows = to_rows(by_month, lambda r: r["label"])

    above = sum(1 for r in student_rows if r["percentage"] >= threshold)
    below = sum(1 for r in student_rows if r["percentage"] < threshold)
    at_risk = sum(1 for r in student_rows if r["total"] > 0 and r["percentage"] < max(threshold - 10, 0))

    return {
        "overall_total": overall.total,
        "overall_attended": overall.attended,
        "overall_missed": overall.missed,
        "overall_percentage": overall.percentage,
        "by_student": student_rows,
        "by_subject": subject_rows,
        "by_month": month_rows,
        "students_above": above,
        "students_below": below,
        "students_at_risk": at_risk,
    }


def student_subject_breakdown(subject_wise_rows, threshold=75.0):
    """Turns models.subject_wise_attendance_for_student() rows into display
    rows (with percentage + Safe/Warning/Critical status) plus an overall
    summary dict. Used by both the student's "My Attendance" page and the
    per-student PDF report, admin- or self-generated."""
    rows = []
    total = 0
    attended = 0
    for r in subject_wise_rows:
        row_total = r["total"]
        row_attended = r["attended"]
        total += row_total
        attended += row_attended
        pct = round((row_attended / row_total) * 100, 2) if row_total else 0.0
        rows.append({
            "subject": r["subject"],
            "total": row_total,
            "attended": row_attended,
            "missed": row_total - row_attended,
            "percentage": pct,
            "status": classify_status(pct, threshold) if row_total else "safe",
        })

    overall_pct = round((attended / total) * 100, 2) if total else 0.0
    overall = {
        "total": total,
        "attended": attended,
        "missed": total - attended,
        "percentage": overall_pct,
        "status": classify_status(overall_pct, threshold) if total else "safe",
    }
    return rows, overall
