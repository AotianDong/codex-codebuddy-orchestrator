from decimal import Decimal

def line_total(unit_price, quantity, discount_percent=0):
    return Decimal(str(unit_price)) * quantity
