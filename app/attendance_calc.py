"""Pure attendance math: percentage, and how many classes to attend/can
skip to reach or maintain the configured threshold (default 75%)."""

import math
from dataclasses import dataclass

# How many percentage points above the threshold still count as "Warning"
# rather than fully "Safe" (e.g. 75-80% is a caution zone, not yet safe).
WARNING_BAND = 5.0


@dataclass
class AttendanceSummary:
    total_classes: int
    attended_classes: int
    percentage: float
    threshold: float
    meets_threshold: bool
    classes_to_attend_for_threshold: int  # needed if below threshold
    classes_can_skip: int  # safe skips if at/above threshold


def compute_summary(total_classes: int, attended_classes: int, threshold: float = 75.0) -> AttendanceSummary:
    if total_classes <= 0:
        percentage = 0.0
    else:
        percentage = (attended_classes / total_classes) * 100

    t = threshold / 100.0
    meets = percentage >= threshold

    classes_to_attend = 0
    classes_can_skip = 0

    if not meets:
        # Smallest integer x (future classes, all attended) such that
        # (attended + x) / (total + x) >= t
        # => x >= (t*total - attended) / (1 - t)
        if t < 1:
            raw = (t * total_classes - attended_classes) / (1 - t)
            classes_to_attend = max(0, math.ceil(raw - 1e-9))
        else:
            classes_to_attend = max(0, total_classes - attended_classes)
    else:
        # Largest integer y (future classes, all skipped) such that
        # attended / (total + y) >= t
        if t > 0:
            raw = (attended_classes / t) - total_classes
            classes_can_skip = max(0, math.floor(raw + 1e-9))

    return AttendanceSummary(
        total_classes=total_classes,
        attended_classes=attended_classes,
        percentage=round(percentage, 2),
        threshold=threshold,
        meets_threshold=meets,
        classes_to_attend_for_threshold=classes_to_attend,
        classes_can_skip=classes_can_skip,
    )


def classify_status(percentage: float, threshold: float = 75.0) -> str:
    """Returns 'critical' (below threshold), 'warning' (threshold to
    threshold + WARNING_BAND), or 'safe' (comfortably above threshold)."""
    if percentage < threshold:
        return "critical"
    if percentage < threshold + WARNING_BAND:
        return "warning"
    return "safe"


def is_exam_eligible(percentage: float, eligibility_threshold: float = 33.0) -> bool:
    """Minimum attendance required just to be allowed to sit an exam - a
    lower bar than the day-to-day attendance threshold (default 75%)."""
    return percentage >= eligibility_threshold


def summary_message(summary: AttendanceSummary) -> str:
    if summary.total_classes == 0:
        return "No classes have been held for your course yet."

    if summary.meets_threshold:
        if summary.classes_can_skip > 0:
            return (
                f"You are meeting the {summary.threshold:.0f}% attendance requirement. "
                f"You can skip up to {summary.classes_can_skip} more class"
                f"{'es' if summary.classes_can_skip != 1 else ''} and still stay at or above "
                f"{summary.threshold:.0f}%."
            )
        return (
            f"You are right at the {summary.threshold:.0f}% attendance requirement. "
            "Attend your next classes to stay above it."
        )

    return (
        f"Your attendance ({summary.percentage}%) is below the required "
        f"{summary.threshold:.0f}%. Attend the next "
        f"{summary.classes_to_attend_for_threshold} class"
        f"{'es' if summary.classes_to_attend_for_threshold != 1 else ''} in a row, "
        f"without missing any, to get back to {summary.threshold:.0f}%."
    )
