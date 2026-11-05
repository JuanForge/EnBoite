RED = "\033[38;5;196m"
GREEN = "\033[32m"
RESET = "\033[0m"
YELLOW = "\033[93m"

STATUS: bool = True

def no_color():
    global RED, GREEN, RESET, YELLOW, STATUS
    RED = GREEN = RESET = YELLOW = ""
    STATUS = False