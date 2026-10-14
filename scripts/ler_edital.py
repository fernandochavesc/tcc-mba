#!/usr/bin/env python3
"""Extrai o texto de um edital em PDF, sem dependências externas.

Uso:
  python3 scripts/ler_edital.py <url_do_pdf> [regex]

Sem regex, imprime o começo do texto; com regex, imprime o entorno de cada
ocorrência. Serve para conferir na fonte o que o anúncio não traz: número de
quartos, matrícula do RGI, inscrição imobiliária e a regra da 2ª praça.

Os PDFs dos leiloeiros saem com uma letra por fragmento, então o texto é
remontado a partir dos literais entre parênteses dos streams Flate.
"""
import re
import sys
import urllib.request
import zlib


def texto(pdf: bytes) -> str:
    partes = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            partes.append(zlib.decompress(m.group(1)))
        except Exception:
            pass  # streams de imagem e fontes não interessam
    s = b"\n".join(partes).decode("latin1")
    t = " ".join(f[1:-1] for f in re.findall(r"\((?:[^()\\]|\\.)*\)", s))
    t = re.sub(r"\\([()\\])", r"\1", t)
    t = re.sub(r"(?<=\w) (?=\w\b)", "", t)  # junta as letras isoladas
    return re.sub(r"\s+", " ", t)


def baixa(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return texto(r.read())


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    t = baixa(sys.argv[1])
    if len(sys.argv) > 2:
        for m in re.finditer(sys.argv[2], t, re.I):
            print("…" + t[max(0, m.start() - 280) : m.start() + 340] + "…\n")
    else:
        print(t[:3500])


if __name__ == "__main__":
    main()
