import sys

def in_virtualenv():
    """Check if the current Python interpreter is running inside a virtual environment."""
    return sys.prefix != sys.base_prefix

if in_virtualenv():
    print("Inside a virtual environment")
else:
    print("Not in a virtual environment")

