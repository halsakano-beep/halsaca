def calculate(a, op, b):
    if op == "+":
        return a + b
    elif op == "-":
        return a - b
    elif op == "*":
        return a * b
    elif op == "/":
        if b == 0:
            return "エラー: 0では割れません"
        return a / b
    else:
        return "エラー: 不明な計算記号です"


def test_add():
    assert calculate(3, "+", 4) == 7
    assert calculate(-1, "+", 1) == 0
    print("✓ 足し算テスト合格")

def test_subtract():
    assert calculate(10, "-", 3) == 7
    print("✓ 引き算テスト合格")

def test_multiply():
    assert calculate(6, "*", 7) == 42
    print("✓ 掛け算テスト合格")

def test_divide():
    assert calculate(10, "/", 2) == 5
    assert calculate(1, "/", 0) == "エラー: 0では割れません"
    print("✓ 割り算テスト合格")

def test_unknown_op():
    assert calculate(1, "?", 1) == "エラー: 不明な計算記号です"
    print("✓ 不明な演算子テスト合格")


if __name__ == "__main__":
    test_add()
    test_subtract()
    test_multiply()
    test_divide()
    test_unknown_op()
    print("\n全テスト合格！")
