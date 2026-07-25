#!/usr/bin/env python3
"""Gera mapa/judicial.json: mescla a coleta bruta (coleta_judicial.py) com a
extração assistida (extracao_manual.json), deduplica bens repetidos entre
leiloeiros e geocodifica os endereços individualmente (Nominatim, com cache).

Uso:
  python3 scripts/gera_judicial.py <judicial_bruto.json>
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_EXTRACAO = RAIZ / "scripts" / "extracao_manual.json"
ARQ_SAIDA = RAIZ / "mapa" / "judicial.json"
ARQ_GEOCACHE = RAIZ / "mapa" / "geocache_judicial.json"
UA = "tcc-mba-mapa/0.1 (pesquisa academica; github.com/fernandochavesc/tcc-mba)"


def geocodifica(endereco: str):
    q = urllib.parse.quote(endereco)
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1&countrycodes=br"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
        if res:
            return [round(float(res[0]["lat"]), 6), round(float(res[0]["lon"]), 6)]
    except Exception as e:
        print(f"  geocode falhou p/ {endereco}: {e}", file=sys.stderr)
    return None


def main():
    bruto = json.loads(Path(sys.argv[1]).read_text())
    extracao = json.loads(ARQ_EXTRACAO.read_text())
    cache = json.loads(ARQ_GEOCACHE.read_text()) if ARQ_GEOCACHE.exists() else {}

    lotes = {l["id"]: l for l in bruto["alvo"]}

    # dedupe entre leiloeiros: merge_em aponta para o registro canônico
    finais = []
    for lid, lote in lotes.items():
        ext = extracao.get(lid, {})
        if ext.get("merge_em"):
            canonico = lotes.get(ext["merge_em"])
            if canonico is not None:
                canonico.setdefault("fontes_extras", []).append(
                    {"leiloeiro": lote["leiloeiro"], "link": lote["link"]}
                )
            continue
        for campo in ("tipo", "area", "quartos", "modalidade", "endereco_geo", "link_lances",
                      "rodadas", "endereco", "titulo", "edital_url", "valor_minimo"):
            if campo in ext:
                lote[campo] = ext[campo]
        # normaliza zeros da plataforma para "não informado"
        if not lote.get("valor_minimo"):
            lote["valor_minimo"] = None
        for r in lote.get("rodadas") or []:
            if not r.get("lance_minimo"):
                r["lance_minimo"] = None
        lote.pop("descricao", None)  # não precisa ir para o mapa
        lote.pop("status", None)
        finais.append(lote)

    # geocodificação individual (com cache)
    pendentes = [l for l in finais if l.get("endereco_geo") and l["endereco_geo"] not in cache]
    if pendentes:
        print(f"Geocodificando {len(pendentes)} endereços (Nominatim, 1 req/s)…")
        for l in pendentes:
            cache[l["endereco_geo"]] = geocodifica(l["endereco_geo"])
            print(f"  {l['endereco_geo']}: {cache[l['endereco_geo']]}")
            time.sleep(1.1)
        ARQ_GEOCACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    for l in finais:
        l["latlng"] = cache.get(l.get("endereco_geo", ""), None)

    saida = {
        "fonte": "Leiloeiros credenciados TJRJ (Portella, Rymer) — coleta própria",
        "gerado_em": bruto.get("gerado_em", ""),
        "lotes": finais,
    }
    ARQ_SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1))
    sem_geo = [l["id"] for l in finais if not l["latlng"]]
    print(f"OK → {ARQ_SAIDA} ({len(finais)} lotes; sem coordenada: {sem_geo or 'nenhum'})")


if __name__ == "__main__":
    main()
