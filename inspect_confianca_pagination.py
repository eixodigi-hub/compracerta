import json
from pathlib import Path

JSON_PATH = Path(
    "/Users/williamcamargo/Projects/compra-certa-mar-lia/"
    "logs/confianca_api_probe_20260718_091243/products_01.json"
)

with JSON_PATH.open("r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 100)
print("INSPEÇÃO DE PAGINAÇÃO, API CONFIANÇA")
print("=" * 100)

print("\nTIPO DA RAIZ:")
print(type(data).__name__)

if not isinstance(data, dict):
    raise SystemExit("A raiz do JSON não é um objeto/dict.")

print("\nCHAVES DA RAIZ:")
for key in data.keys():
    print(f"  {key}")

print("\n" + "=" * 100)
print("VALORES SIMPLES NA RAIZ")
print("=" * 100)

for key, value in data.items():
    if isinstance(value, (str, int, float, bool)) or value is None:
        print(f"{key} = {repr(value)}")

print("\n" + "=" * 100)
print("ESTRUTURAS POSSIVELMENTE RELACIONADAS À PAGINAÇÃO")
print("=" * 100)

keywords = (
    "page",
    "paging",
    "offset",
    "limit",
    "size",
    "total",
    "count",
    "range",
    "next",
    "previous",
    "first",
    "last",
    "start",
    "end"
)

def walk(obj, path="root", depth=0):
    if depth > 4:
        return

    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}"

            if any(word in str(key).lower() for word in keywords):
                if isinstance(value, (dict, list)):
                    preview = f"<{type(value).__name__}>"
                else:
                    preview = repr(value)

                print(f"{current_path} = {preview}")

            walk(value, current_path, depth + 1)

    elif isinstance(obj, list):
        # Não percorre todos os produtos para evitar saída gigantesca.
        # Inspeciona apenas o primeiro elemento estruturalmente.
        if obj:
            walk(obj[0], f"{path}[0]", depth + 1)

walk(data)

print("\n" + "=" * 100)
print("ITEMS")
print("=" * 100)

items = data.get("items")

if isinstance(items, list):
    print(f"Quantidade em root.items: {len(items)}")
else:
    print("root.items não encontrado como lista.")

print("\n" + "=" * 100)
print("OUTRAS LISTAS NA RAIZ")
print("=" * 100)

for key, value in data.items():
    if isinstance(value, list):
        print(f"{key}: {len(value)} registros")

print("\n" + "=" * 100)
print("OBJETOS DA RAIZ, PRIMEIRO NÍVEL")
print("=" * 100)

for key, value in data.items():
    if isinstance(value, dict):
        print(f"\n[{key}]")

        for subkey, subvalue in value.items():
            if isinstance(subvalue, (str, int, float, bool)) or subvalue is None:
                print(f"  {subkey} = {repr(subvalue)}")
            elif isinstance(subvalue, list):
                print(f"  {subkey} = <list com {len(subvalue)} itens>")
            elif isinstance(subvalue, dict):
                print(f"  {subkey} = <dict com {len(subvalue)} chaves>")

print("\n" + "=" * 100)
print("SOMENTE LEITURA. NENHUM ARQUIVO, COLETOR OU BANCO FOI ALTERADO.")
print("=" * 100)
