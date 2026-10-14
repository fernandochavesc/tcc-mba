#!/usr/bin/env python3
"""Gera mapa/data.json a partir da lista oficial de imóveis da Caixa (RJ).

Uso:
  python3 scripts/atualiza_dados.py [caminho_do_csv]

Sem argumento, baixa a lista atual de
https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_RJ.csv

Centróides de bairro ficam em cache em mapa/bairros.json (geocodificados
via Nominatim/OpenStreetMap apenas quando surge bairro novo).
"""
import csv
import io
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_DADOS = RAIZ / "mapa" / "data.json"
ARQ_BAIRROS = RAIZ / "mapa" / "bairros.json"
URL_CSV = "https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_RJ.csv"
UA = "tcc-mba-mapa/0.1 (pesquisa academica; github.com/fernandochavesc/tcc-mba)"

# Bairros-alvo do caso de uso (Zona Sul)
ZONA_SUL_ALVO = ["BOTAFOGO", "FLAMENGO", "COPACABANA", "LARANJEIRAS"]

# Variantes de grafia na lista da Caixa → bairro canônico
ALIAS_BAIRRO = {
    "DISTRITO DO ANDARAI": "ANDARAI",
    "FREG CAMPO GRANDE": "CAMPO GRANDE",
    "FREG DE CAMPO GRANDE": "CAMPO GRANDE",
    "FREGUESIA DE GRANDE": "CAMPO GRANDE",
    "FREG DE GUARATIBA": "GUARATIBA",
    "FREGUESIA  GUARATIBA": "GUARATIBA",
    "FREG DE JACAREPAGUA": "JACAREPAGUA",
    "FRE DE CAMPO GRANDE": "CAMPO GRANDE",
    # Nossa Senhora da Ajuda é a freguesia histórica da Ilha do Governador
    # (conferido: Estrada do Dendê fica no Tauá/Moneró e a Rua Graná, no Cocotá).
    "NOSSA SRA DA AJUDA": "ILHA DO GOVERNADOR",
    "FREG N S D AJUDA": "ILHA DO GOVERNADOR",
    "FREG JACAREPAGUA": "JACAREPAGUA",
    "FREG DE SANTA CRUZ": "SANTA CRUZ",
    "FREGUE DE SANTA CRUZ": "SANTA CRUZ",
    "FREGUESIA DE CAMPO G": "CAMPO GRANDE",
    "FREG. DE SANTA CRUZ": "SANTA CRUZ",
    "FREGUESIA SANTA CRUZ": "SANTA CRUZ",
    "FREG DO ENGENHO NOVO": "ENGENHO NOVO",
    "FREGUESIA (ILHA DO GOVERNADOR)": "FREGUESIA ILHA DO GOVERNADOR",
}

# A lista traz alguns imóveis de outros municípios marcados como "RIO DE JANEIRO"
# na coluna cidade; o bairro denuncia a troca (conferido: a Estrada Velha de
# Santa Rita fica em Nova Iguaçu). Sem isso o imóvel vira uma bolha a 25 km da
# capital, fora do recorte do mapa.
FORA_DA_CAPITAL = {"NOVA IGUACU"}


