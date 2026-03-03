import calendar
from datetime import date, datetime, timedelta


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def month_sequence(month: str, count: int = 3) -> list[str]:
    year, mon = map(int, month.split("-"))
    result: list[str] = []
    current_year = year
    current_mon = mon
    for _ in range(count):
        result.append(f"{current_year:04d}-{current_mon:02d}")
        current_mon -= 1
        if current_mon == 0:
            current_mon = 12
            current_year -= 1
    result.reverse()
    return result


def add_months(base_date: date, months: int) -> date:
    month_index = (base_date.month - 1) + months
    target_year = base_date.year + month_index // 12
    target_month = month_index % 12 + 1
    target_day = min(base_date.day, calendar.monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day)


def next_billing_date(current_date: date, cycle: str) -> date:
    if cycle == "weekly":
        return current_date + timedelta(days=7)
    if cycle == "monthly":
        return add_months(current_date, 1)
    if cycle == "quarterly":
        return add_months(current_date, 3)
    if cycle == "yearly":
        return add_months(current_date, 12)
    return add_months(current_date, 1)
