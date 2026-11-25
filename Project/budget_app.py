
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, TypeVar

'''The charts are the only feature that needs matplotlib, so the rest of
the program still works when the package is not installed.'''
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

# Constants
DATA_FILE = Path(__file__).with_name("budget_data.json")
CHART_FILE = Path(__file__).with_name("expenses_chart.png")
DATE_FORMAT = "%Y-%m-%d"
MONTH_FORMAT = "%Y-%m"
MAX_AMOUNT = 1_000_000_000.00
MAX_INPUT_LENGTH = 100
MAX_CATEGORY_LENGTH = 30
MAX_DESCRIPTION_LENGTH = 60
EARLIEST_DATE = date(2000, 1, 1)

T = TypeVar("T")

# Whitelists: input must match these patterns exactly to be accepted.
AMOUNT_PATTERN = re.compile(r"\d{1,10}(\.\d{1,2})?")
CATEGORY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 &'/-]*")


# Validation Functions (no input or output, so they can be unit tested)

def parse_amount(text: str, allow_zero: bool = True) -> float:
    """Convert user text into a dollar amount.

    Args:
        text: Raw text such as "1500", "$1,500.25", or " 42.5 ".
        allow_zero: Whether an amount of 0 is acceptable.

    Returns:
        The amount as a float rounded to two decimal places.

    Raises:
        ValueError: If the text is too long, is not a plain positive
            number with at most two decimals, or is out of range.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError("Input is too long.")
    cleaned = text.strip().lstrip("$").replace(",", "")
    # The whitelist rejects negatives, letters, "inf", "nan", and
    # scientific notation such as "1e308" before float() ever runs.
    if not AMOUNT_PATTERN.fullmatch(cleaned):
        raise ValueError("Enter a positive number, up to two decimals.")
    amount = round(float(cleaned), 2)
    if amount > MAX_AMOUNT:
        raise ValueError(f"Amount cannot be more than ${MAX_AMOUNT:,.2f}.")
    if amount == 0 and not allow_zero:
        raise ValueError("Amount must be greater than zero.")
    return amount


def parse_date(text: str) -> date:
    """Convert user text in YYYY-MM-DD format into a date.

    Raises:
        ValueError: If the text is not a real calendar date in the
            expected format, is in the future, or is before 2000.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError("Input is too long.")
    try:
        parsed = datetime.strptime(text.strip(), DATE_FORMAT).date()
    except ValueError:
        raise ValueError(
            "Use a real date in the format YYYY-MM-DD."
        ) from None
    if parsed > date.today():
        raise ValueError("The date cannot be in the future.")
    if parsed < EARLIEST_DATE:
        raise ValueError(f"The date cannot be before {EARLIEST_DATE}.")
    return parsed


