"""Executa o notebook analise.ipynb de ponta a ponta e regenera as figuras.

Uso: abra este arquivo no VS Code e clique no ▶ (ou: python rodar.py).
Equivale a: jupyter nbconvert --to notebook --execute analise.ipynb --output analise.ipynb
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)

try:
    import nbformat
    from nbclient import NotebookClient
except ImportError:
    sys.exit("Faltam dependências. Selecione o interpretador do .venv no VS Code "
             "(Ctrl+Shift+P > 'Python: Select Interpreter') ou rode: pip install -r requirements.txt")

if sys.platform == "win32":  # evita aviso do zmq no Windows
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

print("Executando analise.ipynb (cerca de 30 s)...")
nb = nbformat.read(RAIZ / "analise.ipynb", as_version=4)
NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(RAIZ)}}).execute()
nbformat.write(nb, RAIZ / "analise.ipynb")

figuras = sorted((RAIZ / "figures").glob("*.png"))
print(f"\nPronto! Notebook executado sem erros e {len(figuras)} figuras geradas em figures/:")
for f in figuras:
    print("  -", f.name)
print("\nAbra analise.ipynb no VS Code para ver tabelas e gráficos, ou as imagens em figures/.")
