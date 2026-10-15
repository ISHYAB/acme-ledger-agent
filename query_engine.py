
import re
import calendar
from datetime import date

from analytics import (
    ORDERS,
    filter_orders,
    summarize,
    revenue_by,
    available_values,
)


# --------------------------------------------------
# Month name mapping
# --------------------------------------------------

MONTHS = {
    name.lower(): number
    for number, name in enumerate(calendar.month_name)
    if name
}

MONTHS.update({
    name.lower(): number
    for number, name in enumerate(calendar.month_abbr)
    if name
})


# --------------------------------------------------
# Entity extraction
# --------------------------------------------------

def find_value(question, field):
    """Find a known dataset value mentioned in a question."""
    q = question.casefold()
    values = sorted(available_values(field), key=len, reverse=True)

    for value in values:
        pattern = r"(?<!\w)" + re.escape(value.casefold()) + r"(?!\w)"
        if re.search(pattern, q):
            return value

    # Handle simple product plurals, e.g. 'air fryers'.
    if field == "product":
        for value in values:
            plural = value.casefold() + "s"
            pattern = r"(?<!\w)" + re.escape(plural) + r"(?!\w)"
            if re.search(pattern, q):
                return value

    return None


# --------------------------------------------------
# Date extraction
# --------------------------------------------------

def find_date_range(question):
    """
    Extract a month/year or year from a question.
    Returns (start_date, end_date, clarification).
    """
    q = question.casefold()

    year_match = re.search(r"\b(20\d{2})\b", q)
    year = int(year_match.group(1)) if year_match else None

    for month_name, month_number in sorted(
        MONTHS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if re.search(r"\b" + re.escape(month_name) + r"\b", q):
            if year is None:
                return (
                    None,
                    None,
                    f"Which year do you mean for "
                    f"{calendar.month_name[month_number]}?",
                )

            try:
                start = date(year, month_number, 1)
                last_day = calendar.monthrange(year, month_number)[1]
                end = date(year, month_number, last_day)
            except ValueError:
                return None, None, "Please provide a valid month and year."

            return start.isoformat(), end.isoformat(), None

    if year is not None:
        return f"{year}-01-01", f"{year}-12-31", None

    return None, None, None


# --------------------------------------------------
# Question intent detection
# --------------------------------------------------

def contains_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def answer_question(question):
    """Convert a business question into deterministic ledger analytics."""

    if not isinstance(question, str) or not question.strip():
        return "Please provide a non-empty question."

    q = question.strip().casefold()

    # Extract filters.
    region = find_value(q, "region")
    product = find_value(q, "product")
    customer = find_value(q, "customer")
    status = find_value(q, "status")

    start_date, end_date, clarification = find_date_range(q)

    if clarification:
        return clarification

    # Filter using created_at dates in Asia/Kolkata, as implemented
    # in analytics.py.
    orders = filter_orders(
        region=region,
        product=product,
        customer=customer,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )

    # Detect grouping dimensions.
    group_field = None

    if contains_any(q, [
        "by region", "each region", "which region",
        "regions", "per region",
    ]):
        group_field = "region"

    elif contains_any(q, [
        "by product", "each product", "which product",
        "products", "per product",
    ]):
        group_field = "product"

    elif contains_any(q, [
        "by currency", "each currency", "currencies",
        "per currency",
    ]):
        group_field = "currency"

    elif contains_any(q, [
        "by customer", "each customer", "which customer",
        "customers", "per customer",
    ]):
        group_field = "customer"

    # Detect the requested metric.
    asks_revenue = contains_any(q, [
        "revenue", "sales", "turnover", "earned",
        "how much money", "total income",
    ])

    asks_units = contains_any(q, [
        "units sold", "number of units", "how many units",
        "total units", "quantity sold",
    ])

    asks_count = contains_any(q, [
        "how many", "count", "number of",
        "total orders", "orders placed",
    ])

    asks_top = contains_any(q, [
        "highest", "most", "top", "best", "maximum",
    ])

    asks_lowest = contains_any(q, [
        "lowest", "least", "bottom", "minimum",
    ])

    # --------------------------------------------------
    # Unit quantity questions
    # --------------------------------------------------

    if asks_units:
        paid_units = sum(
            int(order["qty"])
            for order in orders
            if order["status"] == "paid"
        )

        return f"Total units in matching paid orders: {paid_units}."

    # --------------------------------------------------
    # Grouped revenue questions
    # --------------------------------------------------

    
    # Grouped revenue questions
    if asks_revenue and group_field:
        totals = revenue_by(orders, group_field)

        if not totals:
            return "No paid orders matched those filters."

        if asks_top:
            name = max(totals, key=totals.get)
            return (
                f"{name} had the highest paid revenue: "
                f"${totals[name]:,.2f} USD."
            )

        if asks_lowest:
            name = min(totals, key=totals.get)
            return (
                f"{name} had the lowest paid revenue: "
                f"${totals[name]:,.2f} USD."
            )

        lines = [
            f"{name}: ${amount:,.2f} USD"
            for name, amount in totals.items()
        ]

        return (
            f"Paid revenue by {group_field}:\n"
            + "\n".join(lines)
        )


    # --------------------------------------------------
    # Revenue questions
    # --------------------------------------------------

    if asks_revenue:
        result = summarize(orders)

        return (
            f"Paid revenue for the matching orders was "
            f"${result['paid_revenue_usd']:,.2f} USD."
        )

    # --------------------------------------------------
    # Status-specific counts
    # --------------------------------------------------

    if asks_count:
        if "paid" in q:
            count = sum(
                order["status"] == "paid"
                for order in orders
            )
            return f"Number of matching paid orders: {count}."

        if "refunded" in q:
            count = sum(
                order["status"] == "refunded"
                for order in orders
            )
            return f"Number of matching refunded orders: {count}."

        if "void" in q:
            count = sum(
                order["status"] == "void"
                for order in orders
            )
            return f"Number of matching void orders: {count}."

        return f"Number of matching current orders: {len(orders)}."

    # --------------------------------------------------
    # Summary questions
    # --------------------------------------------------

    if contains_any(q, ["summary", "overview", "breakdown"]):
        return str(summarize(orders))

    return (
        "I couldn't confidently interpret that question. "
        "Try asking about paid revenue, order counts, units sold, "
        "or revenue grouped by region or product."
    )


# --------------------------------------------------
# Local tests
# --------------------------------------------------

if __name__ == "__main__":
    test_questions = [
        "What is the total paid revenue?",
        "Which region generated the highest revenue?",
        "Show revenue by product",
        "How many orders are from South?",
        "What is the revenue from Air Fryer?",
        "How much revenue was generated in March 2026?",
        "How many paid orders are there?",
        "How many refunded orders are there?",
        "How many void orders are there?",
        "How many units were sold in paid orders?",
        "What was the revenue in South in March 2026?",
        "Show revenue by region in 2026",
        "What was the lowest revenue by product in March 2026?",
        "How many orders were placed in 2025?",
        "What was the lowest revenue by product in March 2026?",
"Which product had the highest revenue in South?",
"How much paid revenue came from refunded orders?",
"How many units were sold in South?",
"Show revenue by region in March 2026",
    ]

    for question in test_questions:
        print(f"\nQ: {question}")
        print(f"A: {answer_question(question)}")
