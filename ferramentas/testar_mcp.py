"""Sobe o app/mcp_server.py por stdio, como o Claude Desktop faria, e chama as ferramentas.

Uso: app/.venv/bin/python -I ferramentas/testar_mcp.py [caminho de um dados.db de teste]
"""
import asyncio
import os
import sys
from pathlib import Path

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

APP = Path(__file__).resolve().parent.parent / "app"
DADOS = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "frases-teste-mcp.db")


def texto(resultado):
    return "\n".join(c.text for c in resultado.content if getattr(c, "text", None))


async def main():
    params = StdioServerParameters(
        command=str(APP / ".venv/bin/python"), args=[str(APP / "mcp_server.py")],
        env={**os.environ, "FRASES_DADOS": DADOS})
    async with stdio_client(params) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as s:
            init = await s.initialize()
            print("servidor:", init.server_info.name, "| instruções:", len(init.instructions or ""), "caracteres")
            ferramentas = (await s.list_tools()).tools
            print("ferramentas:", ", ".join(t.name for t in ferramentas), "\n")

            async def chamar(_ferramenta, **args):
                r = await s.call_tool(_ferramenta, args)
                print(f">>> {_ferramenta}({args}){'  [ERRO]' if r.is_error else ''}\n{texto(r)}\n")
                return texto(r)

            await chamar("listar_obras")
            await chamar("listar_estruturas")
            saida = await chamar("buscar", estrutura="third conditional", obras=["Friends"], quantidade=2)
            frase_id = int(saida.split("frase_id ")[1].split()[0])
            await chamar("buscar", estrutura="Used to", personagem="Sheldon", quantidade=1, semente=4)
            await chamar("testar_padrao", padrao="[l=wish] [t=PRP|NNP] [w=would|'d] [t=VB]", quantidade=2)
            await chamar("cadastrar_estrutura", nome="Wish + would", explicacao="Irritação ou desejo de que alguém mude: wish + would.",
                         formula="wish + sujeito + would + verbo", padrao="[l=wish] [t=PRP|NNP] [w=would|'d] [t=VB]",
                         categoria="Desejos", nivel="B2", exemplos=["I wish you would stop."])
            await chamar("editar_estrutura", nome="Wish + would", pegadinhas="Não use com o próprio sujeito: *I wish I would.")
            await chamar("favoritar", frase_id=frase_id, estrutura="Third conditional", nota="bom exemplo")
            await chamar("listar_favoritos")
            await chamar("marcar_falso_positivo", estrutura="Third conditional", frase_id=frase_id)
            await chamar("buscar", estrutura="third conditional", obras=["Friends"], quantidade=0)
            await chamar("buscar", estrutura="não existe")
            await chamar("testar_padrao", padrao="[x=1]")


asyncio.run(main())
