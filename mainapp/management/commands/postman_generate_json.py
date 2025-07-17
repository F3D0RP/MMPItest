import json

answers = {str(i): "1" for i in range(1, 567)}
with open("answers.json", "w", encoding="utf-8") as f:
    json.dump(answers, f, indent=2, ensure_ascii=False)

print("Файл answers.json успешно создан!")
