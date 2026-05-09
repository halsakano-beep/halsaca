from calc_core import calculate, add_to_history


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
    assert calculate(10, "/", 2) == 5.0
    assert calculate(1, "/", 0) is None
    print("✓ 割り算テスト合格")

def test_unknown_op():
    assert calculate(1, "?", 1) is None
    print("✓ 不明な演算子テスト合格")

def test_history_limit():
    history = []
    for i in range(15):
        add_to_history(history, i, "+", 0, i)
    assert len(history) == 10, f"履歴は10件以内のはず: {len(history)}件"
    print("✓ 履歴件数制限テスト合格")

def test_history_format():
    history = []
    add_to_history(history, 3, "+", 4, 7)
    assert history[0] == "3.0 + 4.0 = 7"
    print("✓ 履歴フォーマットテスト合格")


if __name__ == "__main__":
    test_add()
    test_subtract()
    test_multiply()
    test_divide()
    test_unknown_op()
    test_history_limit()
    test_history_format()
    print("\n全テスト合格！")
