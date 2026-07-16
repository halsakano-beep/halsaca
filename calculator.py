print("電卓アプリ")
print("----------")
print("コマンド: h=履歴表示 / n=次の計算 / q=終了")

history = []

while True:
    command = input("\n> ").strip().lower()

    if command == "q":
        print("終了します。")
        break
    elif command == "h":
        if not history:
            print("履歴はまだありません。")
        else:
            print("--- 計算履歴 ---")
            for i, entry in enumerate(history, 1):
                print(f"  {i}. {entry}")
            print("----------------")
    elif command == "n" or command == "":
        try:
            a = float(input("最初の数字を入力してください: "))
            op = input("計算の種類を入力してください (+ - * /): ")
            b = float(input("次の数字を入力してください: "))
        except ValueError:
            print("エラー: 数字を正しく入力してください。")
            continue

        if op == "+":
            result = a + b
        elif op == "-":
            result = a - b
        elif op == "*":
            result = a * b
        elif op == "/":
            if b == 0:
                print("エラー: 0では割れません")
                continue
            result = a / b
        else:
            print("エラー: 不明な計算記号です")
            continue

        print(f"答え: {result}")
        history.append(f"{a} {op} {b} = {result}")
        if len(history) > 10:
            history.pop(0)
    else:
        print("不明なコマンドです。h=履歴 / n=計算 / q=終了")
