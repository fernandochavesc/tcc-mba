#!/usr/bin/env python3
"""Coleta lotes de leilão judicial de imóveis nos sites dos leiloeiros
credenciados do TJRJ (lista CGJ em scripts/leiloeiros.json) e filtra os
bairros-alvo (Zona Sul).

Plataformas suportadas: "suporteleiloes" e "lel.br" (as duas mais comuns na
lista CGJ). Sites em outras plataformas ficam registrados no inventário para
fases futuras.

Uso:
  python3 scripts/coleta_judicial.py [saida.json]

Sem dados pessoais de partes: o campo "Autor" das páginas NUNCA é coletado
(LGPD). A extração de quartos/área é feita em etapa posterior (LLM), registrada
em scripts/extracao_manual.json.
"""
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (pesquisa academica TCC; github.com/fernandochavesc/tcc-mba)"

CATEGORIAS_SUPORTE = ["Imóveis", "Apartamentos", "Casas", "Terreno", "Sala Comercial", "Rural"]
BAIRROS_ALVO = ["BOTAFOGO", "FLAMENGO", "COPACABANA", "LARANJEIRAS", "CATETE"]
# tokens de lugares reconhecíveis fora do alvo → permite pular a página de
# detalhe quando o slug já revela a localização (economia de requisições)
LUGARES_FORA = """
jacarepagua tijuca centro barra recreio taquara freguesia meier madureira bangu
campo-grande santa-cruz guaratiba realengo iraja penha olaria ramos bonsucesso
caju sao-cristovao gamboa lapa gloria santa-teresa vila-isabel grajau andarai
maracana engenho cachambi pilares abolicao piedade encantado quintino cascadura
marechal deodoro sepetiba paciencia cosmos inhoaiba pavuna anchieta guadalupe
ricardo-de-albuquerque costa-barros acari coelho-neto colegio iraja vicente
vila-da-penha cordovil braz-de-pina vista-alegre jardim-america itanhanga
gavea leblon ipanema lagoa jardim-botanico humaita urca cosme-velho vidigal
sao-conrado joa niteroi sao-goncalo caxias nova-iguacu belford mesquita
nilopolis queimados itaborai marica petropolis teresopolis friburgo cabo-frio
buzios arraial rio-das-ostras macae campos itaperuna resende volta-redonda
barra-mansa angra paraty mangaratiba itaguai seropedica japeri sao-joao-de-meriti
magalhaes-bastos vila-militar padre-miguel santissimo senador-camara vaz-lobo
""".split()
PAUSA = 1.0

MES_PT = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
          "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"}


