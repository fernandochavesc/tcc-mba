# Observação das praças

Instrumento da observação estruturada prevista na Metodologia do projeto de pesquisa: observação natural e
não disfarçada de leilões em ambiente eletrônico, com o que se observa e como se registra definidos de
antemão, sem interferir no certame. Serve ao objetivo específico (a), ao documentar a dinâmica do certame e
o resultado que nenhum anúncio informa.

Ficha e agenda: [`observacao-pracas.csv`](observacao-pracas.csv). Protocolo das rodadas de coleta:
[`registro-de-coleta.md`](registro-de-coleta.md).

## 1. Por que em tempo real

Na rodada de 02/11/2026, sete das oito páginas de lotes que saíram dos sites responderam erro HTTP 500, e a
restante exibia "Leilão Suspenso" (registro de coleta, seção 5). O desfecho não fica consultável depois do
certame: tem de ser registrado no dia da praça.

## 2. O que se registra

Uma linha por lote e por praça. As colunas de `data` a `lance_minimo` vêm da coleta; as demais são
preenchidas na observação.

| Coluna | Conteúdo |
|---|---|
| `data`, `hora` | data e hora da praça, como anunciadas |
| `id_lote` | identificador do lote no registro de coleta |
| `praca` | número da praça (1 ou 2) |
| `bairro`, `tipo`, `modalidade`, `leiloeiro`, `link` | como em `mapa/judicial.json` |
| `lance_minimo` | lance mínimo anunciado para a praça. Conferir no auditório; se divergir, registrar o valor observado e anotar o anunciado em `observacao` |
| `observado_em` | data e hora em que o desfecho foi visto (DD/MM/AAAA HH:MM) |
| `numero_lances` | quantidade de lances na praça. Contar, nunca copiar apelidos |
| `valor_final` | maior lance ao encerramento, em reais; vazio se não houve lance |
| `desfecho` | uma das três categorias do projeto: `arrematação`, `ausência de lances` ou `suspensão` |
| `observacao` | o que não couber nas colunas, como nova data anunciada ou divergência de valores |

O arquivo usa `;` como separador e vírgula decimal, para abrir direto no Numbers ou no Excel em português.

## 3. Regras

1. Observar sem interferir: o pesquisador não dá lances nem se manifesta no auditório.
2. Nenhum dado de pessoas. Não registrar apelido, nome ou cidade de licitantes, nem processo, vara ou partes.
   A ficha está em repositório público.
3. Capturas de tela ficam só no computador do pesquisador, na pasta
   `MBA/3-Coleta e Observação/Observação das praças/<data>/`, porque o auditório virtual exibe o apelido e a
   cidade de quem dá lance. Nunca entram neste repositório.
4. Lotes de modalidade `PGFN · Comprei` recebem lance no portal Comprei da PGFN, não no site do leiloeiro:
   observar lá.
5. Suspensão anunciada antes da data: registrar quando vista, com `desfecho` = `suspensão`.
6. Bem arrematado na 1ª praça: a linha da 2ª praça fica sem desfecho, com
   `não realizada: arrematado na 1ª praça` em `observacao`.

## 4. Agenda

Depois de cada rodada de coleta, com `mapa/judicial.json` já gerado:

```
python3 scripts/agenda_observacao.py
```

O script acrescenta as praças novas a partir da data do dia e nunca altera linhas existentes.

A agenda herda o recorte da coleta, de 32 sites e cinco bairros-alvo. Praças fora desse recorte não são
observadas.

Situação em 14/11/2026: 20 praças de 12 bens. Destas, 19 praças de 11 bens ocorrem entre 16/11 e
17/12/2026, e uma 2ª praça está marcada para 27/01/2027.
