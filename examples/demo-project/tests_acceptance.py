import sys
from pathlib import Path
import unittest
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from pricing import line_total
from order_summary import order_total

class PricingAcceptance(unittest.TestCase):
    def test_existing_behavior(self):
        self.assertEqual(line_total("10.00", 2), Decimal("20.00"))
    def test_discount(self):
        self.assertEqual(line_total("10.00", 2, 15), Decimal("17.00"))
        self.assertEqual(line_total("10.00", 2, 100), Decimal("0.00"))
    def test_half_up(self):
        self.assertEqual(line_total("0.05", 1, 10), Decimal("0.05"))
    def test_money_precision(self):
        self.assertEqual(str(line_total("1", 1)), "1.00")
    def test_invalid_quantity(self):
        for value in (-1, 1.5, True):
            with self.subTest(quantity=value), self.assertRaises(ValueError):
                line_total("1", value)
    def test_invalid_discount(self):
        for value in (-1, 101):
            with self.subTest(discount=value), self.assertRaises(ValueError):
                line_total("1", 1, value)
    def test_order_discount_passthrough(self):
        self.assertEqual(order_total([{"unit_price":"10", "quantity":2, "discount_percent":15},
                                      {"unit_price":"0.05", "quantity":1, "discount_percent":10}]), Decimal("17.05"))
    def test_empty_order(self):
        self.assertEqual(str(order_total([])), "0.00")

if __name__ == "__main__":
    unittest.main(verbosity=2)
