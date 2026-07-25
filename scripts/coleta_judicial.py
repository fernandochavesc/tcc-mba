#!/usr/bin/env python3
"""Coleta lotes de leilão judicial de imóveis nos sites de leiloeiros do TJRJ
(plataforma suporteleiloes: Portella, Rymer) e filtra os bairros-alvo (Zona Sul).

Uso:
  python3 scripts/coleta_judicial.py [saida.json]

Saída: JSON bruto com um registro por lote (sem dados pessoais de partes —
o campo "Autor" da página NUNCA é coletado, por desenho/LGPD). A extração de
quartos a partir da descrição é feita em etapa posterior (LLM).
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (pesquisa academica TCC; github.com/fernandochavesc/tcc-mba)"

LEILOEIROS = {
    "Portella Leilões": "https://www.portellaleiloes.com.br",
    "Rymer Leilões": "https://www.rymerleiloes.com.br",
}
CATEGORIAS = ["Imóveis", "Apartamentos", "Casas", "Terreno", "Sala Comercial", "Rural"]
BAIRROS_ALVO = ["BOTAFOGO", "FLAMENGO", "COPACABANA", "LARANJEIRAS", "CATETE"]
PAUSA = 1.2  # segundos entre requisições (educado com os sites)


def busca(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


def sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFD", s.upper())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def json_da_var(src: str, nome: str):
    i = src.find(f"var {nome} = {{")
    if i < 0:
        return None
    s = src[i + len(f"var {nome} = "):]
    prof = 0
    em_str = esc = False
    for j, ch in enumerate(s):
        if em_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                em_str = False
        else:
            if ch == '"':
                em_str = True
            elif ch == "{":
                prof += 1
            elif ch == "}":
                prof -= 1
                if prof == 0:
                    try:
                        return json.loads(s[: j + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def texto_de_html(h: str) -> str:
    h = re.sub(r"<br ?/?>|</div>|</p>", "\n", h or "")
    h = re.sub(r"<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"[ \t]+", " ", h).strip()


def acha_bairro(*textos: str):
    for t in textos:  # ordem dos argumentos = prioridade (título > endereço > descrição)
        blob = sem_acento(t or "")
        for b in BAIRROS_ALVO:
            if b in blob:
                return b
    return None


def parse_lote(url: str, html: str, leiloeiro: str):
    lote = json_da_var(html, "lote")
    if not lote:
        return None
    leilao = json_da_var(html, "leilao") or {}
    descricao = texto_de_html(lote.get("descricao", ""))
    endereco = descricao.split("\n")[0].strip() if descricao else ""
    m1 = re.search(r"Primeiro leil[ãa]o\s*</div>.{0,200}?(\d{2}/\d{2}/\d{4}) - (\d{2}:\d{2})", html, re.S)
    m2 = re.search(r"Segundo leil[ãa]o\s*</div>.{0,200}?(\d{2}/\d{2}/\d{4}) - (\d{2}:\d{2})", html, re.S)
    mvara = re.search(r"<strong>Cart[óo]rio:</strong>\s*([^<]+)", html)
    mproc = re.search(r'id="processo" value="(\d+)"', html)
    medital = re.search(r'href="(https://static\.suporteleiloes\.com\.br/[^"]+\.pdf)"[^>]*>[^<]*<i[^>]*></i>\s*<small[^>]*>Edital', html)
    if not medital:
        medital = re.search(r'href="(https://static\.suporteleiloes\.com\.br/[^"]+\.pdf)"', html)
    foto = re.search(r'url\((https://static\.suporteleiloes\.com\.br/[^)]+)\)', html)

    def num(v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    rodadas = []
    if m1:
        rodadas.append({"n": 1, "data": m1.group(1), "hora": m1.group(2), "lance_minimo": num(lote.get("valorInicial"))})
    if m2:
        rodadas.append({"n": 2, "data": m2.group(1), "hora": m2.group(2), "lance_minimo": num(lote.get("valorInicial2"))})
    if not rodadas:
        # fallback (template Rymer): data da próxima praça no JSON do leilão
        prox = (leilao.get("dataProximoLeilao") or {}).get("date")
        if prox:
            data_iso, hora_iso = prox.split(" ")
            d, m, a = data_iso.split("-")[::-1]
            rodadas.append({
                "n": leilao.get("praca") or 1,
                "data": f"{d}/{m}/{a}",
                "hora": hora_iso[:5],
                "lance_minimo": num(lote.get("valorInicial")) or num(lote.get("valorMinimo")),
            })

    return {
        "id": f"{sem_acento(leiloeiro).split()[0]}-{lote.get('aid') or lote.get('bemId')}",
        "titulo": lote.get("titulo", ""),
        "endereco": endereco,
        "bairro": acha_bairro(lote.get("titulo", ""), endereco, descricao[:400]),
        "descricao": descricao[:1500],
        "quartos": None,  # preenchido na etapa de extração (LLM)
        "avaliacao": num(lote.get("valorAvaliacao")),
        "valor_minimo": num(lote.get("valorMinimo")),
        "rodadas": rodadas,
        "modalidade": ("Judicial · Venda Direta" if leilao.get("vendaDireta") else "Leilão Judicial")
                      if leilao.get("judicial", True) else "Leilão Extrajudicial",
        "status_leilao": leilao.get("statusString"),
        "vara": mvara.group(1).strip() if mvara else None,
        "processo": mproc.group(1) if mproc else None,
        "leiloeiro": leiloeiro,
        "link": url,
        "edital_url": medital.group(1) if medital else None,
        "foto": foto.group(1) if foto else None,
        "status": lote.get("status"),
    }


def main():
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("judicial_bruto.json")
    todos, alvo = [], []
    for leiloeiro, base in LEILOEIROS.items():
        links = set()
        for cat in CATEGORIAS:
            url = f"{base}/busca?tipo={urllib.parse.quote(cat)}"
            try:
                html = busca(url)
            except Exception as e:
                print(f"  busca {cat} falhou: {e}", file=sys.stderr)
                continue
            achados = re.findall(r'href="(/oferta/[^"]+)"', html)
            links.update(a.split('#')[0] for a in achados)
            time.sleep(PAUSA)
        print(f"{leiloeiro}: {len(links)} lotes de imóveis")
        for i, rel in enumerate(sorted(links), 1):
            url = base + rel
            try:
                html = busca(url)
                registro = parse_lote(url, html, leiloeiro)
            except Exception as e:
                print(f"  [{i}] erro em {rel}: {e}", file=sys.stderr)
                registro = None
            if registro:
                todos.append(registro)
                if registro["bairro"]:
                    alvo.append(registro)
                    print(f"  ✓ ALVO {registro['bairro']}: {registro['titulo']} ({len(registro['rodadas'])} rodadas)")
            time.sleep(PAUSA)

    saida.write_text(json.dumps({"coletados": len(todos), "alvo": alvo, "todos_bairros": sorted({t['bairro'] or '?' for t in todos})}, ensure_ascii=False, indent=1))
    print(f"\nTotal coletado: {len(todos)} lotes; na Zona Sul alvo: {len(alvo)} → {saida}")


if __name__ == "__main__":
    main()