def baixar_csv(tentativas: int = 4) -> str:
    """Baixa a lista da Caixa. O servidor recusa downloads em sequência, então
    tenta de novo com espera crescente antes de desistir."""
    erro = None
    for n in range(1, tentativas + 1):
        try:
            req = urllib.request.Request(URL_CSV, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                texto = r.read().decode("latin1")
            if "UF" in texto[:4000]:
                return texto
            erro = "resposta sem o cabeçalho esperado"
        except Exception as e:
            erro = e
        if n < tentativas:
            espera = 15 * n
            print(f"  tentativa {n} falhou ({erro}); nova tentativa em {espera}s…")
            time.sleep(espera)
    raise SystemExit(f"não foi possível baixar a lista da Caixa: {erro}")


def num_br(texto: str):
    texto = (texto or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def slug(bairro: str) -> str:
    s = unicodedata.normalize("NFD", bairro.strip().upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return ALIAS_BAIRRO.get(s, s)


def geocodificar_bairro(bairro: str):
    q = urllib.parse.quote(f"{bairro.title()}, Rio de Janeiro, RJ, Brasil")
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1&countrycodes=br"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
        if res:
            return [round(float(res[0]["lat"]), 5), round(float(res[0]["lon"]), 5)]
    except Exception as e:
        print(f"  geocode falhou p/ {bairro}: {e}", file=sys.stderr)
    return None


def main():
    if len(sys.argv) > 1:
        bruto = Path(sys.argv[1]).read_text(encoding="latin1")
        print(f"CSV local: {sys.argv[1]}")
    else:
        print("Baixando lista da Caixa…")
        bruto = baixar_csv()

    linhas = bruto.splitlines()
    # Acha a linha de cabeçalho (começa com "N° do imóvel")
    inicio = next((i for i, l in enumerate(linhas) if "imóvel" in l and "UF" in l), None)
    if inicio is None:
        raise SystemExit("CSV da Caixa sem linha de cabeçalho — download provavelmente truncado")
    data_geracao = ""
    m = re.search(r"(\d{2}/\d{2}/\d{4})", "\n".join(linhas[:inicio]))
    if m:
        data_geracao = m.group(1)

    leitor = csv.reader(io.StringIO("\n".join(linhas[inicio:])), delimiter=";")
    cab = next(leitor)

    imoveis = []
    for row in leitor:
        if len(row) < 12:
            continue
        _id, uf, cidade, bairro, endereco, preco, avaliacao, desconto, financ, desc, modalidade, link = (
            c.strip() for c in row[:12]
        )
        if slug(cidade) != "RIO DE JANEIRO" or slug(bairro) in FORA_DA_CAPITAL:
            continue
        mq = re.search(r"(\d+)\s*qto", desc)
        ma = re.search(r"([\d.]+)\s*de área privativa", desc)
        tipo = desc.split(",")[0].strip() if desc else ""
        imoveis.append(
            {
                "id": _id,
                "bairro": slug(bairro),
                "endereco": endereco,
                "preco": num_br(preco),
                "avaliacao": num_br(avaliacao),
                "desconto": num_br(desconto),
                "quartos": int(mq.group(1)) if mq else None,
                "area": float(ma.group(1)) if ma else None,
                "tipo": tipo,
                "modalidade": modalidade,
                "link": link,
            }
        )

    print(f"Imóveis na capital: {len(imoveis)}")

    # Centróides de bairro (cache + Nominatim para os novos)
    cache = json.loads(ARQ_BAIRROS.read_text()) if ARQ_BAIRROS.exists() else {}
    pendentes = sorted({im["bairro"] for im in imoveis} - set(cache))
    if pendentes:
        print(f"Geocodificando {len(pendentes)} bairros novos (Nominatim, 1 req/s)…")
        for i, b in enumerate(pendentes, 1):
            cache[b] = geocodificar_bairro(b)
            print(f"  [{i}/{len(pendentes)}] {b}: {cache[b]}")
            time.sleep(1.1)
        ARQ_BAIRROS.parent.mkdir(parents=True, exist_ok=True)
        ARQ_BAIRROS.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    saida = {
        "fonte": "Lista oficial de imóveis à venda da Caixa (RJ)",
        "url_fonte": URL_CSV,
        "data_geracao": data_geracao,
        "zona_sul_alvo": ZONA_SUL_ALVO,
        "imoveis": imoveis,
    }
    ARQ_DADOS.parent.mkdir(parents=True, exist_ok=True)
    ARQ_DADOS.write_text(json.dumps(saida, ensure_ascii=False))
    sem_geo = sorted({im["bairro"] for im in imoveis if not cache.get(im["bairro"])})
    print(f"OK → {ARQ_DADOS} ({len(imoveis)} imóveis, gerado em {data_geracao})")
    if sem_geo:
        print(f"Bairros sem centróide (aparecem só na lista): {', '.join(sem_geo)}")


if __name__ == "__main__":
    main()
