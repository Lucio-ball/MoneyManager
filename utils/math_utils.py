def monthly_cost(amount: float, cycle: str) -> float:
    if cycle == "yearly":
        return round(amount / 12, 2)
    if cycle == "quarterly":
        return round(amount / 3, 2)
    if cycle == "weekly":
        return round(amount * 52 / 12, 2)
    return round(amount, 2)
