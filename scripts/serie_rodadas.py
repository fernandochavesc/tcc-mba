#!/usr/bin/env python3
"""Reconstrói a série das rodadas de coleta a partir do histórico do git e dos
arquivos atuais, e reescreve as tabelas de docs/registro-de-coleta.md entre os
marcadores <!-- serie:inicio --> e <!-- serie:fim -->.

Uso:
  python3 scripts/serie_rodadas.py            # imprime as tabelas (Markdown)
  python3 scripts/serie_rodadas.py --escreve  # também atualiza o registro

Cada rodada é um commit em que mapa/data.json (lista da Caixa) e/ou
mapa/judicial.json (coleta nos sites dos leiloeiros) foram atualizados; a
entrada "HEAD+" representa a árvore de trabalho ainda não commitada. As
definições das métricas estão no próprio registro (seção 3).
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "docs" / "registro-de-coleta.md"

# (ref do git, data da coleta nos sites dos leiloeiros, observação)
# A data da lista da Caixa vem do próprio data.json (data_geracao).
RODADAS = [
    ("ab4be3e", "25/07/2026", "primeira coleta: 25 dos 77 sites (adaptadores suporteleiloes e lel.br)"),
    ("f562264", "08/08/2026", "cobertura ampliada para 32 sites (adaptador vlance)"),
    ("14daee7", "27/08/2026", ""),
    ("0186be2", "04/10/2026", "coletor corrigido: 2ª praça voltou a ser lida"),
    ("9fbd383", "14/10/2026", ""),
    ("HEAD+", "02/11/2026", "quinta rodada; registro de coleta iniciado"),
]

ALVO = {"BOTAFOGO", "FLAMENGO", "COPACABANA", "LARANJEIRAS"}
ZONA_SUL = ALVO | {"CATETE", "GLORIA", "URCA", "LEME", "IPANEMA", "LEBLON", "LAGOA", "JARDIM BOTANICO",
                   "GAVEA", "HUMAITA", "SAO CONRADO", "VIDIGAL", "COSME VELHO", "SANTA TERESA"}
RESIDENCIAL = {"apartamento", "casa", "cobertura", "kitnet", "conjugado"}


def carrega(ref: str, caminho: str):
    if ref == "HEAD+":
        return json.loads((RAIZ / caminho).read_text())
    out = subprocess.run(["git", "show", f"{ref}:{caminho}"], cwd=RAIZ, capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else None


def fmt(n):
    return f"{n:,}".replace(",", ".")


def pct(a, b):
    return f"{a / b:.0%}" if b else "—"


def serie_caixa():
    linhas = []
    anterior = None
    vistos = set()
    for ref, _, _ in RODADAS:
        d = carrega(ref, "mapa/data.json")
        if d is None:
            continue
        atual = {x["id"]: x for x in d["imoveis"]}
        if anterior is not None and d["data_geracao"] == anterior[0]:
            continue  # mesma lista da Caixa em dois commits
        bairros = Counter(x["bairro"] for x in atual.values())
        zs = sum(v for b, v in bairros.items() if b in ZONA_SUL)
        alvo = sum(v for b, v in bairros.items() if b in ALVO)
        sem_q = sum(1 for x in atual.values() if not x.get("quartos"))
        if anterior is None:
            sairam = entraram = relist = None
        else:
            ant = anterior[1]
            sairam = len(set(ant) - set(atual))
            ent = set(atual) - set(ant)
            entraram = len(ent)
            relist = len(ent & vistos)
        vistos |= set(atual)
        linhas.append({
            "lista": d["data_geracao"], "total": len(atual), "zona_sul": zs, "alvo": alvo,
            "sem_quartos": sem_q, "sairam": sairam, "entraram": entraram, "relist": relist,
            "anterior": len(anterior[1]) if anterior else None,
            "top": bairros.most_common(1)[0],
        })
        anterior = (d["data_geracao"], atual)
    md = ["| Lista da Caixa | Imóveis na capital | Zona Sul | 4 bairros-alvo | Sem nº de quartos | Saíram desde a lista anterior | Entraram | Entradas que são relistagem | Bairro com mais imóveis |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for l in linhas:
        s = f"{fmt(l['sairam'])} ({pct(l['sairam'], l['anterior'])})" if l["sairam"] is not None else "—"
        e = fmt(l["entraram"]) if l["entraram"] is not None else "—"
        r = f"{fmt(l['relist'])} ({pct(l['relist'], l['entraram'])})" if l["relist"] is not None else "—"
        md.append(f"| {l['lista']} | {fmt(l['total'])} | {l['zona_sul']} | {l['alvo']} | {fmt(l['sem_quartos'])} ({pct(l['sem_quartos'], l['total'])}) | {s} | {e} | {r} | {l['top'][0].title()} ({fmt(l['top'][1])}) |")
    return "\n".join(md)


def serie_judicial():
    md = ["| Coleta nos sites | Sites cobertos | Anúncios na Zona Sul | Bens distintos (após dedupe) | Botafogo / Copacabana / Flamengo / Laranjeiras / Catete | Com 2ª praça | 2ª praça a 50% | Residenciais com nº de quartos | Observação |",
          "|---|---:|---:|---:|---|---:|---:|---|---|"]
    for ref, data, obs in RODADAS:
        j = carrega(ref, "mapa/judicial.json")
        if j is None:
            continue
        lotes = j["lotes"]
        extras = sum(len(l.get("fontes_extras") or []) for l in lotes)
        b = Counter(l["bairro"] for l in lotes)
        com2 = [l for l in lotes if len(l.get("rodadas") or []) >= 2]
        meio = sum(1 for l in com2 if l["rodadas"][0].get("lance_minimo") and l["rodadas"][1].get("lance_minimo")
                   and abs(l["rodadas"][1]["lance_minimo"] / l["rodadas"][0]["lance_minimo"] - 0.5) < 0.01)
        res = [l for l in lotes if (l.get("tipo") or "").lower() in RESIDENCIAL]
        qk = sum(1 for l in res if l.get("quartos") is not None)
        sites = 25 if ref == "ab4be3e" else 32
        dist = " / ".join(str(b.get(k, 0)) for k in ("BOTAFOGO", "COPACABANA", "FLAMENGO", "LARANJEIRAS", "CATETE"))
        md.append(f"| {data} | {sites} | {len(lotes) + extras} | {len(lotes)} | {dist} | {len(com2)} | {meio} | {qk} de {len(res)} | {obs} |")
    return "\n".join(md)


def main():
    bloco = "\n".join([
        "**Tabela 1 – Lista de imóveis da Caixa Econômica Federal, município do Rio de Janeiro, por data da lista**", "",
        serie_caixa(), "",
        "**Tabela 2 – Coleta nos sites dos leiloeiros credenciados (lotes judiciais nos bairros-alvo), por data da coleta**", "",
        serie_judicial(), "",
        "_Tabelas geradas por `scripts/serie_rodadas.py` a partir do histórico do repositório; não editar à mão._",
    ])
    print(bloco)
    if "--escreve" in sys.argv and REGISTRO.exists():
        txt = REGISTRO.read_text()
        novo = re.sub(r"<!-- serie:inicio -->.*?<!-- serie:fim -->",
                      lambda m: "<!-- serie:inicio -->\n" + bloco + "\n<!-- serie:fim -->", txt, flags=re.S)
        REGISTRO.write_text(novo)
        print(f"\nOK → {REGISTRO.relative_to(RAIZ)} atualizado", file=sys.stderr)


if __name__ == "__main__":
    main()
