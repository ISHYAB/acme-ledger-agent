
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).resolve().parent / "data"
BUSINESS_TZ = ZoneInfo("Asia/Kolkata")

with open(DATA_DIR / "current_orders.json", encoding="utf-8") as f:
    ORDERS = json.load(f)

with open(DATA_DIR / "rates.json", encoding="utf-8") as f:
    RATES_DATA = json.load(f)

USD_RATES = RATES_DATA["usd_per_unit"]


def parse_timestamp(value):
    """Parse a timestamp and convert it to the business timezone."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BUSINESS_TZ)

    return dt.astimezone(BUSINESS_TZ)


def amount_in_usd(order):
    """Convert an order's amount to USD using the supplied API rates."""
    currency = order["currency"]

    if currency not in USD_RATES:
        raise ValueError(f"Unknown currency: {currency}")

    return float(order["amount"]) * float(USD_RATES[currency])


def filter_orders(
    orders=None,
    region=None,
    product=None,
    customer=None,
    status=None,
    start_date=None,
    end_date=None,
):
    """Filter current order records by common business dimensions."""
    result = list(ORDERS if orders is None else orders)

    if region:
        result = [
            o for o in result
            if o["region"].casefold() == region.casefold()
        ]

    if product:
        result = [
            o for o in result
            if o["product"].casefold() == product.casefold()
        ]

    if customer:
        result = [
            o for o in result
            if o["customer"].casefold() == customer.casefold()
        ]

    if status:
        result = [
            o for o in result
            if o["status"].casefold() == status.casefold()
        ]

    if start_date:
        start = datetime.fromisoformat(start_date).date()
        result = [
            o for o in result
            if parse_timestamp(o["created_at"]).date() >= start
        ]

    if end_date:
        end = datetime.fromisoformat(end_date).date()
        result = [
            o for o in result
            if parse_timestamp(o["created_at"]).date() <= end
        ]

    return result


def summarize(orders):
    """Calculate standard metrics for a set of current orders."""
    paid = [o for o in orders if o["status"] == "paid"]

    return {
        "order_count": len(orders),
        "paid_order_count": len(paid),
        "refunded_order_count": sum(
            o["status"] == "refunded" for o in orders
        ),
        "void_order_count": sum(
            o["status"] == "void" for o in orders
        ),
        "paid_revenue_usd": round(
            sum(amount_in_usd(o) for o in paid), 2
        ),
        "paid_quantity": sum(int(o["qty"]) for o in paid),
    }


def revenue_by(orders, field):
    """Group paid revenue by a field such as region, product, or currency."""
    if field not in {"region", "product", "customer", "currency"}:
        raise ValueError(f"Unsupported grouping field: {field}")

    totals = defaultdict(float)

    for order in orders:
        if order["status"] != "paid":
            continue

        totals[order[field]] += amount_in_usd(order)

    return {
        key: round(value, 2)
        for key, value in sorted(
            totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    }


def available_values(field):
    """Return distinct values available for a supported field."""
    if field not in {
        "region", "product", "customer", "currency", "status"
    }:
        raise ValueError(f"Unsupported field: {field}")

    return sorted({str(o[field]) for o in ORDERS})


if __name__ == "__main__":
    print("========== DATASET CHECK ==========")
    print("Current unique orders:", len(ORDERS))
    print("Overall summary:")
    print(json.dumps(summarize(ORDERS), indent=2))

    print("\nAvailable regions:")
    print(json.dumps(available_values("region"), indent=2))

    print("\nAvailable products:")
    print(json.dumps(available_values("product"), indent=2))

    print("\nRevenue by region (USD):")
    print(json.dumps(revenue_by(ORDERS, "region"), indent=2))
