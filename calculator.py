print("電卓アプリ")
print("----------")

while True:
    a = float(input("最初の数字を入力してください: "))
    op = input("計算の種類を入力してください (+ - * /): ")
    b = float(input("次の数字を入力してください: "))

    if op == "+":
        result = a + b
    elif op == "-":
        result = a - b
    elif op == "*":
        result = a * b
    elif op == "/":
        if b == 0:
            result = "エラー: 0では割れません"
        else:
            result = a / b
    else:
        result = "エラー: 不明な計算記号です"

    print(f"答え: {result}")

    again = input("もう一度計算しますか？ (y/n): ")
    if again.lower() != "y":
        print("終了します。")
        break
