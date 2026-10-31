from datetime import timedelta

from jalboot.api import metrics
from jalboot.db.models import Ticket
from tests.conftest import ANCHOR


def test_top_issues_come_largest_first_with_ties_in_a_fixed_order(db):
    counts = {"account": 1, "late_delivery": 2, "wrong_item": 5, "other": 1, "promo_issue": 3}
    start = ANCHOR + timedelta(days=1)
    for category, count in counts.items():
        for number in range(count):
            db.add(Ticket(
                id=f"T-{category}-{number}", category=category, subject="s", created_at=start - timedelta(hours=1),
            ))
    db.commit()
    issues = metrics.top_issues(db, start, 1, "en")
    assert [issue["id"] for issue in issues if issue["id"] in counts] == [
        "wrong_item", "promo_issue", "late_delivery", "account", "other",
    ]
