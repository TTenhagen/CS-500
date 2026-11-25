"""Unit tests for budget_app.py.

Run with:  python -m unittest -v test_budget_app
"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from budget_app import (
    MAX_AMOUNT,
    BudgetCategory,
    BudgetManager,
    Expense,
    clean_category,
    clean_description,
    parse_amount,
    parse_date,
    parse_month,
)


class TestParseAmount(unittest.TestCase):
    """Amount validation, including overflow and injection-style input."""

    def test_accepts_plain_and_formatted_numbers(self):
        self.assertEqual(parse_amount("1500"), 1500.0)
        self.assertEqual(parse_amount(" $1,500.25 "), 1500.25)

    def test_rejects_negative_numbers(self):
        with self.assertRaises(ValueError):
            parse_amount("-50")

    def test_rejects_letters_and_empty_input(self):
        for text in ("abc", "", "12abc"):
            with self.assertRaises(ValueError):
                parse_amount(text)

    def test_rejects_overflow_style_input(self):
        for text in ("inf", "nan", "1e308", "9" * 400):
            with self.assertRaises(ValueError):
                parse_amount(text)

    def test_rejects_amount_over_maximum(self):
        with self.assertRaises(ValueError):
            parse_amount("9999999999")
        self.assertEqual(parse_amount("1000000000"), MAX_AMOUNT)

    def test_zero_allowed_only_when_requested(self):
        self.assertEqual(parse_amount("0"), 0.0)
        with self.assertRaises(ValueError):
            parse_amount("0", allow_zero=False)


class TestParseDate(unittest.TestCase):
    """Date validation."""

    def test_accepts_valid_date(self):
        self.assertEqual(parse_date("2026-11-05"), date(2026, 11, 5))

    def test_rejects_wrong_format(self):
        for text in ("11/05/2026", "2026-13-01", "yesterday", ""):
            with self.assertRaises(ValueError):
                parse_date(text)

    def test_rejects_impossible_date(self):
        with self.assertRaises(ValueError):
            parse_date("2026-02-30")

    def test_rejects_future_date(self):
        tomorrow = date.today() + timedelta(days=1)
        with self.assertRaises(ValueError):
            parse_date(tomorrow.strftime("%Y-%m-%d"))

    def test_month_filter(self):
        self.assertEqual(parse_month("2026-11"), "2026-11")
        self.assertIsNone(parse_month("   "))
        with self.assertRaises(ValueError):
            parse_month("November")


class TestTextValidation(unittest.TestCase):
    """Category and description validation."""

    def test_category_is_normalized(self):
        self.assertEqual(clean_category("  gROCERIES "), "Groceries")

    def test_category_rejects_bad_characters_and_length(self):
        for text in ("", "<script>", "../etc/passwd", "x" * 31):
            with self.assertRaises(ValueError):
                clean_category(text)

    def test_description_rejects_control_characters(self):
        with self.assertRaises(ValueError):
            clean_description("coffee\x1b[2J")

    def test_description_rejects_empty_and_too_long(self):
        for text in ("   ", "x" * 61):
            with self.assertRaises(ValueError):
                clean_description(text)


class TestBudgetCategory(unittest.TestCase):
    """Category totals."""

    def test_total_and_month_filter(self):
        category = BudgetCategory("Groceries")
        category.add_expense(Expense("Milk", 4.10, date(2026, 10, 30)))
        category.add_expense(Expense("Bread", 3.20, date(2026, 11, 2)))
        self.assertEqual(category.total_expenses(), 7.30)
        self.assertEqual(category.total_expenses("2026-11"), 3.20)

    def test_empty_category_total_is_zero(self):
        self.assertEqual(BudgetCategory("Rent").total_expenses(), 0.0)


class TestBudgetManager(unittest.TestCase):
    """Manager behavior, each test using its own temporary data file."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.data_file = Path(self.folder.name) / "budget_data.json"
        self.manager = BudgetManager(self.data_file)

    def tearDown(self):
        self.folder.cleanup()

    def test_expenses_are_grouped_by_category(self):
        self.manager.add_expense("rent", 1200, "November rent",
                                 date(2026, 11, 1))
        self.manager.add_expense("Groceries", 85.50, "Weekly shop",
                                 date(2026, 11, 3))
        self.manager.add_expense("groceries", 14.50, "Snacks",
                                 date(2026, 11, 4))
        self.assertEqual(self.manager.total_expenses(), 1300.00)
        self.assertEqual(
            self.manager.totals_by_category(),
            {"Groceries": 100.00, "Rent": 1200.00},
        )

    def test_manager_rejects_invalid_amounts_directly(self):
        for amount in (-1, float("inf"), float("nan"), "100", True):
            with self.assertRaises(ValueError):
                self.manager.set_income(amount)
        with self.assertRaises(ValueError):
            self.manager.add_expense("Rent", 0, "Free", date(2026, 11, 1))

    def test_progress_on_track(self):
        self.manager.set_income(3000)
        self.manager.set_savings_goal(500)
        self.manager.add_expense("Rent", 1200, "Rent", date(2026, 11, 1))
        self.assertEqual(
            self.manager.progress_toward_goal(), (1800.00, 0.0, True)
        )

    def test_progress_not_on_track(self):
        self.manager.set_income(1500)
        self.manager.set_savings_goal(500)
        self.manager.add_expense("Rent", 1200, "Rent", date(2026, 11, 1))
        self.assertEqual(
            self.manager.progress_toward_goal(), (300.00, 200.00, False)
        )

    def test_save_and_reload(self):
        self.manager.set_income(3000)
        self.manager.set_savings_goal(500)
        self.manager.add_expense("Rent", 1200, "Rent", date(2026, 11, 1))
        self.assertTrue(self.manager.save_data())

        reloaded = BudgetManager(self.data_file)
        self.assertEqual(reloaded.income, 3000.00)
        self.assertEqual(reloaded.savings_goal, 500.00)
        self.assertEqual(reloaded.total_expenses(), 1200.00)

    def test_corrupted_file_starts_empty(self):
        self.data_file.write_text("{not valid json", encoding="utf-8")
        manager = BudgetManager(self.data_file)
        self.assertEqual(manager.income, 0.0)
        self.assertEqual(manager.total_expenses(), 0.0)

    def test_tampered_records_are_skipped(self):
        tampered = {
            "income": -5000,
            "savings_goal": 500,
            "categories": {
                "Rent": [
                    {"description": "Rent", "amount": 1200,
                     "date": "2026-11-01"},
                    {"description": "Bad", "amount": "1e400",
                     "date": "2026-11-01"},
                    {"description": "No date", "amount": 10},
                ]
            },
        }
        self.data_file.write_text(json.dumps(tampered), encoding="utf-8")
        manager = BudgetManager(self.data_file)
        self.assertEqual(manager.income, 0.0)
        self.assertEqual(manager.savings_goal, 500.00)
        self.assertEqual(manager.total_expenses(), 1200.00)

    def test_no_chart_without_expenses(self):
        self.assertIsNone(self.manager.visualize_expenses(show=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
