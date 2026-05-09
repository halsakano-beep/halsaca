def calculate(a, op, b):
    if op == "+":
        return a + b
    elif op == "-":
        return a - b
    elif op == "*":
        return a * b
    elif op == "/":
        if b == 0:
            return None
        return a / b
    return None


def add_to_history(history, a, op, b, result):
    history.append(f"{float(a)} {op} {float(b)} = {result}")
    if len(history) > 10:
        history.pop(0)
