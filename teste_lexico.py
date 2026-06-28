# teste_lexico.py
# Testa o módulo do léxico com uma ata real do Copom

from pathlib import Path
from src.copom.features.lexico import calcular_lexico

# lê a ata mais recente — reunião 279, junho de 2026
caminho = Path("data/raw/ata_279_2026-06-17.txt")
texto = caminho.read_text(encoding="utf-8")

# roda o léxico
resultado = calcular_lexico(texto)

# mostra o resultado
print("=== CopomLens — Baseline Léxico ===")
print(f"Score:      {resultado['score']}")
print(f"Hawkish:    {resultado['n_hawkish']} palavras → {resultado['palavras_hawkish']}")
print(f"Dovish:     {resultado['n_dovish']} palavras → {resultado['palavras_dovish']}")