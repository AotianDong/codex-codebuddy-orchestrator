from decimal import Decimal
from pricing import line_total

def order_total(lines):
    return sum((line_total(x["unit_price"], x["quantity"]) for x in lines), Decimal("0.00"))
