#!/usr/bin/env python3
"""Gera mapa/judicial.json: mescla a coleta bruta (coleta_judicial.py) com a
extração assistida (extracao_manual.json), deduplica bens repetidos entre
leiloeiros e geocodifica os endereços individualmente (Nominatim, com cache).

Anúncios ainda sem extração entram no mapa pelo que o próprio anúncio informa:
- localização pelo endereço do anúncio, aceita só se o bairro devolvido pelo
  mapa-base for o bairro do anúncio; senão, centro do bairro (precisão "bairro");
- tipo e número de quartos lidos por regra no título, só quando escritos ali.
A área não é lida do título, porque ali ela é ambígua (privativa, total, por
andar). Os campos geo_precisao e dados_fonte dizem de onde veio cada coisa.

Uso:
  python3 scripts/gera_judicial.py <judicial_bruto.json>
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_EXTRACAO = RAIZ / "scripts" / "extracao_manual.json"
ARQ_SAIDA = RAIZ / "mapa" / "judicial.json"
ARQ_GEOCACHE = RAIZ / "mapa" / "geocache_judicial.json"
ARQ_CENTROIDES = RAIZ / "mapa" / "bairros.json"
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


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").upper().strip()


VIA = r"(?:Rua|R\.|Avenida|Av\.?|Travessa|Tv\.|Pra[çc]a|Praia|Largo|Estrada|Ladeira|Alameda|Rodovia)"


def rua_numero(endereco):
    """(logradouro, número) do endereço em texto livre do anúncio, ou None."""
    m = re.search(VIA + r"\s+([^,;\n\-–]+?)\s*(?:,|\s)\s*(?:n[º°o]\.?|n\.?|número)?\s*(\d{1,5})\b",
                  endereco or "", re.I)
    if not m:
        return None
    via = re.match(VIA, m.group(0), re.I).group(0)
    via = {"r.": "Rua", "av": "Avenida", "av.": "Avenida", "tv.": "Travessa"}.get(via.lower(), via)
    return f"{via} {m.group(1).strip()}", m.group(2)


def consulta(params):
    q = urllib.parse.urlencode({**params, "format": "json", "limit": 1, "addressdetails": 1, "countrycodes": "br"})
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())
    if not res:
        return {}
    ad = res[0].get("address", {})
    return {"latlng": [round(float(res[0]["lat"]), 6), round(float(res[0]["lon"]), 6)],
            "bairro": sem_acento(ad.get("suburb") or ad.get("neighbourhood") or ad.get("city_district")),
            "classe": res[0].get("class", "")}


def localiza_pelo_anuncio(lote, cache, centroides):
    """Coordenada e precisão ("número", "rua" ou "bairro") a partir do endereço do anúncio."""
    bairro = sem_acento(lote.get("bairro"))
    rn = rua_numero(lote.get("endereco", ""))
    if rn:
        rua, num = rn
        tentativas = [
            ("estruturada", {"street": f"{num} {rua}", "city": "Rio de Janeiro", "state": "RJ", "country": "Brasil"}),
            ("livre", {"q": f"{rua}, {num}, {(lote.get('bairro') or '').title()}, Rio de Janeiro, RJ"}),
        ]
        for modo, params in tentativas:
            chave = f"anuncio|{modo}|{rua}|{num}|{bairro}"
            if chave not in cache:
                try:
                    cache[chave] = consulta(params)
                except Exception as e:  # falha de rede não vai para o cache
                    print(f"  geocode falhou p/ {rua}, {num}: {e}", file=sys.stderr)
                    continue
                time.sleep(1.1)
            r = cache[chave]
            if r and r.get("bairro") == bairro:
                return r["latlng"], ("rua" if r.get("classe") == "highway" else "número")
    c = centroides.get(bairro)
    if not c and bairro:  # bairro fora da lista da Caixa: centro do bairro no mapa-base, com a mesma trava
        chave = f"bairro|{bairro}"
        if chave not in cache:
            try:
                cache[chave] = consulta({"q": f"{(lote.get('bairro') or '').title()}, Rio de Janeiro, RJ"})
                time.sleep(1.1)
            except Exception as e:
                print(f"  centro do bairro {bairro} falhou: {e}", file=sys.stderr)
        r = cache.get(chave)
        if r and r.get("bairro") == bairro:
            c = r["latlng"]
    return (c, "bairro") if c else (None, None)


TIPO_NO_TITULO = [
    (r"\b(apartamento|apto|cobertura|kitnet|conjugado|flat)\b", "Apartamento"),
    (r"\bsalas?\b", "Sala Comercial"),
    (r"\bcasas?\b", "Casa"),
    (r"\blojas?\b", "Loja"),
    (r"\bpr[ée]dios?\b", "Prédio"),
    (r"\bterrenos?\b", "Terreno"),
]


def dados_do_titulo(titulo):
    """Tipo e quartos escritos no título; None quando ausentes ou ambíguos. Nunca infere."""
    t = titulo or ""
    tipos = {nome for padrao, nome in TIPO_NO_TITULO if re.search(padrao, t, re.I)}
    quartos = {int(q) for q in re.findall(r"\b(\d{1,2})\s*(?:quartos?|dormit[óo]rios?)\b", t, re.I)}
    return (tipos.pop() if len(tipos) == 1 else None), (quartos.pop() if len(quartos) == 1 else None)


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
        if ext:
            lote["dados_fonte"] = "extração"
        else:
            tipo, quartos = dados_do_titulo(lote.get("titulo"))
            lote["tipo"] = lote.get("tipo") or tipo
            if lote.get("quartos") is None:
                lote["quartos"] = quartos
            lote["dados_fonte"] = "título do anúncio"
        # normaliza zeros da plataforma para "não informado"
        if not lote.get("valor_minimo"):
            lote["valor_minimo"] = None
        for r in lote.get("rodadas") or []:
            if not r.get("lance_minimo"):
                r["lance_minimo"] = None
        lote.pop("descricao", None)  # não precisa ir para o mapa
        lote.pop("status", None)
        # processo e vara ficam só na coleta bruta local (chave interna de consolidação);
        # o projeto promete que o número do processo nunca é divulgado.
        lote.pop("processo", None)
        lote.pop("vara", None)
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

    centroides = json.loads(ARQ_CENTROIDES.read_text()) if ARQ_CENTROIDES.exists() else {}
    for l in finais:
        if l.get("endereco_geo"):
            l["latlng"] = cache.get(l["endereco_geo"])
            l["geo_precisao"] = "conferida" if l["latlng"] else None
        else:
            l["latlng"], l["geo_precisao"] = localiza_pelo_anuncio(l, cache, centroides)
    ARQ_GEOCACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

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
