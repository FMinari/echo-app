"""Confere o "Salvar áudio" (app/nucleo/audio.py) no que dá para conferir fora do Windows: o nome do
arquivo, quais vozes são inglês, a ordem das vozes a tentar e as recusas. A gravação em si (SAPI) só roda
no Windows: lá, salve o áudio de uma frase pelo app e confira o .wav em Músicas › Sitcomática.

Uso: app/.venv/bin/python -I ferramentas/testar_audio.py
"""
import os
import sys
import tempfile
from pathlib import Path

PASTA = Path(tempfile.mkdtemp(prefix="sitcomatica-audio-"))
os.environ["FRASES_AUDIOS"] = str(PASTA)
os.environ["FRASES_DADOS"] = str(PASTA / "dados.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from nucleo import audio  # noqa: E402

falhas = []


def caso(nome, cond, detalhe=""):
    print(("ok  " if cond else "ERRO"), nome, detalhe)
    if not cond:
        falhas.append(nome)


def erro(fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        return str(e)
    return None


ep = {"obra": "Friends", "referencia": "S04E12", "tipo": "serie",
      "frase": "I mean if they had lost, we would've made them get rid of the birds and the duck too, right?"}
nome = audio.nome_do_arquivo(ep)
caso("nome com obra e episódio", nome.startswith("Friends S04E12 - I mean if they had lost"), nome)
caso("frase cortada numa palavra inteira", nome.endswith(".wav") and len(nome) < 90 and "rig.wav" not in nome, nome)
filme = audio.nome_do_arquivo({"obra": "Shrek", "referencia": "filme", "tipo": "filme", "frase": 'What? "Ogres": are/like <onions>?'})
caso("filme sem episódio e sem o que o Windows não aceita", filme == "Shrek - What Ogres are like onions.wav", filme)
caso("velocidade no nome", audio.nome_do_arquivo(ep, "bem-devagar").endswith("(bem devagar).wav"))
caso("frase só de pontuação ainda tem nome", audio.nome_do_arquivo({"frase": "..."}) == "Frase.wav")

caso("409 é inglês", audio._em_ingles("409"))
caso("809;9 é inglês", audio._em_ingles("809;9"))
caso("416 (português) não é", not audio._em_ingles("416"))
caso("lixo não quebra", not audio._em_ingles("abc;") and not audio._em_ingles(None))

V = [{"nome": "Microsoft Hazel - English (United Kingdom)", "curto": "Microsoft Hazel", "idioma": "809", "token": "a"},
     {"nome": "Microsoft Zira - English (United States)", "curto": "Microsoft Zira", "idioma": "409", "token": "b"},
     {"nome": "Microsoft David - English (United States)", "curto": "Microsoft David", "idioma": "409", "token": "c"}]
ordem, achou = audio.escolher(V, "Microsoft Hazel - English (United Kingdom)")
caso("a voz do Ouvir vem primeiro", achou and [v["token"] for v in ordem] == ["a", "b", "c"])
ordem, achou = audio.escolher(V, "Microsoft David")
caso("acha pelo nome curto", achou and ordem[0]["token"] == "c")
ordem, achou = audio.escolher(V, "Microsoft Aria Online (Natural) - English (United States)")
caso("voz Online: americanas antes, e avisa", not achou and [v["token"] for v in ordem] == ["b", "c", "a"])
ordem, achou = audio.escolher(V, None)
caso("sem voz escolhida: americana", not achou and ordem[0]["idioma"] == "409")
caso("sem vozes: nada a tentar", audio.escolher([], "x") == ([], False))

caso("frase vazia recusada", erro(audio.salvar, {"frase": "  "}) == "Essa frase está vazia.")
if sys.platform != "win32":
    caso("fora do Windows avisa", "só funciona no Windows" in (erro(audio.salvar, ep) or ""))
(PASTA / "Friends S04E12 - Hi.wav").write_bytes(b"x")
(PASTA / "Friends S04E12 - Hi (2).wav").write_bytes(b"x")
caso("não sobrescreve: numera", audio.livre(PASTA / "Friends S04E12 - Hi.wav").name == "Friends S04E12 - Hi (3).wav")
caso("nome livre fica igual", audio.livre(PASTA / "Outra.wav").name == "Outra.wav")
caso("mostrar só abre áudio da pasta", erro(audio.mostrar, "/etc/passwd") is not None
     and erro(audio.mostrar, str(PASTA / "x.txt")) is not None)

# ---------- textos (1.5): MP3, com volta para .wav ----------
caso("nome do texto: aula e título", audio.nome_do_texto({"titulo": "My weekend", "aula": "Aula 5"}) == "Aula 5 - My weekend.mp3")
caso("nome do texto sem aula: só o título", audio.nome_do_texto({"titulo": 'A "b": c?', "aula": None}) == "A b c.mp3")
caso("nome do texto com velocidade", audio.nome_do_texto({"titulo": "T", "aula": None}, 0.75) == "T (0,75x).mp3")
caso("velocidade normal fica fora do nome", audio.nome_do_texto({"titulo": "T", "aula": None}, 1.0) == "T.mp3")
caso("ajustes: velocidade, tom e volume na escala da SAPI (a mesma conta do Edge)",
     audio.ajustes_sapi({"taxa": 0.75, "tom": 1.2, "volume": 80}) == (-3, 2, 80), str(audio.ajustes_sapi({"taxa": 0.75, "tom": 1.2, "volume": 80})))
caso("ajustes: sem nada é o normal", audio.ajustes_sapi(None) == (0, 0, 100))
caso("ajustes: fora da faixa e lixo não passam", audio.ajustes_sapi({"taxa": 9, "tom": -4, "volume": 300}) == (6, -5, 100)
     and audio.ajustes_sapi({"taxa": "x", "tom": None, "volume": "alto"}) == (0, 0, 100))
caso("texto vazio recusado", erro(audio.salvar_texto, {"titulo": "T", "corpo": " \n "}) == "Esse texto está vazio.")

import wave  # noqa: E402


def _wav(caminho, segundos, hz):
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(hz)
        w.writeframes(b"\x01\x00" * int(segundos * hz))


amostra = PASTA / "amostra.wav"
_wav(amostra, 2.5, 44100)
blocos = list(audio._blocos_pcm(amostra))
caso("PCM em blocos: todos os bytes, em ordem", sum(len(b) for b, _, _ in blocos) == 2.5 * 44100 * 2
     and [t for _, t, _ in blocos] == sorted(t for _, t, _ in blocos) and blocos[0][1] == 0, f"{len(blocos)} blocos")
caso("PCM em blocos: tempos em 100 ns que fecham a duração", sum(d for _, _, d in blocos) == 25_000_000
     and all(t + d == blocos[i + 1][1] for i, (_, t, d) in enumerate(blocos[:-1])))
_wav(amostra, 1, 22050)
caso("PCM: só aceita 44,1 kHz mono 16 bits", erro(lambda: list(audio._blocos_pcm(amostra))) is not None)

# a gravação e a conversão de verdade só rodam no Windows: aqui entram falsas, para conferir o caminho em volta
gravados = []


def gravar_falso(texto, voz_, taxa, destino, hz=22050, tom=0, volume=100):
    gravados.append((texto, voz_["token"], Path(destino), hz, taxa, tom, volume))
    _wav(destino, 1, hz)


def mp3_falso(origem, destino):
    Path(destino).write_bytes(b"ID3" + b"\x00" * 5000)


def mp3_quebrado(origem, destino):
    Path(destino).write_bytes(b"pela metade")
    raise OSError("[WinError -1072875852] codificador não achou um tipo")


antes = (audio._windows, audio.vozes, audio._gravar_windows, audio._mp3_windows)
audio._windows, audio.vozes, audio._gravar_windows = (lambda: True), (lambda: V), gravar_falso
try:
    audio._mp3_windows = mp3_falso
    t = {"titulo": "My weekend", "aula": "Aula 5", "corpo": "I went\nto the beach."}
    r = audio.salvar_texto(t, {"voz": "Microsoft David"})
    caso("texto vira .mp3 na pasta", r["nome"] == "Aula 5 - My weekend.mp3" and Path(r["arquivo"]).exists()
         and r["formato"] == "mp3" and r["voz"] == "Microsoft David", str(r))
    caso("gravado em 44,1 kHz, com o texto numa linha só", gravados[-1][3] == 44100
         and gravados[-1][0] == "I went to the beach.")
    caso("o .wav temporário não fica", not gravados[-1][2].exists() and gravados[-1][2].parent != PASTA)
    r_ajustes = audio.salvar_texto(t, {"voz": "Microsoft David", "taxa": 0.75, "tom": 1.2, "volume": 80})
    caso("grava com a velocidade, o tom e o volume escolhidos", gravados[-1][4:] == (-3, 2, 80)
         and r_ajustes["nome"] == "Aula 5 - My weekend (0,75x).mp3", f"{gravados[-1][4:]} {r_ajustes['nome']}")
    r2 = audio.salvar_texto(t, {"voz": "Microsoft David"})
    caso("de novo: não sobrescreve", r2["nome"] == "Aula 5 - My weekend (2).mp3", r2["nome"])

    audio._mp3_windows = mp3_quebrado
    r3 = audio.salvar_texto(t, {"voz": "Microsoft David"})
    caso("MP3 falhou: fica o .wav e avisa", r3["formato"] == "wav" and r3["nome"] == "Aula 5 - My weekend.wav"
         and Path(r3["arquivo"]).exists() and r3.get("sem_mp3"), str(r3))
    caso("MP3 falhou: nada pela metade na pasta", not any(p.suffix == ".mp3" and p.stat().st_size < 100
                                                         for p in PASTA.iterdir()))
    caso("MP3 falhou: o .wav temporário não fica", not gravados[-1][2].exists())

    r4 = audio.salvar(ep, "Microsoft David")
    caso("frase continua em .wav de 22 kHz", r4["nome"].endswith(".wav") and gravados[-1][3] == 22050, r4["nome"])
    import subprocess
    abertos, popen = [], subprocess.Popen
    subprocess.Popen = lambda argumentos, **_: abertos.append(argumentos)  # sem abrir o Explorador de verdade
    try:
        caso("mostrar abre .mp3 da pasta", erro(audio.mostrar, r["arquivo"]) is None and len(abertos) == 1)
    finally:
        subprocess.Popen = popen
finally:
    audio._windows, audio.vozes, audio._gravar_windows, audio._mp3_windows = antes

if falhas:
    print(f"\n{len(falhas)} falha(s): {', '.join(falhas)}")
    sys.exit(1)
print("\ntudo certo")