def parse_month(text: str) -> Optional[str]:
    """Convert user text into a YYYY-MM month filter.

    Returns:
        The month as "YYYY-MM", or None when the text is blank, which
        means "all months."

    Raises:
        ValueError: If the text is not blank and not a real month.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError("Input is too long.")
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned, MONTH_FORMAT).strftime(MONTH_FORMAT)
    except ValueError:
        raise ValueError(
            "Enter a month in the format YYYY-MM, or press Enter for all."
        ) from None


def clean_category(text: str) -> str:
    """Validate a category name and return it in a consistent format.

    "groceries", "Groceries", and " GROCERIES " all become "Groceries"
    so they are tracked as one category.

    Raises:
        ValueError: If the name is empty, too long, or contains
            characters outside the allowed set.
    """
    cleaned = " ".join(text.split())
    if not cleaned:
        raise ValueError("Category cannot be empty.")
    if len(cleaned) > MAX_CATEGORY_LENGTH:
        raise ValueError(
            f"Category must be {MAX_CATEGORY_LENGTH} characters or fewer."
        )
    if not CATEGORY_PATTERN.fullmatch(cleaned):
        raise ValueError("Use only letters, numbers, spaces, & ' / -.")
    return cleaned.title()


def clean_description(text: str) -> str:
    """Validate an expense description and return it trimmed.

    Raises:
        ValueError: If the description is empty, too long, or contains
            non-printable characters such as terminal control codes.
    """
    cleaned = " ".join(text.split())
    if not cleaned:
        raise ValueError("Description cannot be empty.")
    if len(cleaned) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters "
            "or fewer."
        )
    if not cleaned.isprintable():
        raise ValueError(
            "Description contains characters that are not allowed."
        )
    return cleaned


# Expense Class
@dataclass(frozen=True)
class Expense:
    """One expense entry. Frozen so a saved entry cannot be reassigned."""

    description: str
    amount: float
    date: date

    def to_dict(self) -> dict:
        """Return the expense in a form that can be written as JSON."""
        return {
            "description": self.description,
            "amount": self.amount,
            "date": self.date.strftime(DATE_FORMAT),
        }

    @classmethod
    def from_dict(cls, record: dict) -> "Expense":
        """Build an expense from saved data, re-validating every field.

        Raises:
            ValueError: If any field is missing or fails validation.
        """
        try:
            return cls(
                description=clean_description(str(record["description"])),
                amount=parse_amount(str(record["amount"]), allow_zero=False),
                date=parse_date(str(record["date"])),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"Invalid expense record: {error}") from None


# Budget Category Class
class BudgetCategory:
    """A named group of expenses, such as "Groceries" or "Rent"."""

    def __init__(self, name: str) -> None:
        """Create an empty category with the given name."""
        self.name = name
        self.expenses: List[Expense] = []

    def add_expense(self, expense: Expense) -> None:
        """Add one expense to this category."""
        self.expenses.append(expense)

    def total_expenses(self, month: Optional[str] = None) -> float:
        """Return the category total, optionally for one YYYY-MM month."""
        amounts = [
            expense.amount
            for expense in self.expenses
            if month is None or expense.date.strftime(MONTH_FORMAT) == month
        ]
        # fsum avoids the small rounding errors that sum() can build up.
        return round(math.fsum(amounts), 2)


# Budget Manager Class
class BudgetManager:
    """Holds income, the savings goal, and every budget category."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        """Start with an empty budget, then load any saved data."""
        self.income = 0.0
        self.savings_goal = 0.0
        self.categories: Dict[str, BudgetCategory] = {}
        self.data_file = Path(data_file)
        self.load_data()

    def set_income(self, amount: float) -> None:
        """Set the income after confirming it is a valid amount."""
        self.income = self._checked_amount(amount)

    def set_savings_goal(self, amount: float) -> None:
        """Set the savings goal after confirming it is a valid amount."""
        self.savings_goal = self._checked_amount(amount)

    def add_expense(
        self,
        category: str,
        amount: float,
        description: str,
        expense_date: date,
    ) -> Expense:
        """Create an expense and file it under its category.

        Returns:
            The expense that was added.

        Raises:
            ValueError: If the category, amount, or description is invalid.
        """
        name = clean_category(category)
        expense = Expense(
            description=clean_description(description),
            amount=self._checked_amount(amount, allow_zero=False),
            date=expense_date,
        )
        if name not in self.categories:
            self.categories[name] = BudgetCategory(name)
        self.categories[name].add_expense(expense)
        return expense

    def total_expenses(self, month: Optional[str] = None) -> float:
        """Return total spending, optionally for one YYYY-MM month."""
        return round(math.fsum(self.totals_by_category(month).values()), 2)

    def totals_by_category(
        self, month: Optional[str] = None
    ) -> Dict[str, float]:
        """Return each category's total, leaving out categories at zero."""
        totals = {
            name: category.total_expenses(month)
            for name, category in sorted(self.categories.items())
        }
        return {name: total for name, total in totals.items() if total > 0}

    def progress_toward_goal(self) -> Tuple[float, float, bool]:
        """Compare current savings with the savings goal.

        Returns:
            A tuple of (current savings, amount still needed, on track).
            Current savings is income minus total expenses and can be
            negative when spending is higher than income.
        """
        current_savings = round(self.income - self.total_expenses(), 2)
        still_needed = round(max(self.savings_goal - current_savings, 0.0), 2)
        on_track = current_savings >= self.savings_goal
        return current_savings, still_needed, on_track

    def save_data(self) -> bool:
        """Write all data to the JSON file.

        The data is written to a temporary file first and then swapped
        into place, so a crash mid-save cannot corrupt the existing file.

        Returns:
            True if the data was saved, False if the file could not be
            written.
        """
        data = {
            "income": self.income,
            "savings_goal": self.savings_goal,
            "categories": {
                name: [expense.to_dict() for expense in category.expenses]
                for name, category in self.categories.items()
            },
        }
        temp_file = self.data_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
            os.replace(temp_file, self.data_file)
        except OSError as error:
            print(f"Could not save data: {error.strerror}.")
            return False
        return True

    def load_data(self) -> None:
        """Load saved data, skipping anything that fails validation.

        A missing file is normal on the first run. A damaged file is
        reported and the program starts with an empty budget instead of
        crashing.
        """
        try:
            with open(self.data_file, encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            print(
                "Saved data could not be read. "
                "Starting with an empty budget."
            )
            return

        if not isinstance(data, dict):
            print("Saved data is not in the expected format. Starting empty.")
            return

        skipped = 0
        # The file is treated like user input: every value is re-validated.
        for key, setter in (
            ("income", self.set_income),
            ("savings_goal", self.set_savings_goal),
        ):
            try:
                setter(parse_amount(str(data.get(key, 0))))
            except ValueError:
                skipped += 1

        categories = data.get("categories", {})
        if not isinstance(categories, dict):
            categories = {}
            skipped += 1
        for name, records in categories.items():
            if not isinstance(records, list):
                skipped += 1
                continue
            for record in records:
                try:
                    expense = Expense.from_dict(record)
                    self.add_expense(
                        name, expense.amount, expense.description, expense.date
                    )
                except ValueError:
                    skipped += 1
        if skipped:
            print(f"Skipped {skipped} saved value(s) that were not valid.")

    def visualize_expenses(self, show: bool = True) -> Optional[Path]:
        """Draw a pie chart and bar graph of spending by category.

        Args:
            show: Whether to open the chart window after saving the image.

        Returns:
            The path of the saved chart image, or None if no chart was
            made because there are no expenses or matplotlib is missing.
        """
        totals = self.totals_by_category()
        if not totals:
            print("No expenses to visualize yet. Add an expense first.")
            return None
        if plt is None:
            print(
                "Charts need matplotlib. "
                "Install it with: pip install matplotlib"
            )
            return None

        names = list(totals.keys())
        amounts = list(totals.values())
        figure, (pie_axes, bar_axes) = plt.subplots(1, 2, figsize=(11, 5))
        figure.suptitle("Spending by Category")

        pie_axes.pie(amounts, labels=names, autopct="%1.1f%%", startangle=90)
        pie_axes.set_title("Share of Total Spending")

        bar_axes.bar(names, amounts, color="steelblue")
        bar_axes.set_title("Total Spent per Category")
        bar_axes.set_ylabel("Amount ($)")
        bar_axes.tick_params(axis="x", rotation=30)

        figure.tight_layout()
        try:
            figure.savefig(CHART_FILE)
            print(f"Chart saved to {CHART_FILE.name}.")
        except OSError as error:
            print(f"Could not save the chart image: {error.strerror}.")
        if show:
            plt.show()
        plt.close(figure)
        return CHART_FILE

    @staticmethod
    def _checked_amount(amount: float, allow_zero: bool = True) -> float:
        """Re-check an amount inside the class (a second validation layer).

        The leading underscore marks this as an internal helper. Python
        does not block outside code from calling it; the underscore is a
        naming convention, not enforced privacy.
        """
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("Amount must be a number.")
        if not math.isfinite(amount) or amount < 0 or amount > MAX_AMOUNT:
            raise ValueError("Amount is out of the allowed range.")
        if amount == 0 and not allow_zero:
            raise ValueError("Amount must be greater than zero.")
        return round(float(amount), 2)


# Input Validation Functions

def get_valid_input(prompt: str, parser: Callable[[str], T]) -> T:
    """Keep prompting until the parser accepts what the user typed.

    Args:
        prompt: The text shown to the user.
        parser: A function that returns the converted value or raises
            ValueError with a message explaining what is wrong.

    Returns:
        The converted value from the first input the parser accepts.
    """
    while True:
        try:
            return parser(input(prompt))
        except ValueError as error:
            print(f"Invalid input: {error}")


def get_valid_float(prompt: str, allow_zero: bool = True) -> float:
    """Prompt until the user enters a valid dollar amount."""
    return get_valid_input(prompt, lambda text: parse_amount(text, allow_zero))


def get_valid_date(prompt: str) -> date:
    """Prompt until the user enters a valid date (YYYY-MM-DD)."""
    return get_valid_input(prompt, parse_date)


# Main Program

def show_total_expenses(manager: BudgetManager) -> None:
    """Display total spending and a per-category breakdown."""
    month = get_valid_input(
        "Enter a month (YYYY-MM) or press Enter for all expenses: ",
        parse_month,
    )
    period = month if month else "all time"
    totals = manager.totals_by_category(month)
    total = manager.total_expenses(month)
    print(f"\nTotal expenses ({period}): ${total:,.2f}")
    for name, category_total in totals.items():
        print(f"  {name:<{MAX_CATEGORY_LENGTH}} ${category_total:>14,.2f}")


def show_savings_progress(manager: BudgetManager) -> None:
    """Display whether the user is on track to reach the savings goal."""
    current_savings, still_needed, on_track = manager.progress_toward_goal()
    if manager.savings_goal == 0:
        print("No savings goal is set yet. Choose option 2 to set one.")
        print(f"Current savings: ${current_savings:,.2f}")
    elif on_track:
        print("You are on track!")
        print(
            f"Current savings: ${current_savings:,.2f} "
            f"(goal: ${manager.savings_goal:,.2f})"
        )
    else:
        print(
            f"Current savings ${current_savings:,.2f}. "
            f"You need ${still_needed:,.2f} to reach your goal."
        )


def main() -> None:
    """Run the menu loop until the user chooses to save and exit."""
    manager = BudgetManager()

    print("Welcome to Personal Budgeting Application!")

    try:
        while True:
            print("\nMenu:")
            print("1. Set Income")
            print("2. Set Savings Goal")
            print("3. Add Expense")
            print("4. View Total Expenses")
            print("5. View Savings Progress")
            print("6. Visualize Expenses")
            print("7. Save & Exit")

            choice = input("Choose an option (1-7): ").strip()

            if choice == "1":
                income = get_valid_float("Enter your monthly income: $")
                manager.set_income(income)
                print(f"Income set to ${manager.income:,.2f}")

            elif choice == "2":
                goal = get_valid_float("Enter your savings goal: $")
                manager.set_savings_goal(goal)
                print(f"Savings goal set to ${manager.savings_goal:,.2f}")

            elif choice == "3":
                category = get_valid_input(
                    "Enter expense category (e.g., Rent, Groceries): ",
                    clean_category,
                )
                amount = get_valid_float(
                    "Enter expense amount: $", allow_zero=False
                )
                description = get_valid_input(
                    "Enter a brief description: ", clean_description
                )
                expense_date = get_valid_date(
                    "Enter expense date (YYYY-MM-DD): "
                )
                expense = manager.add_expense(
                    category, amount, description, expense_date
                )
                print(
                    f"Added: ${expense.amount:,.2f} '{expense.description}' "
                    f"to {category} on {expense.date}"
                )

            elif choice == "4":
                show_total_expenses(manager)

            elif choice == "5":
                show_savings_progress(manager)

            elif choice == "6":
                manager.visualize_expenses()

            elif choice == "7":
                if manager.save_data():
                    print("Data saved successfully. Exiting the program.")
                else:
                    print("Exiting the program without saving.")
                break

            else:
                print("Invalid choice. Please try again.")
    except (EOFError, KeyboardInterrupt):
        # Ctrl+C or a closed input stream should not lose the user's data.
        print("\nInput ended. Saving your data before exiting.")
        manager.save_data()


if __name__ == "__main__":
    main()
