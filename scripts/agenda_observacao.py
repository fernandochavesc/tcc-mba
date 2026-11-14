# -*- coding: utf-8 -*-
"""Mantém a agenda/ficha de observação das praças (docs/observacao-pracas.csv).

Lê mapa/judicial.json e acrescenta uma linha por (lote, praça) com data a partir de --desde
(padrão: hoje). Nunca altera nem apaga linhas que já existem: as colunas preenchidas na
observação ficam intactas. Rodar depois de cada rodada de coleta (após gera_judicial.py).

O arquivo usa ';' como separador e vírgula decimal, para abrir direto no Numbers/Excel em
português. Não contém processo, vara nem qualquer dado de pessoas.

Uso: python3 scripts/agenda_observacao.py [--desde DD/MM/AAAA]
"""
import csv, json, sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "mapa" / "judicial.json"
FICHA = RAIZ / "docs" / "observacao-pracas.csv"

COLUNAS = ["data", "hora", "id_lote", "praca", "bairro", "tipo", "modalidade", "leiloeiro", "link",
           "lance_minimo",                                   # vem da coleta; conferir no dia
           "observado_em", "numero_lances", "valor_final", "desfecho", "observacao"]  # preencher na praça

def para_data(s):
    d, m, a = map(int, s.split("/"))
    return date(a, m, d)

def reais(v):
    return "" if v is None else f"{v:.2f}".replace(".", ",")

def main():
    desde = date.today()
    if "--desde" in sys.argv:
        desde = para_data(sys.argv[sys.argv.index("--desde") + 1])
    existentes = []
    if FICHA.exists():
        with FICHA.open(encoding="utf-8", newline="") as f:
            existentes = list(csv.DictReader(f, delimiter=";"))
    chaves = {(r["id_lote"], r["praca"]) for r in existentes}

    novas = []
    for l in json.loads(FONTE.read_text(encoding="utf-8"))["lotes"]:
        for r in l.get("rodadas") or []:
            if not r.get("data") or para_data(r["data"]) < desde:
                continue
            chave = (l["id"], str(r["n"]))
            if chave in chaves:
                continue
            novas.append({
                "data": r["data"], "hora": r.get("hora") or "", "id_lote": l["id"], "praca": str(r["n"]),
                "bairro": (l.get("bairro") or "").title(), "tipo": l.get("tipo") or "",
                "modalidade": l.get("modalidade") or "", "leiloeiro": l.get("leiloeiro") or "",
                "link": l.get("link") or "", "lance_minimo": reais(r.get("lance_minimo")),
            })
            chaves.add(chave)

    linhas = existentes + novas
    linhas.sort(key=lambda r: (para_data(r["data"]), r.get("hora", ""), r["id_lote"], r["praca"]))
    FICHA.parent.mkdir(exist_ok=True)
    with FICHA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in linhas:
            w.writerow({c: r.get(c, "") for c in COLUNAS})
    print(f"{len(novas)} praça(s) nova(s) na agenda; {len(linhas)} no total -> {FICHA.relative_to(RAIZ)}")

if __name__ == "__main__":
    main()
