#!/usr/bin/env python3
"""Fotografa o mapa a partir dos arquivos locais do repositório, com o Chrome sem janela, e salva as imagens
fora do repositório, em "../Capturas do mapa/AAAA-MM-DD/" (pasta irmã do repositório na estrutura do MBA).

Duas vistas: a cidade inteira (lista da Caixa por bairro) e a Zona Sul alvo (lotes judiciais). Só o mapa
publicado é fotografado: páginas de lotes e editais não, porque exibem número do processo e nomes das partes.

Uso: python3 scripts/captura_mapa.py [pasta_de_saida]
"""
import socket
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VISTAS = [("mapa-cidade.png", "/mapa/"), ("mapa-zona-sul.png", "/mapa/?vista=zona-sul")]


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ.parent / "Capturas do mapa" / date.today().isoformat()
    if not Path(CHROME).exists():
        sys.exit(f"Chrome não encontrado em {CHROME}; capturas não feitas.")
    saida.mkdir(parents=True, exist_ok=True)
    porta = porta_livre()
    servidor = subprocess.Popen([sys.executable, "-m", "http.server", str(porta), "--bind", "127.0.0.1",
                                 "--directory", str(RAIZ)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", porta), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        with tempfile.TemporaryDirectory() as perfil:  # perfil descartável: não toca no Chrome do usuário
            for nome, caminho in VISTAS:
                subprocess.run([CHROME, "--headless=new", f"--user-data-dir={perfil}", "--no-first-run",
                                "--hide-scrollbars", "--window-size=1440,1000", "--virtual-time-budget=20000",
                                f"--screenshot={saida / nome}", f"http://127.0.0.1:{porta}{caminho}"],
                               check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"captura: {saida / nome}")
    finally:
        servidor.terminate()


if __name__ == "__main__":
    main()
