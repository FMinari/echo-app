"""Gera app/janela/icone.ico e icone.png (o ícone do Echo: o "o" alto-falante amarelo em fundo preto) a partir
dos desenhos em ferramentas/marca/: icone.svg para 32 px ou mais, icone-pequeno.svg (anel e uma onda só, sem o
cone) para 16 e 24 px, onde o desenho completo vira um borrão.

Uso (rsvg-convert e magick só no PC do dev; nada disso entra no app): python3 -I ferramentas/gerar_icone.py
"""
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCA = RAIZ / "ferramentas" / "marca"
DESTINO = RAIZ / "app" / "janela" / "icone.ico"

with tempfile.TemporaryDirectory() as pasta:
    camadas = []
    for tamanho in (16, 24, 32, 48, 64, 128, 256):
        desenho = MARCA / ("icone-pequeno.svg" if tamanho < 32 else "icone.svg")
        png = Path(pasta) / f"{tamanho}.png"
        subprocess.run(["rsvg-convert", "-w", str(tamanho), "-h", str(tamanho), str(desenho), "-o", str(png)], check=True)
        camadas.append(str(png))
    subprocess.run(["magick", *camadas, str(DESTINO)], check=True)
    subprocess.run(["rsvg-convert", "-w", "256", "-h", "256", str(MARCA / "icone.svg"), "-o",
                    str(DESTINO.with_suffix(".png"))], check=True)
print(DESTINO)
