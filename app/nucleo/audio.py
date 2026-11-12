"""Salvar o áudio de uma frase (.wav) ou de um texto da cliente (.mp3), com as vozes em inglês do Windows (para
a cliente usar na aula).

O "Ouvir" da tela usa o speechSynthesis do Edge, que só toca. Aqui a gravação é pela SAPI do Windows,
chamada pela ctypes (biblioteca padrão; nada de PowerShell, que o Controle Inteligente de Aplicativos pode
deixar em modo restrito). As vozes vêm do registro: `Speech_OneCore` (as que se instalam em Configurações ›
Fala) e `Speech` (as antigas). As "Online (Natural)" do Edge são da internet e não dão para gravar: aí vai
uma voz em inglês do Windows, e a resposta diz qual.

O MP3 do texto sai do codificador que já vem no Windows (Media Foundation, também pela ctypes): a SAPI grava
um .wav temporário e ele vira .mp3. Se o MP3 falhar, o áudio não se perde: fica o .wav, e a resposta avisa.

Os arquivos ficam em Músicas › Echo: o da frase com o nome da obra, do episódio e o começo da frase; o
do texto com o nome da aula e o título.
"""
import math
import os
import re
import shutil
import sys
import tempfile
import uuid
import wave
from pathlib import Path

PASTA_NOME = "Echo"  # até a 1.4.1 era "Sitcomática": os áudios de antes ficam lá
RAIZES = (r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens", r"SOFTWARE\Microsoft\Speech\Voices\Tokens")
# a mesma velocidade do "Ouvir" (taxa 1 / 0,8 / 0,6 no Edge); na SAPI cada passo é ~10% (de -10 a 10)
TAXAS = {"normal": 0, "devagar": -2, "bem-devagar": -4}
HZ_FRASE = 22050
HZ_MP3 = 44100  # o codificador MP3 do Windows (MPEG-1) aceita 32, 44,1 ou 48 kHz
KBPS_MP3 = 96   # voz mono: bom e pequeno (1 minuto ≈ 0,7 MB)
SEM_VOZ = ("Para salvar o áudio, o Windows precisa de uma voz em inglês: Configurações › Hora e idioma › Fala › "
           "Adicionar vozes › Inglês (Estados Unidos). Depois, feche e abra o app.")


def pasta():
    """Músicas › Echo (a pasta Músicas de verdade, mesmo se ela tiver mudado de lugar)."""
    if os.environ.get("FRASES_AUDIOS"):
        return Path(os.environ["FRASES_AUDIOS"])
    musicas = Path.home() / "Music"
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                musicas = Path(os.path.expandvars(winreg.QueryValueEx(k, "My Music")[0]))
        except OSError:
            pass
    return musicas / PASTA_NOME


def _windows():
    return sys.platform == "win32"


def _limpo(nome, padrao):
    """Sem o que o Windows não aceita em nome de arquivo, nem ponto ou espaço no fim."""
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", nome)
    return " ".join(nome.split()).rstrip(". ") or padrao


def _com_velocidade(nome, velocidade):
    return nome + (f" ({velocidade.replace('-', ' ')})" if velocidade != "normal" else "")


def nome_do_arquivo(x, velocidade="normal"):
    """'Friends S04E12 - If they had lost, we would've made them get rid.wav' (sem o que o Windows
    não aceita em nome de arquivo)."""
    onde = x.get("obra") or "Frase"
    if x.get("tipo") == "musica":
        onde += f" - {x['titulo']}" if x.get("titulo") else ""
    elif x.get("referencia") and x.get("referencia") != "filme" and x.get("tipo") != "filme":
        onde += f" {x['referencia']}"
    frase = " ".join(str(x.get("frase") or "").split())
    if len(frase) > 60:
        frase = frase[:60].rsplit(" ", 1)[0]
    nome = f"{onde} - {frase}" if re.search(r"\w", frase) else onde
    return _limpo(_com_velocidade(nome, velocidade), "frase") + ".wav"


def nome_do_texto(t, taxa=1.0):
    """'Aula 5 - My weekend.mp3' (só o título, em "Sem aula"), cortado numa palavra inteira; com a
    velocidade quando não é a normal ('… (0,75x).mp3')."""
    titulo = " ".join(str(t.get("titulo") or "").split())
    nome = f"{t['aula']} - {titulo}" if t.get("aula") else titulo
    if len(nome) > 120:
        nome = nome[:120].rsplit(" ", 1)[0]
    taxa = round(float(taxa), 2)
    if taxa != 1:
        nome += f" ({f'{taxa:g}'.replace('.', ',')}x)"
    return _limpo(nome, "texto") + ".mp3"


def _numero(valor, padrao, minimo, maximo):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    return padrao if math.isnan(numero) else min(maximo, max(minimo, numero))


def taxa_do_texto(ajustes):
    """A velocidade pedida na tela (1 = normal), dentro da faixa que a tela oferece."""
    return _numero((ajustes or {}).get("taxa"), 1.0, 0.5, 2.0)


def ajustes_sapi(ajustes):
    """Os ajustes da tela ({taxa, tom, volume}, como os do speechSynthesis: taxa e tom com 1 = normal,
    volume de 0 a 100) na escala da SAPI: (velocidade de -10 a 10, tom de -10 a 10, volume de 0 a 100).
    É a mesma conta que o Edge faz para ler com essas vozes (Chromium, tts_win.cc): cada passo de
    velocidade da SAPI é ~10% (3 elevado a 1/10), e o tom vai de 0,5 a 1,5 → -5 a 5."""
    ajustes = ajustes or {}
    taxa = round(10 * math.log(taxa_do_texto(ajustes)) / math.log(3))
    tom = round((_numero(ajustes.get("tom"), 1.0, 0.5, 1.5) - 1) * 10)
    volume = round(_numero(ajustes.get("volume"), 100, 0, 100))
    return max(-10, min(10, taxa)), tom, volume


def para_ler(corpo):
    """O texto como a voz deve ler: cada parágrafo (separado por linha em branco) numa linha só, com ponto
    no fim se a cliente não pôs (um título sem ponto ganha a pausa), e os parágrafos um depois do outro."""
    paragrafos = [" ".join(p.split()) for p in re.split(r"\n\s*\n", str(corpo or ""))]
    return " ".join(p if p[-1] in ".!?;:…\"'”’)" else p + "." for p in paragrafos if p)


# ---------- vozes ----------
def _em_ingles(idioma):
    """'409' (en-US), '809;9'…: o código de idioma do Windows em hexadecimal; inglês = 0x09 no fim."""
    for parte in str(idioma or "").split(";"):
        try:
            if int(parte, 16) & 0x3FF == 0x09:
                return True
        except ValueError:
            pass
    return False


def vozes():
    """[{nome, curto, idioma, token, categoria}] das vozes em inglês instaladas no Windows (vazio fora
    dele): as do computador (HKLM) e as instaladas só para a cliente (HKCU)."""
    if not _windows():
        return []
    import winreg
    achadas = []
    lugares = [(hive, nome_hive, raiz) for hive, nome_hive in ((winreg.HKEY_LOCAL_MACHINE, "HKEY_LOCAL_MACHINE"),
                                                             (winreg.HKEY_CURRENT_USER, "HKEY_CURRENT_USER"))
               for raiz in RAIZES]
    for hive, nome_hive, raiz in lugares:
        try:
            tokens = winreg.OpenKey(hive, raiz)
        except OSError:
            continue
        with tokens:
            i = 0
            while True:
                try:
                    chave = winreg.EnumKey(tokens, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(tokens, chave) as k:
                        nome = winreg.QueryValueEx(k, "")[0]
                    with winreg.OpenKey(tokens, chave + r"\Attributes") as k:
                        idioma = winreg.QueryValueEx(k, "Language")[0]
                        curto = winreg.QueryValueEx(k, "Name")[0]
                except OSError:
                    continue
                if _em_ingles(idioma):
                    achadas.append({"nome": nome, "curto": curto, "idioma": idioma,
                                    "token": rf"{nome_hive}\{raiz}\{chave}",
                                    "categoria": rf"{nome_hive}\{raiz.removesuffix(chr(92) + 'Tokens')}"})
    return achadas


def escolher(lista, pedida):
    """As vozes a tentar, na ordem: a pedida (pelo nome do Edge, "Microsoft David - English (United
    States)", ou pelo curto, "Microsoft David"), depois as americanas, depois as outras em inglês.
    Devolve (candidatas, achou_a_pedida)."""
    pedida = str(pedida or "")
    curta = pedida.split(" - ")[0].strip().lower()
    iguais = [v for v in lista if pedida and (v["nome"] == pedida or v["curto"].lower() == curta)]
    eua = [v for v in lista if v not in iguais and "409" in str(v["idioma"]).split(";")]
    resto = [v for v in lista if v not in iguais and v not in eua]
    return iguais + eua + resto, bool(iguais)


# ---------- COM pela ctypes ----------
def _com():
    """(ctypes, GUID, guid, metodo) para falar com objetos COM: `guid("…")` monta o GUID do texto e
    `metodo(obj, i, *tipos)` pega o método i da tabela do objeto (a ordem é a do .idl da interface)."""
    import ctypes
    from ctypes import POINTER, c_void_p

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    def guid(texto_guid):
        return GUID.from_buffer_copy(uuid.UUID(texto_guid).bytes_le)

    def metodo(obj, indice, *tipos):
        tabela = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
        return ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *tipos)(tabela[indice])

    return ctypes, GUID, guid, metodo


# ---------- gravar (SAPI) ----------
def _gravar_windows(texto, voz_, taxa, destino, hz=HZ_FRASE, tom=0, volume=100):
    """Fala `texto` com a voz `voz_` (de vozes()) direto num .wav (`hz`, 16 bits, mono). Mesmo caminho
    do Edge (Chromium, tts_win.cc): SAPI no MTA, token aberto com a categoria dele, e o tom pela marca
    <pitch> do XML da SAPI (o texto vai escapado; sem tom, vai como texto puro)."""
    from .registro import log
    ctypes, GUID, guid, metodo = _com()
    from ctypes import POINTER, byref, c_void_p, c_wchar_p

    class WAVEFORMATEX(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("wFormatTag", ctypes.c_ushort), ("nChannels", ctypes.c_ushort),
                    ("nSamplesPerSec", ctypes.c_ulong), ("nAvgBytesPerSec", ctypes.c_ulong),
                    ("nBlockAlign", ctypes.c_ushort), ("wBitsPerSample", ctypes.c_ushort), ("cbSize", ctypes.c_ushort)]

    def criar(clsid, iid):
        obj = c_void_p()
        ole32.CoCreateInstance(byref(guid(clsid)), None, 0x17, byref(guid(iid)), byref(obj))  # CLSCTX_ALL
        return obj

    ole32 = ctypes.OleDLL("ole32")  # erro de HRESULT vira OSError
    inicio = ctypes.windll.ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
    objetos = []
    try:
        token = criar("ef411752-3736-4cb4-9c8c-8ef4ccb58efe", "14056589-e16c-11d2-bb90-00c04f8ee6c0")  # SpObjectToken
        objetos.append(token)
        metodo(token, 15, c_wchar_p, c_wchar_p, ctypes.c_int)(token, voz_["categoria"], voz_["token"], 0)  # SetId
        voz = criar("96749377-3391-11d2-9ee3-00c04f797396", "6c44df74-72b9-4992-a1ec-ef996e0422d4")  # SpVoice
        objetos.append(voz)
        metodo(voz, 18, c_void_p)(voz, token)  # SetVoice
        metodo(voz, 28, ctypes.c_long)(voz, taxa)  # SetRate
        metodo(voz, 30, ctypes.c_ushort)(voz, volume)  # SetVolume
        fluxo = criar("715d9c59-4442-11d2-9605-00c04f8ee628", "12e3cca9-7518-44c5-a5e7-ba5a79cb929e")  # SpStream
        objetos.append(fluxo)
        formato = WAVEFORMATEX(1, 1, hz, hz * 2, 2, 16, 0)
        metodo(fluxo, 17, c_wchar_p, ctypes.c_int, POINTER(GUID), POINTER(WAVEFORMATEX), ctypes.c_ulonglong)(
            fluxo, str(destino), 3, byref(guid("c31adbae-527f-4ff5-a230-f62bb61ff70c")), byref(formato), 0)  # BindToFile
        try:
            metodo(voz, 13, c_void_p, ctypes.c_int)(voz, fluxo, 1)  # SetOutput
            if tom:
                from xml.sax.saxutils import escape
                fala, marcas = f'<pitch absmiddle="{tom}">{escape(texto)}</pitch>', 0x08  # SPF_IS_XML
            else:
                fala, marcas = texto, 0x10  # SPF_IS_NOT_XML
            metodo(voz, 20, c_wchar_p, ctypes.c_ulong, c_void_p)(voz, fala, marcas, None)  # Speak
        finally:
            try:
                metodo(fluxo, 18)(fluxo)  # Close: fecha o .wav
            except OSError:  # não esconde o erro do Speak
                log.warning("fechar o .wav", exc_info=True)
    finally:
        for obj in reversed(objetos):
            if obj:
                metodo(obj, 2)(obj)  # Release
        if inicio in (0, 1):  # S_OK / S_FALSE: quem abriu fecha
            ctypes.windll.ole32.CoUninitialize()


def livre(destino):
    """O nome pedido ou, se já existe (outra voz, ou aberto no player), "nome (2).wav", "nome (3).wav"…"""
    n = 2
    novo = destino
    while novo.exists():
        novo = destino.with_name(f"{destino.stem} ({n}){destino.suffix}")
        n += 1
    return novo


def _preparar(voz):
    """As vozes a tentar e se a pedida está entre elas; recusa fora do Windows, sem voz em inglês ou sem
    a pasta dos áudios."""
    from .registro import AVISO, log
    if not _windows():
        raise ValueError("Salvar o áudio só funciona no Windows.")
    candidatas, achou = escolher(vozes(), voz)
    if not candidatas:
        raise ValueError(SEM_VOZ)
    try:
        pasta().mkdir(parents=True, exist_ok=True)
    except OSError:
        log.exception("criar a pasta dos áudios %s", pasta())
        raise ValueError(f"O Windows não deixou criar a pasta {pasta()} (talvez a proteção contra ransomware "
                         "do antivírus). " + AVISO) from None
    return candidatas, achou


def _gravar(texto, candidatas, taxa, destino, hz, tom=0, volume=100):
    """Grava com a primeira voz que der certo; devolve a voz usada."""
    from .registro import AVISO, log
    for v in candidatas:
        try:
            _gravar_windows(texto, v, taxa, destino, hz, tom, volume)
            if destino.stat().st_size > 4096:  # mais que um cabeçalho de .wav sem som
                return v
            log.warning("áudio com a voz %s saiu vazio", v["token"])
        except OSError:
            log.warning("áudio com a voz %s não saiu", v["token"], exc_info=True)
        try:
            destino.unlink(missing_ok=True)
        except OSError:
            log.warning("apagar o áudio que não saiu", exc_info=True)
    raise ValueError("Não consegui gravar o áudio com nenhuma voz do Windows. " + AVISO)


def _resposta(destino, v, voz, achou, candidatas):
    return {"arquivo": str(destino), "pasta": str(destino.parent), "nome": destino.name, "voz": v["curto"],
            "outra_voz": bool(voz) and not (achou and v is candidatas[0])}


def salvar(x, voz=None, velocidade="normal"):
    """Grava a frase `x` (resultado de busca ou frase da aula) num .wav. Devolve {arquivo, pasta, nome, voz,
    outra_voz}."""
    texto = " ".join(str(x.get("frase") or "").split())
    if not texto:
        raise ValueError("Essa frase está vazia.")
    candidatas, achou = _preparar(voz)
    destino = livre(pasta() / nome_do_arquivo(x, velocidade))
    v = _gravar(texto, candidatas, TAXAS.get(velocidade, 0), destino, HZ_FRASE)
    return _resposta(destino, v, voz, achou, candidatas)


def salvar_texto(t, ajustes=None):
    """Grava o texto `t` ({titulo, aula, corpo}) num .mp3 com os ajustes escolhidos na tela ({voz, taxa, tom,
    volume}: valem só para esta gravação, nada fica guardado); se o MP3 não sair, fica o .wav (`sem_mp3`).
    Devolve {arquivo, pasta, nome, voz, outra_voz, formato, sem_mp3}."""
    from .registro import log
    texto = para_ler(t.get("corpo"))
    if not texto:
        raise ValueError("Esse texto está vazio.")
    voz = (ajustes or {}).get("voz")
    taxa, tom, volume = ajustes_sapi(ajustes)
    candidatas, achou = _preparar(voz)
    nome = nome_do_texto(t, taxa_do_texto(ajustes))
    destino = livre(pasta() / nome)
    descritor, temporario = tempfile.mkstemp(prefix="sitcomatica-", suffix=".wav")
    os.close(descritor)
    temporario = Path(temporario)
    try:
        v = _gravar(texto, candidatas, taxa, temporario, HZ_MP3, tom, volume)
        try:
            _mp3_windows(temporario, destino)
            if destino.stat().st_size <= 1024:
                raise OSError(f"o .mp3 saiu com {destino.stat().st_size} bytes")
        except Exception:  # noqa: BLE001 — qualquer falha do codificador: fica o .wav
            log.warning("o MP3 não saiu; fica o .wav", exc_info=True)
            destino.unlink(missing_ok=True)
            destino = livre(pasta() / Path(nome).with_suffix(".wav"))
            shutil.move(temporario, destino)
    finally:
        temporario.unlink(missing_ok=True)
    formato = destino.suffix[1:]
    return {**_resposta(destino, v, voz, achou, candidatas), "formato": formato, "sem_mp3": formato != "mp3"}


# ---------- MP3 (Media Foundation) ----------
def _blocos_pcm(caminho, segundos=1):
    """O .wav da SAPI em blocos de `segundos`: (bytes, início, duração), com os tempos em unidades de 100 ns
    (as do Media Foundation), contados em amostras para um bloco começar exatamente onde o outro termina."""
    with wave.open(str(caminho), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, HZ_MP3):
            raise ValueError(f"áudio em formato inesperado para o MP3: {w.getparams()}")
        feitos = 0
        while True:
            dados = w.readframes(HZ_MP3 * segundos)
            if not dados:
                return
            n = len(dados) // 2
            inicio = feitos * 10_000_000 // HZ_MP3
            fim = (feitos + n) * 10_000_000 // HZ_MP3
            yield dados, inicio, fim - inicio
            feitos += n


def _mp3_windows(origem, destino):
    """Converte o .wav da SAPI (44,1 kHz, 16 bits, mono) em .mp3 com o IMFSinkWriter do Media Foundation e o
    codificador MP3 que vem no Windows. Os índices dos métodos seguem o mfobjects.idl e o mfreadwrite.idl."""
    from .registro import log
    ctypes, GUID, guid, metodo = _com()
    from ctypes import POINTER, byref, c_void_p, c_wchar_p
    u32 = ctypes.c_uint32

    def formato_de_audio(codigo):  # DEFINE_MEDIATYPE_GUID
        return f"{codigo:08x}-0000-0010-8000-00aa00389b71"

    AUDIO = "73647561-0000-0010-8000-00aa00389b71"  # MFMediaType_Audio
    PCM, MP3 = formato_de_audio(0x0001), formato_de_audio(0x0055)  # WAVE_FORMAT_PCM, WAVE_FORMAT_MPEGLAYER3
    TIPO = "48eba18e-f8c9-4687-bf11-0a74c9f96a8f"  # MF_MT_MAJOR_TYPE
    SUBTIPO = "f7e34c9a-42e8-4714-b74b-cb29d72c35e5"  # MF_MT_SUBTYPE
    CANAIS = "37e48bf5-645e-4c5b-89de-ada9e29b696a"  # MF_MT_AUDIO_NUM_CHANNELS
    HZ = "5faeeae7-0290-4c31-9e8a-c534f68d9dba"  # MF_MT_AUDIO_SAMPLES_PER_SECOND
    BYTES_POR_SEGUNDO = "1aab75c8-cfef-451c-ab95-ac034b8e1731"  # MF_MT_AUDIO_AVG_BYTES_PER_SECOND
    ALINHAMENTO = "322de230-9eeb-43bd-ab7a-ff412251541d"  # MF_MT_AUDIO_BLOCK_ALIGNMENT
    BITS = "f2deb57f-40fa-4764-aa33-ed4f2d1ff669"  # MF_MT_AUDIO_BITS_PER_SAMPLE
    INDEPENDENTES = "c9173739-5e56-461c-b713-46fb995cb95f"  # MF_MT_ALL_SAMPLES_INDEPENDENT
    CONTEINER = "150ff23f-4abc-478b-ac4f-e1916fba1cca"  # MF_TRANSCODE_CONTAINERTYPE
    CONTEINER_MP3 = "e438b912-83f1-4de6-9e3a-9ffbc6dd24d1"  # MFTranscodeContainerType_MP3
    IID_TIPO = "44ae0fa8-ea31-4109-8d2e-4cae4997c555"  # IMFMediaType

    def por_guid(obj, chave, valor):  # IMFAttributes::SetGUID
        metodo(obj, 24, POINTER(GUID), POINTER(GUID))(obj, byref(guid(chave)), byref(guid(valor)))

    def por_numero(obj, chave, valor):  # IMFAttributes::SetUINT32
        metodo(obj, 21, POINTER(GUID), u32)(obj, byref(guid(chave)), valor)

    def numero(obj, chave):  # IMFAttributes::GetUINT32
        valor = u32()
        metodo(obj, 7, POINTER(GUID), POINTER(u32))(obj, byref(guid(chave)), byref(valor))
        return valor.value

    def soltar(obj):
        if obj:
            metodo(obj, 2)(obj)  # Release

    mfplat, mf, mfrw = ctypes.OleDLL("mfplat"), ctypes.OleDLL("mf"), ctypes.OleDLL("mfreadwrite")

    def tipo_de_saida():
        """O tipo MP3 que o próprio codificador oferece em 44,1 kHz mono, com a taxa mais perto de KBPS_MP3;
        se ele não listar nenhum, um montado à mão com o mínimo que a documentação pede."""
        melhor, distancia = None, None
        tipos = c_void_p()
        try:
            # MFT_ENUM_FLAG_ALL sem FIELDOFUSE, com SORTANDFILTER (o que a documentação usa)
            mf.MFTranscodeGetAudioOutputAvailableTypes(byref(guid(MP3)), 0x77, None, byref(tipos))
            quantos = u32()
            metodo(tipos, 3, POINTER(u32))(tipos, byref(quantos))  # IMFCollection::GetElementCount
            for i in range(quantos.value):
                item, tipo = c_void_p(), c_void_p()
                try:
                    metodo(tipos, 4, u32, POINTER(c_void_p))(tipos, i, byref(item))  # GetElement
                    metodo(item, 0, POINTER(GUID), POINTER(c_void_p))(item, byref(guid(IID_TIPO)), byref(tipo))
                    if numero(tipo, HZ) == HZ_MP3 and numero(tipo, CANAIS) == 1:
                        d = abs(numero(tipo, BYTES_POR_SEGUNDO) - KBPS_MP3 * 125)
                        if distancia is None or d < distancia:
                            soltar(melhor)
                            melhor, distancia, tipo = tipo, d, None
                except OSError:  # um tipo sem o atributo: só não serve
                    pass
                finally:
                    soltar(tipo)
                    soltar(item)
        except OSError:
            log.warning("o Windows não listou os tipos de MP3", exc_info=True)
        finally:
            soltar(tipos)
        if melhor:
            log.info("MP3: tipo do codificador, %s bytes/s", numero(melhor, BYTES_POR_SEGUNDO))
            return melhor
        log.info("MP3: nenhum tipo listado em 44,1 kHz mono; tipo montado à mão")
        tipo = c_void_p()
        mfplat.MFCreateMediaType(byref(tipo))
        por_guid(tipo, TIPO, AUDIO)
        por_guid(tipo, SUBTIPO, MP3)
        por_numero(tipo, CANAIS, 1)
        por_numero(tipo, HZ, HZ_MP3)
        por_numero(tipo, BYTES_POR_SEGUNDO, KBPS_MP3 * 125)
        return tipo

    inicio = ctypes.windll.ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
    try:
        mfplat.MFStartup(0x00020070, 0)  # MF_VERSION, MFSTARTUP_FULL
        objetos = []
        try:
            saida = tipo_de_saida()
            objetos.append(saida)
            atributos = c_void_p()
            mfplat.MFCreateAttributes(byref(atributos), 1)
            objetos.append(atributos)
            por_guid(atributos, CONTEINER, CONTEINER_MP3)
            escritor = c_void_p()
            mfrw.MFCreateSinkWriterFromURL(c_wchar_p(str(destino)), None, atributos, byref(escritor))
            objetos.append(escritor)
            fluxo = u32()
            metodo(escritor, 3, c_void_p, POINTER(u32))(escritor, saida, byref(fluxo))  # AddStream
            entrada = c_void_p()
            mfplat.MFCreateMediaType(byref(entrada))
            objetos.append(entrada)
            por_guid(entrada, TIPO, AUDIO)
            por_guid(entrada, SUBTIPO, PCM)
            for chave, valor in ((CANAIS, 1), (HZ, HZ_MP3), (BITS, 16), (ALINHAMENTO, 2),
                                 (BYTES_POR_SEGUNDO, HZ_MP3 * 2), (INDEPENDENTES, 1)):
                por_numero(entrada, chave, valor)
            metodo(escritor, 4, u32, c_void_p, c_void_p)(escritor, fluxo.value, entrada, None)  # SetInputMediaType
            metodo(escritor, 5)(escritor)  # BeginWriting
            for dados, comeco, duracao in _blocos_pcm(origem):
                memoria, amostra = c_void_p(), c_void_p()
                try:
                    mfplat.MFCreateMemoryBuffer(len(dados), byref(memoria))
                    ponteiro = POINTER(ctypes.c_ubyte)()
                    metodo(memoria, 3, POINTER(POINTER(ctypes.c_ubyte)), POINTER(u32), POINTER(u32))(
                        memoria, byref(ponteiro), None, None)  # IMFMediaBuffer::Lock
                    ctypes.memmove(ponteiro, dados, len(dados))
                    metodo(memoria, 4)(memoria)  # Unlock
                    metodo(memoria, 6, u32)(memoria, len(dados))  # SetCurrentLength
                    mfplat.MFCreateSample(byref(amostra))
                    metodo(amostra, 42, c_void_p)(amostra, memoria)  # IMFSample::AddBuffer
                    metodo(amostra, 36, ctypes.c_longlong)(amostra, comeco)  # SetSampleTime
                    metodo(amostra, 38, ctypes.c_longlong)(amostra, duracao)  # SetSampleDuration
                    metodo(escritor, 6, u32, c_void_p)(escritor, fluxo.value, amostra)  # WriteSample
                finally:
                    soltar(amostra)
                    soltar(memoria)
            metodo(escritor, 11)(escritor)  # Finalize: fecha o .mp3
        finally:
            for obj in reversed(objetos):
                soltar(obj)
            mfplat.MFShutdown()
    finally:
        if inicio in (0, 1):  # S_OK / S_FALSE: quem abriu fecha
            ctypes.windll.ole32.CoUninitialize()


def mostrar(arquivo):
    """Abre o Explorador na pasta dos áudios com o arquivo selecionado."""
    import subprocess
    caminho = Path(arquivo)
    if caminho.parent != pasta() or caminho.suffix not in (".wav", ".mp3"):
        raise ValueError("Esse arquivo não é um áudio do Echo.")
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(caminho)])  # noqa: S603, S607
    else:
        subprocess.Popen(["xdg-open", str(caminho.parent)])  # noqa: S603, S607
