#!/usr/bin/env python3
"""Executa a parte mecânica de uma rodada de coleta (registro de coleta, seção 3.1, passos 1, 2, 4 e 5),
atualiza a agenda de observação das praças e acrescenta à seção 5 do registro um bloco só com os números.

Não lê editais nem faz extração por modelo de linguagem: o passo 3 segue o protocolo de extração do projeto
(anonimização antes de qualquer processamento) e é feito à parte. Anúncios novos entram nos totais com os campos
do coletor e ficam fora do mapa até a extração, porque a coordenada depende do endereço normalizado;
eles são listados no resumo. Não faz commit.

Uso: python3 scripts/rodada.py [--data DD/MM/AAAA]

Saída: 0 = rodada concluída; 2 = árvore com alterações não commitadas (nada foi feito);
3 = coleta suspeita (totais zerados ou queda acima de 50%): conferir antes de publicar.
"""
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "docs" / "registro-de-coleta.md"
SERIE = RAIZ / "scripts" / "serie_rodadas.py"
BRUTO = RAIZ / "judicial_bruto.json"


def roda(*args):
    print(f"\n$ {' '.join(args)}", flush=True)
    subprocess.run(args, cwd=RAIZ, check=True)


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()


def fmt(n):
    return f"{n:,}".replace(",", ".")


def le(caminho):
    p = RAIZ / caminho
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def atualiza_lista_rodadas(data):
    """Fixa a rodada anterior no commit dela e abre a nova como HEAD+ (árvore de trabalho)."""
    txt = SERIE.read_text(encoding="utf-8")
    m = re.search(r'    \("HEAD\+", "(\d\d/\d\d/\d{4})", "([^"]*)"\),\n', txt)
    if not m:
        sys.exit("serie_rodadas.py: entrada HEAD+ não encontrada em RODADAS")
    if m.group(1) == data:
        print(f"RODADAS já tem a rodada de {data}; lista mantida.")
        return
    sha, quando = git("log", "-1", "--format=%h %cs", "--grep=^Atualiza dados:").split()
    if datetime.strptime(quando, "%Y-%m-%d").strftime("%d/%m/%Y") != m.group(1):
        sys.exit(f"serie_rodadas.py: a entrada HEAD+ ({m.group(1)}) não corresponde ao último commit de rodada "
                 f"({sha}, {quando}). Corrigir RODADAS à mão.")
    fixa = f'    ("{sha}", "{m.group(1)}", "{m.group(2)}"),\n'
    nova = f'    ("HEAD+", "{data}", ""),\n'
    SERIE.write_text(txt[:m.start()] + fixa + nova + txt[m.end():], encoding="utf-8")
    print(f"RODADAS: {m.group(1)} fixada em {sha}; {data} aberta como HEAD+.")


def registra_numeros(data, caixa, bruto, bens, novos):
    """Acrescenta à seção 5 do registro um bloco factual da rodada, uma única vez por data."""
    txt = REGISTRO.read_text(encoding="utf-8")
    titulo = f"### {data} – rodada automática (lista da Caixa de {caixa['data_geracao']})"
    if titulo in txt:
        print("Seção 5 já tem o bloco desta rodada.")
        return
    linhas = [titulo, "",
              f"- Caixa: lista de {caixa['data_geracao']}, {fmt(len(caixa['imoveis']))} imóveis na capital.",
              f"- Leiloeiros: {bruto['coletados']} anúncios analisados nos sites cobertos, {len(bruto['alvo'])} nos "
              f"bairros-alvo, {bens} bens após a deduplicação.",
              (f"- Anúncios novos ainda sem extração: {len(novos)} ({', '.join(novos)}). Contam nos totais, mas ficam "
               "fora do mapa até a extração pelo protocolo do projeto, que fornece o endereço normalizado usado "
               "na geocodificação." if novos else
               "- Nenhum anúncio novo sem extração."),
              "- Registro gerado por `scripts/rodada.py`; os achados desta rodada ainda não foram redigidos.", "", ""]
    corte = txt.index("## 6.")
    REGISTRO.write_text(txt[:corte] + "\n".join(linhas) + txt[corte:], encoding="utf-8")
    print("Seção 5: bloco factual da rodada acrescentado.")


def main():
    data = date.today().strftime("%d/%m/%Y")
    if "--data" in sys.argv:
        data = sys.argv[sys.argv.index("--data") + 1]

    if git("status", "--porcelain", "--untracked-files=no"):
        print("Há alterações não commitadas no repositório. Nada foi feito.")
        sys.exit(2)

    antes_caixa = le("mapa/data.json")
    antes_bruto = json.loads(BRUTO.read_text(encoding="utf-8")) if BRUTO.exists() else None

    roda(sys.executable, "scripts/atualiza_dados.py")
    roda(sys.executable, "scripts/coleta_judicial.py", BRUTO.name)

    caixa = le("mapa/data.json")
    bruto = json.loads(BRUTO.read_text(encoding="utf-8"))
    alertas = []
    if not caixa["imoveis"]:
        alertas.append("lista da Caixa veio vazia")
    elif antes_caixa and len(caixa["imoveis"]) < 0.5 * len(antes_caixa["imoveis"]):
        alertas.append(f"Caixa caiu de {len(antes_caixa['imoveis'])} para {len(caixa['imoveis'])} imóveis")
    if not bruto.get("coletados"):
        alertas.append("nenhum anúncio coletado nos sites dos leiloeiros")
    elif antes_bruto and bruto["coletados"] < 0.5 * antes_bruto.get("coletados", 0):
        alertas.append(f"anúncios analisados caíram de {antes_bruto['coletados']} para {bruto['coletados']}")
    if alertas:
        print("\nCOLETA SUSPEITA: " + "; ".join(alertas) + ". Conferir antes de publicar.")
        sys.exit(3)

    extracao = le("scripts/extracao_manual.json") or {}
    novos = sorted(l["id"] for l in bruto["alvo"] if l["id"] not in extracao)

    roda(sys.executable, "scripts/gera_judicial.py", BRUTO.name)
    judicial = le("mapa/judicial.json")
    bens = len(judicial["lotes"])

    atualiza_lista_rodadas(data)
    roda(sys.executable, "scripts/serie_rodadas.py", "--escreve")
    roda(sys.executable, "scripts/agenda_observacao.py")
    registra_numeros(data, caixa, bruto, bens, novos)

    sem_geo = [l["id"] for l in judicial["lotes"] if not l.get("latlng")]
    print("\n=== RESUMO DA RODADA ===")
    print(f"Data da rodada: {data}")
    ant = f" (rodada anterior: {fmt(len(antes_caixa['imoveis']))})" if antes_caixa else ""
    print(f"Caixa: lista de {caixa['data_geracao']}, {fmt(len(caixa['imoveis']))} imóveis na capital{ant}")
    print(f"Leiloeiros: {bruto['coletados']} anúncios analisados, {len(bruto['alvo'])} nos bairros-alvo, "
          f"{bens} bens após deduplicação")
    print(f"Anúncios novos sem extração: {len(novos)}")
    for i in novos:
        lote = next(l for l in bruto["alvo"] if l["id"] == i)
        print(f"  {i}  {lote.get('link', '')}")
    print(f"Lotes sem coordenada no mapa: {', '.join(sem_geo) or 'nenhum'}")
    print(f"MENSAGEM DE COMMIT: Atualiza dados: Caixa {caixa['data_geracao'][:5]} "
          f"({fmt(len(caixa['imoveis']))}) e {bens} lotes judiciais na Zona Sul")


if __name__ == "__main__":
    main()
