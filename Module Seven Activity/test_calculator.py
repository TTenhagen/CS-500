import unittest

from calculator import add, subtract, multiply, divide, calculate, parse_number


class TestAddition(unittest.TestCase):
    def test_add_positive_numbers(self):
        self.assertEqual(add(5, 3), 8)

    def test_add_negative_numbers(self):
        self.assertEqual(add(-4, -6), -10)

    def test_add_decimals(self):
        # Floats are stored in binary, so 0.1 + 0.2 is not exactly 0.3.
        self.assertAlmostEqual(add(0.1, 0.2), 0.3)


class TestSubtraction(unittest.TestCase):
    def test_subtract_positive_numbers(self):
        self.assertEqual(subtract(10, 4), 6)

    def test_subtract_result_negative(self):
        self.assertEqual(subtract(3, 9), -6)


class TestMultiplication(unittest.TestCase):
    def test_multiply_positive_numbers(self):
        self.assertEqual(multiply(6, 7), 42)

    def test_multiply_by_zero(self):
        self.assertEqual(multiply(125, 0), 0)

    def test_multiply_negative_numbers(self):
        self.assertEqual(multiply(-3, -5), 15)


class TestDivision(unittest.TestCase):
    def test_divide_evenly(self):
        self.assertEqual(divide(20, 4), 5)

    def test_divide_with_decimal_result(self):
        self.assertEqual(divide(7, 2), 3.5)

    def test_divide_by_zero_raises(self):
        with self.assertRaises(ZeroDivisionError):
            divide(10, 0)

    def test_divide_zero_by_number(self):
        self.assertEqual(divide(0, 5), 0)


class TestCalculateAndInput(unittest.TestCase):
    def test_calculate_routes_to_correct_operation(self):
        self.assertEqual(calculate("1", 2, 3), 5)
        self.assertEqual(calculate("4", 9, 3), 3)

    def test_calculate_invalid_choice_raises(self):
        with self.assertRaises(ValueError):
            calculate("9", 1, 1)

    def test_parse_number_valid_input(self):
        self.assertEqual(parse_number(" 42 "), 42.0)

    def test_parse_number_invalid_input_raises(self):
        with self.assertRaises(ValueError):
            parse_number("abc")

    def test_parse_number_rejects_infinity_and_nan(self):
        for text in ("inf", "-inf", "nan"):
            with self.assertRaises(ValueError):
                parse_number(text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
