"""Janela do app: o Python serve a tela (ui/) num servidor local só dele e o Microsoft Edge a mostra em
modo aplicativo. Assim só rodam programas assinados, o Python do python.org e o Edge: o Controle
Inteligente de Aplicativos do Windows bloqueia o resto (ver o plano F16).

- app.py       ponto de partida (atalho, dois cliques num .sitcomatica, modo --navegador)
- api.py       os métodos que a tela chama (POST /api/<método>)
- servidor.py  o servidor local: senha da sessão, Host conferido, fecha sozinho sem sinal da tela
- edge.py      abre a tela no Edge em modo aplicativo
- sistema.py   o que é do Windows: o tipo .sitcomatica e a mensagem de erro quando nem a janela abre
"""
from pathlib import Path

PASTA = Path(__file__).resolve().parent
APP = PASTA.parent
UI = PASTA / "ui"
ICONE = PASTA / "icone.ico"