def busca(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        # fallback: curl lida melhor com TLS antigo de alguns sites
        out = subprocess.run(
            ["curl", "-sL", "--max-time", "45", "-A", UA, url],
            capture_output=True, timeout=60,
        )
        if out.returncode != 0 or not out.stdout:
            raise RuntimeError(f"fetch falhou: {url}")
        return out.stdout.decode("utf-8", errors="replace")


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
    h = re.sub(r"<br ?/?>|</div>|</p>|</li>", "\n", h or "")
    h = re.sub(r"<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"[ \t]+", " ", h).strip()


def acha_bairro(*textos: str):
    for t in textos:  # ordem = prioridade (título > endereço > descrição)
        blob = sem_acento(t or "")
        for b in BAIRROS_ALVO:
            if b in blob:
                return b
    return None


def num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def num_br(texto):
    if not texto:
        return None
    return num(texto.strip().replace(".", "").replace(",", "."))


def slug_interessante(slug: str) -> bool:
    """Vale a pena baixar o detalhe? Sim se o slug cita um bairro-alvo, ou se
    não cita nenhum lugar conhecido (localização desconhecida)."""
    s = sem_acento(slug).lower().replace("_", "-")
    for alvo in BAIRROS_ALVO:
        if alvo.lower() in s.replace("-", ""):
            return True
    for fora in LUGARES_FORA:
        if fora in s:
            return False
    return True


# ---------------------------------------------------------------- suporteleiloes

def parse_lote_suporte(url, html, leiloeiro):
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
    medital = re.search(r'href="(https://static\.suporteleiloes\.com\.br/[^"]+\.pdf)"', html)
    foto = re.search(r"url\((https://static\.suporteleiloes\.com\.br/[^)]+)\)", html)

    rodadas = []
    if m1:
        rodadas.append({"n": 1, "data": m1.group(1), "hora": m1.group(2), "lance_minimo": num(lote.get("valorInicial"))})
    if m2:
        rodadas.append({"n": 2, "data": m2.group(1), "hora": m2.group(2), "lance_minimo": num(lote.get("valorInicial2"))})
    if not rodadas:
        prox = (leilao.get("dataProximoLeilao") or {}).get("date") if isinstance(leilao.get("dataProximoLeilao"), dict) else None
        if prox:
            data_iso, hora_iso = prox.split(" ")
            d, m, a = data_iso.split("-")[::-1]
            rodadas.append({"n": leilao.get("praca") or 1, "data": f"{d}/{m}/{a}", "hora": hora_iso[:5],
                            "lance_minimo": num(lote.get("valorInicial")) or num(lote.get("valorMinimo"))})

    return {
        "id": f"{sem_acento(leiloeiro).replace(' ', '')[:12]}-{lote.get('aid') or lote.get('bemId')}",
        "titulo": lote.get("titulo", ""),
        "endereco": endereco,
        "bairro": acha_bairro(lote.get("titulo", ""), endereco, descricao[:400]),
        "descricao": descricao[:1500],
        "quartos": None,
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
    }


def coleta_suporte(nome, base, todos, alvo):
    links = set()
    for cat in CATEGORIAS_SUPORTE:
        url = f"{base}/busca?tipo={urllib.parse.quote(cat)}"
        try:
            html = busca(url)
        except Exception as e:
            print(f"  busca {cat} falhou: {e}", file=sys.stderr)
            continue
        links.update(a.split("#")[0] for a in re.findall(r'href="(/oferta/[^"]+)"', html))
        time.sleep(PAUSA)
    uteis = [l for l in sorted(links) if slug_interessante(l.rsplit("/", 1)[-1])]
    print(f"  {nome}: {len(links)} lotes de imóveis, {len(uteis)} detalhes a baixar")
    for rel in uteis:
        url = base + rel
        try:
            registro = parse_lote_suporte(url, busca(url), nome)
        except Exception as e:
            print(f"    erro em {rel}: {e}", file=sys.stderr)
            registro = None
        if registro:
            todos.append(registro)
            if registro["bairro"]:
                alvo.append(registro)
                print(f"    ✓ ALVO {registro['bairro']}: {registro['titulo']} ({len(registro['rodadas'])} rodadas)")
        time.sleep(PAUSA)


# ---------------------------------------------------------------------- lel.br

def data_lel(texto):
    """'13 Ago, 2026 - 13:00' ou '13/08/2026 13:30:00' → (dd/mm/aaaa, hh:mm)"""
    if not texto:
        return None
    t = texto.strip()
    m = re.match(r"(\d{1,2})/(\d{2})/(\d{4})\s+(\d{2}:\d{2})", t)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}/{m.group(3)}", m.group(4)
    m = re.match(r"(\d{1,2})\s+(\w{3})\w*,?\s+(\d{4})\s*-\s*(\d{2}:\d{2})", t)
    if m and m.group(2).lower()[:3] in MES_PT:
        return f"{int(m.group(1)):02d}/{MES_PT[m.group(2).lower()[:3]]}/{m.group(3)}", m.group(4)
    return None


def coleta_lelbr(nome, base, todos, alvo):
    try:
        html = busca(f"{base}/browse.php?id=0")
    except Exception as e:
        print(f"  {nome}: browse falhou: {e}", file=sys.stderr)
        return
    itens = sorted(set(re.findall(r'item\.php\?id=(\d+)', html)))
    print(f"  {nome}: {len(itens)} itens")
    for iid in itens:
        url = f"{base}/item.php?id={iid}"
        try:
            src = busca(url)
        except Exception as e:
            print(f"    erro no item {iid}: {e}", file=sys.stderr)
            continue
        texto = texto_de_html(re.sub(r"<(script|style).*?</\1>", " ", src, flags=re.S))
        mtit = re.search(r"Categoria do artigo:.*?>\s*([^\n>]{3,80})\n", texto)
        titulo = (mtit.group(1).strip() if mtit else "").title() or "Imóvel"
        mdesc = re.search(r"Descrição do Item\s*\n(.*?)\n\s*informação adicional", texto, re.S | re.I)
        descricao = (mdesc.group(1).strip() if mdesc else "")[:1500]
        bairro = acha_bairro(titulo, descricao)
        if not bairro:
            time.sleep(PAUSA)
            continue
        d1 = data_lel((re.search(r"1° Leilão:\s*\n?\s*([^\n]+)", texto) or [None, None])[1])
        d2 = data_lel((re.search(r"2° Leilão:\s*\n?\s*([^\n]+)", texto) or [None, None])[1])
        v1 = num_br((re.search(r"(?:Oferta atual|Iniciando as Ofertas):\s*\n?\s*BRL\s*\n?\s*([\d.,]+)", texto) or [None, None])[1])
        v2 = num_br((re.search(r"Lançe Inicial:\s*\n?\s*BRL\s*\n?\s*([\d.,]+)", texto) or [None, None])[1])
        rodadas = []
        if d1:
            rodadas.append({"n": 1, "data": d1[0], "hora": d1[1], "lance_minimo": v1})
        if d2:
            rodadas.append({"n": 2, "data": d2[0], "hora": d2[1], "lance_minimo": v2})
        pdfs = [urllib.parse.urljoin(base + "/", h) for h in re.findall(r'href="([^"]+\.pdf)"', src, re.I)]
        edital = next((p for p in pdfs if "edital" in p.lower()), pdfs[0] if pdfs else None)
        registro = {
            "id": f"{sem_acento(nome).replace(' ', '')[:12]}-LEL{iid}",
            "titulo": titulo,
            "endereco": descricao.split("\n")[0][:160],
            "bairro": bairro,
            "descricao": descricao,
            "quartos": None,
            "avaliacao": v1,
            "valor_minimo": v2 or v1,
            "rodadas": rodadas,
            "modalidade": "Leilão Judicial",
            "status_leilao": None,
            "vara": None,
            "processo": None,
            "leiloeiro": nome,
            "link": url,
            "edital_url": edital,
            "foto": None,
        }
        todos.append(registro)
        alvo.append(registro)
        print(f"    ✓ ALVO {bairro}: {titulo} ({len(rodadas)} rodadas)")
        time.sleep(PAUSA)


# ------------------------------------------------------------------------ main

def main():
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("judicial_bruto.json")
    inventario = json.loads((RAIZ / "scripts" / "leiloeiros.json").read_text())
    todos, alvo = [], []
    for lei in inventario:
        plat, dom, nome = lei["plataforma"], lei["site"], lei["nome"]
        base = f"https://www.{dom}"
        if plat == "suporteleiloes":
            print(f"[suporteleiloes] {nome} ({dom})")
            coleta_suporte(nome, base, todos, alvo)
        elif plat == "lel.br":
            print(f"[lel.br] {nome} ({dom})")
            coleta_lelbr(nome, base, todos, alvo)
    dedup = {}
    for r in alvo:
        dedup[r["id"]] = r
    saida.write_text(json.dumps({"coletados": len(todos), "alvo": list(dedup.values())}, ensure_ascii=False, indent=1))
    print(f"\nTotal analisado: {len(todos)} lotes; na Zona Sul alvo: {len(dedup)} → {saida}")


if __name__ == "__main__":
    main()
