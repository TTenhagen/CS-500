import math

# Pure arithmetic functions, kept separate from input/output so they can be unit tested.
def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    # Raises ZeroDivisionError when b is 0; the menu loop catches it and shows a message.
    return a / b


# Maps each menu choice to its label, symbol, and function.
OPERATIONS = {
    "1": ("Addition", "+", add),
    "2": ("Subtraction", "-", subtract),
    "3": ("Multiplication", "*", multiply),
    "4": ("Division", "/", divide),
}
EXIT_CHOICE = "5"


def calculate(choice, a, b):
    """Run the operation for a menu choice. Raises ValueError for an unknown choice."""
    if choice not in OPERATIONS:
        raise ValueError(f"Invalid operation: {choice}")
    _, _, operation = OPERATIONS[choice]
    return operation(a, b)


def parse_number(text):
    """Convert user text to a float. Raises ValueError for text that is not a finite number."""
    value = float(text.strip())
    # float() also accepts "inf" and "nan", which would produce meaningless results.
    if not math.isfinite(value):
        raise ValueError(f"Not a finite number: {text}")
    return value


def display_menu():
    print("\n===== Simple Calculator =====")
    for key, (label, symbol, _) in OPERATIONS.items():
        print(f"{key}. {label} ({symbol})")
    print(f"{EXIT_CHOICE}. Exit")


def get_number(prompt):
    """Keep prompting until the user enters a valid number."""
    while True:
        try:
            return parse_number(input(prompt))
        except ValueError:
            print("That is not a valid number. Please try again.")


def format_result(value):
    # Show 8.0 as 8, but keep real decimals like 2.5.
    return str(int(value)) if value.is_integer() else str(value)


def main():
    while True:
        display_menu()
        choice = input("Select an operation (1-5): ").strip()

        if choice == EXIT_CHOICE:
            print("Goodbye!")
            break
        if choice not in OPERATIONS:
            print("Invalid choice. Please enter a number from 1 to 5.")
            continue

        a = get_number("Enter the first number: ")
        b = get_number("Enter the second number: ")
        label, symbol, _ = OPERATIONS[choice]

        try:
            result = calculate(choice, a, b)
            print(f"Result: {format_result(a)} {symbol} {format_result(b)} = {format_result(result)}")
        except ZeroDivisionError:
            print("Error: Division by zero is not allowed.")

        again = input("Perform another calculation? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()
