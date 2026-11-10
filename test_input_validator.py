
from src.utils.input_validator import validate_ticket


test_cases = [

    ("Rahul", "My VPN is not connecting."),

    ("", "My VPN is not connecting."),

    ("A", "My VPN is not connecting."),

    ("Rahul", ""),

    ("Rahul", "Hi"),

    ("Rahul", "1234567890"),

]


for employee_name, issue in test_cases:

    is_valid, message = validate_ticket(
        employee_name,
        issue
    )

    print("\nEmployee:", employee_name)
    print("Issue:", issue)
    print("Valid:", is_valid)
    print("Message:", message)
