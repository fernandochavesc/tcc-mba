# Registro da coleta documental automatizada

Pesquisa: *Agregador de leilões de imóveis no Rio de Janeiro: coleta automatizada e percepção do mercado* (TCC, MBA em Gestão de Negócios Digitais e Inteligência Artificial, USP/Esalq). Autor: Fernando Chaves de Cerqueira. Orientador: Aimar Martins Lopes.

Este registro documenta a etapa de coleta documental do projeto (objetivo específico *a*: caracterizar a oferta e a dinâmica dos leilões) de forma reproduzível: fontes, instrumento, protocolo de cada rodada, definição das métricas, série das rodadas e achados. Ele é a base da seção de resultados da coleta nos Resultados Preliminares e no trabalho final. Os dados de cada rodada ficam versionados neste repositório; a data de cada coleta é a do commit correspondente.

---

## 1. Escopo

- **Recorte geográfico:** município do Rio de Janeiro. O caso de uso de referência é a busca por apartamento em quatro bairros da Zona Sul: Botafogo, Copacabana, Flamengo e Laranjeiras. O coletor dos sites dos leiloeiros inclui também o Catete, bairro contíguo, para não perder anúncios que o descrevem como endereço; os quadros desta documentação separam os quatro bairros-alvo do Catete.
- **Objeto coletado:** anúncios de leilão de imóveis e seus editais. São registrados exclusivamente dados do imóvel e do certame. O campo "Autor"/partes do processo nunca é coletado, e nenhum dado pessoal constante dos editais é transcrito (Lei nº 13.709/2018).
- **Período:** coletas exploratórias desde 25/07/2026, com periodicidade quinzenal prevista no projeto a partir de novembro de 2026.

## 2. Fontes e instrumento

### 2.1 Fontes

| Fonte | O que fornece | Acesso | Arquivo gerado |
|---|---|---|---|
| Relação de leiloeiros públicos da Corregedoria Geral da Justiça do TJRJ (PDF) | nome e endereço eletrônico de cada leiloeiro credenciado | público, download | `scripts/leiloeiros.json` (inventário com 77 registros e a plataforma de cada site) |
| Sites dos leiloeiros credenciados | anúncios de lotes judiciais: título, endereço, bairro, avaliação, lance mínimo, datas e lances das praças, modalidade, status, vara, link do edital, foto | público, rastreamento automatizado | `judicial_bruto.json` (não versionado) → `mapa/judicial.json` |
| Editais em PDF publicados nos sites | laudo: área, cômodos, matrícula do RGI, inscrição imobiliária, regra da 2ª praça | público | lidos sob demanda com `scripts/ler_edital.py`; resultado registrado em `scripts/extracao_manual.json` |
| Lista de imóveis à venda da Caixa Econômica Federal (CSV, estado do RJ) | id, bairro, endereço, preço, avaliação, desconto, nº de quartos, área, tipo, modalidade, link | público, download (`venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_RJ.csv`) | `mapa/data.json` |

### 2.2 Cobertura dos sites dos leiloeiros

O inventário classifica os 77 sites pela plataforma que os serve. Três plataformas concentram 32 sites e são lidas por três adaptadores do coletor; as demais ficam registradas para fases futuras.

| Plataforma | Sites | Situação na coleta |
|---|---:|---|
| suporteleiloes | 14 | coletado (adaptador 1) |
| lel.br | 11 | coletado (adaptador 2) |
| vlance | 7 | coletado (adaptador 3, via API REST não documentada) |
| superbid | 6 | não coletado |
| wordpress | 1 | não coletado |
| outras (sites próprios) | 34 | não coletado |
| bloqueado (HTTP 403) | 3 | inacessível ao rastreador |
| fora do ar | 1 | inacessível |
| **Total** | **77** | **32 coletados (42%)** |

Pendência: a página de resultados do site cita 78 leiloeiros; o inventário tem 77. Reconciliar com a planilha atual da CGJ antes dos Resultados Preliminares.

### 2.3 Instrumento (scripts)

| Script | Função |
|---|---|
| `scripts/atualiza_dados.py` | baixa o CSV da Caixa, filtra o município do Rio de Janeiro (normalizando grafias de bairro e excluindo registros de outros municípios rotulados como "Rio de Janeiro"), geocodifica centróides de bairros novos (Nominatim) e grava `mapa/data.json` com a data da lista (`data_geracao`). |
| `scripts/coleta_judicial.py` | percorre os 32 sites cobertos, lê os anúncios das categorias de imóveis, filtra os cinco bairros-alvo e grava `judicial_bruto.json` (campo `coletados` = anúncios analisados; `alvo` = anúncios nos bairros-alvo). Nunca lê o campo "Autor". |
| `scripts/ler_edital.py` | extrai o texto de um edital em PDF (sem dependências) para conferir quartos, área, matrícula e a regra da 2ª praça; detecta PDF escaneado (sem camada de texto). |
| `scripts/extracao_manual.json` | extração assistida por modelo de linguagem, revisada manualmente, por anúncio: `quartos` (null = não informado na fonte), `area`, `tipo`, `modalidade` corrigida, `endereco_geo`, `merge_em` (mesmo bem anunciado por outro leiloeiro), correções de `rodadas`, e `_nota` com a evidência. |
| `scripts/gera_judicial.py` | mescla a coleta bruta com a extração, deduplica (`merge_em`), geocodifica cada endereço (Nominatim, com cache em `mapa/geocache_judicial.json`) e grava `mapa/judicial.json`. |
| `scripts/serie_rodadas.py` | reconstrói a série das rodadas a partir do histórico do git e atualiza as tabelas da seção 4 deste registro. |

Os arquivos `mapa/*.json` alimentam o mapa publicado em GitHub Pages (`mapa/`), e a página `leiloes/` traz a leitura narrativa dos resultados.

## 3. Protocolo de uma rodada e definição das métricas

### 3.1 Passos

1. Atualizar a lista da Caixa: `python3 scripts/atualiza_dados.py`. Registrar a data da lista (campo `data_geracao`), o total de imóveis na capital e os bairros novos geocodificados.
2. Rastrear os sites dos leiloeiros: `python3 scripts/coleta_judicial.py judicial_bruto.json`. Registrar o número de anúncios analisados (`coletados`) e o de anúncios nos bairros-alvo.
3. Comparar os ids dos anúncios nos bairros-alvo com `scripts/extracao_manual.json`. Para cada anúncio novo: ler o anúncio e o edital (`python3 scripts/ler_edital.py <url_do_pdf> [regex]`), registrar quartos, área, tipo, modalidade, endereço normalizado e a regra da 2ª praça; identificar o mesmo bem anunciado por outro leiloeiro (chave: matrícula do RGI; na falta, endereço normalizado + processo) e apontar `merge_em`; anotar edital ausente ou PDF escaneado. Nunca transcrever nomes de pessoas, CPF ou dados das partes.
4. Gerar o arquivo do mapa: `python3 scripts/gera_judicial.py judicial_bruto.json`.
5. Atualizar as tabelas da série: `python3 scripts/serie_rodadas.py --escreve`, e redigir os achados da rodada na seção 5.
6. Atualizar os números da página `leiloes/index.html`, commitar com a mensagem padrão `Atualiza dados: Caixa DD/MM (N) e K lotes judiciais na Zona Sul` e publicar (`git push`).

### 3.2 Definições

- **Imóveis na capital (Caixa):** registros do CSV cujo município, após normalização das grafias de bairro, é o Rio de Janeiro, excluídos os bairros identificados como de outros municípios (por exemplo, Nova Iguaçu rotulado como "Rio de Janeiro").
- **Zona Sul (Caixa):** bairros Botafogo, Copacabana, Flamengo, Laranjeiras, Catete, Glória, Urca, Leme, Ipanema, Leblon, Lagoa, Jardim Botânico, Gávea, Humaitá, São Conrado, Vidigal, Cosme Velho e Santa Teresa. **4 bairros-alvo:** Botafogo, Copacabana, Flamengo e Laranjeiras.
- **Saíram / entraram:** ids presentes na lista anterior e ausentes na atual, e vice-versa. O percentual de saídas é calculado sobre a lista anterior.
- **Entradas que são relistagem:** entre os ids que entraram, os que já haviam aparecido em qualquer lista anterior da série. Mede quanto do movimento é retirada e recolocação do mesmo imóvel, e não oferta nova.
- **Anúncios na Zona Sul (judicial):** anúncios coletados nos cinco bairros-alvo nos sites cobertos, antes da deduplicação. **Bens distintos:** após a consolidação dos anúncios do mesmo bem (`merge_em`).
- **Com 2ª praça:** lotes com duas datas de praça lidas do anúncio. **2ª praça a 50%:** lance mínimo da 2ª praça igual à metade do da 1ª (tolerância de 1%).
- **Residenciais com nº de quartos:** entre os lotes de tipo apartamento, casa, cobertura, kitnet ou conjugado, os que têm `quartos` preenchido após a extração assistida (anúncio ou edital).

Observação: as rodadas anteriores a 04/10/2026 subestimam a 2ª praça, porque o coletor deixou de ler a segunda data quando a plataforma suporteleiloes alterou a marcação do rótulo; o instrumento foi corrigido em 04/10/2026 (ver seção 6).

## 4. Série das rodadas

<!-- serie:inicio -->
**Tabela 1 – Lista de imóveis da Caixa Econômica Federal, município do Rio de Janeiro, por data da lista**

| Lista da Caixa | Imóveis na capital | Zona Sul | 4 bairros-alvo | Sem nº de quartos | Saíram desde a lista anterior | Entraram | Entradas que são relistagem | Bairro com mais imóveis |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 24/07/2026 | 4.906 | 11 | 5 | 626 (13%) | — | — | — | Santa Cruz (1.366) |
| 07/08/2026 | 3.767 | 10 | 5 | 533 (14%) | 1.415 (29%) | 276 | 0 (0%) | Santa Cruz (1.046) |
| 27/08/2026 | 3.681 | 10 | 4 | 500 (14%) | 813 (22%) | 727 | 331 (46%) | Santa Cruz (1.090) |
| 02/10/2026 | 2.863 | 1 | 0 | 355 (12%) | 1.728 (47%) | 910 | 806 (89%) | Santa Cruz (862) |
| 13/10/2026 | 3.362 | 1 | 0 | 402 (12%) | 331 (12%) | 830 | 596 (72%) | Santa Cruz (993) |
| 30/10/2026 | 3.771 | 8 | 2 | 510 (14%) | 705 (21%) | 1.114 | 772 (69%) | Santa Cruz (939) |

**Tabela 2 – Coleta nos sites dos leiloeiros credenciados (lotes judiciais nos bairros-alvo), por data da coleta**

| Coleta nos sites | Sites cobertos | Anúncios na Zona Sul | Bens distintos (após dedupe) | Botafogo / Copacabana / Flamengo / Laranjeiras / Catete | Com 2ª praça | 2ª praça a 50% | Residenciais com nº de quartos | Observação |
|---|---:|---:|---:|---|---:|---:|---|---|
| 25/07/2026 | 25 | 22 | 18 | 5 / 7 / 1 / 3 / 2 | 8 | 6 | 5 de 15 | primeira coleta: 25 dos 77 sites (adaptadores suporteleiloes e lel.br) |
| 08/08/2026 | 32 | 23 | 12 | 3 / 6 / 0 / 3 / 0 | 4 | 2 | 5 de 8 | cobertura ampliada para 32 sites (adaptador vlance) |
| 27/08/2026 | 32 | 27 | 13 | 4 / 4 / 2 / 3 / 0 | 3 | 3 | 3 de 8 |  |
| 04/10/2026 | 32 | 17 | 14 | 3 / 7 / 3 / 1 / 0 | 8 | 8 | 4 de 8 | coletor corrigido: 2ª praça voltou a ser lida |
| 14/10/2026 | 32 | 18 | 15 | 4 / 8 / 2 / 1 / 0 | 9 | 8 | 4 de 9 |  |
| 02/11/2026 | 32 | 17 | 14 | 6 / 6 / 1 / 1 / 0 | 8 | 5 | 4 de 11 | quinta rodada; registro de coleta iniciado |

_Tabelas geradas por `scripts/serie_rodadas.py` a partir do histórico do repositório; não editar à mão._
<!-- serie:fim -->

## 5. Achados por rodada

### 25/07/2026 – primeira coleta (lista da Caixa de 24/07)

- A lista da Caixa registrava 4.906 imóveis na capital, concentrados na periferia (Santa Cruz, 1.366); a Zona Sul tinha 11 e os quatro bairros-alvo, 5. Em 13% dos registros o número de quartos não vinha preenchido.
- O rastreamento de 25 sites localizou 22 anúncios nos bairros-alvo, consolidados em 18 bens distintos (Botafogo 5, Copacabana 7, Flamengo 1, Laranjeiras 3, Catete 2). Quatro anúncios eram repetições do mesmo bem por outro leiloeiro.
- O TJRJ não mantém portal único de leilões; os editais vivem nos sites dos leiloeiros (o Diário da Justiça Eletrônico não é fonte primária dos anúncios). Nenhuma das cinco plataformas agregadoras consultadas em 25/07 oferecia filtro por número de dormitórios. A lista da Caixa era a única fonte com campos estruturados e download completo.
- Para o fluxo "3 ou mais quartos na Zona Sul", a Caixa não tinha resultado e a via judicial tinha 3.

### 08/08/2026 – ampliação da cobertura (lista da Caixa de 07/08)

- Adaptador para a plataforma vlance (sete sites, lidos por API REST não documentada), elevando a cobertura para 32 sites.
- Caixa: 3.767 imóveis; 1.415 saíram (29% da lista anterior) e 276 entraram em duas semanas.
- Judicial: 23 anúncios → 12 bens distintos; 11 anúncios eram repetições entre leiloeiros.

### 27/08/2026 (lista da Caixa de 27/08)

- Caixa: 3.681 imóveis; Zona Sul 10, bairros-alvo 4.
- Judicial: 27 anúncios → 13 bens; 14 anúncios (52%) eram repetições. Um único bem, o prédio da Rua Pereira da Silva (Laranjeiras), estava anunciado por nove leiloeiros credenciados, com lance mínimo divergente entre eles (R$ 600 mil na maioria, R$ 440 mil em um); uma loja em Copacabana, por três. Nos dois casos, certame da Justiça do Trabalho distribuído a vários profissionais. Deduplicação é requisito, não refinamento.

### 04/10/2026 (lista da Caixa de 02/10)

- Caixa: 2.863 imóveis. Entre 27/08 e 02/10, 1.728 saíram (47%) e 910 entraram, dos quais 806 (89%) eram relistagens de imóveis já vistos. A Zona Sul caiu para um imóvel (terreno em São Conrado) e os bairros-alvo para zero. A composição por modalidade mudou ("Venda Direta Online" 2.623 → 1.220; "Venda Online" 293 → 1.378; "Licitação Aberta" desapareceu).
- A lista da Caixa traz imóveis de outros municípios rotulados como "Rio de Janeiro" (conferido por geocodificação: Nova Iguaçu). Criado o filtro de exclusão no instrumento.
- Judicial: 118 anúncios analisados nos 32 sites, 17 nos bairros-alvo, 14 bens distintos (repetições: 3 em 17; a taxa de duplicação é instável e vem em blocos, quando um certame grande é distribuído).
- Correção de instrumento: o coletor vinha perdendo a 2ª praça (mudança de marcação na plataforma suporteleiloes); corrigido e recoletado, 8 dos 17 anúncios trouxeram 2ª praça, todas a 50% da avaliação, cerca de três dias após a primeira.
- Teto da extração: em 2 dos 8 lotes residenciais o número de quartos não consta do anúncio nem do edital (o laudo descreve área, prédio e bairro, não os cômodos). "Não informado" precisa ser um estado explícito do filtro.
- Chave de identidade do bem: dois lotes em Laranjeiras com endereços de esquina (Leite Leal 32 × Sebastião de Lacerda 70) pareciam o mesmo bem, mas têm matrículas, áreas (1.178 × 1.105 m²) e processos distintos. A chave é a matrícula do RGI, não o endereço.

### 14/10/2026 (lista da Caixa de 13/10)

- Caixa: 3.362 imóveis. Em 11 dias, 331 saíram (12%) e 830 entraram (72% relistagens). A composição por modalidade voltou ao padrão anterior ("Venda Direta Online" 1.220 → 2.366; "Venda Online" 1.378 → 430; "Licitação Aberta" reapareceu com 192): a modalidade oscila em ciclos de campanha, e duas medições não fazem tendência. Zona Sul: 1 (o mesmo terreno); bairros-alvo: 0.
- Judicial: 106 anúncios analisados, 18 nos bairros-alvo, 15 bens distintos (Copacabana 8, Botafogo 4, Flamengo 2, Laranjeiras 1). Entre 04/10 e 14/10, 2 lotes se encerraram e 3 entraram: a via judicial gira muito mais devagar que a lista da Caixa.
- A 2ª praça a 50% não é regra: em 8 das 9 segundas praças o piso é metade da avaliação; na nona (sala em Copacabana, 4ª Vara de Família) o juízo fixou piso único para as duas datas. O art. 891 do CPC só veda o preço vil; os 50% são convenção fixada caso a caso. O desconto deve ser lido do edital, nunca calculado.
- Relistagem temporal: a cobertura da Praia de Botafogo 198 (avaliação R$ 10 milhões) apareceu em 25/07 com praça em 30/07, sumiu de três coletas (08/08, 27/08, 04/10) e reapareceu em 14/10 com praça em 02/12 e a mesma avaliação. Um retrato do dia não diz que o imóvel já foi a leilão sem venda; o agregador precisa de memória de lote.
- Teto da extração por outro ângulo: dos 18 anúncios, 3 não tinham edital publicado e 1 era PDF escaneado (sem camada de texto); 4 em 18 fora do alcance de um extrator de texto.
- O tipo do imóvel diverge entre fontes (anúncio "Sala Comercial" × laudo "Apartamento de 34 m²"). Mantida a classificação do anúncio, divergência registrada.

### 02/11/2026 – quinta rodada (lista da Caixa de 30/10)

- Caixa: 3.771 imóveis. Entre 13/10 e 30/10, 705 saíram (21%) e 1.114 entraram, dos quais 772 (69%) relistagens. Na série de seis listas, 6.258 ids distintos apareceram ao menos uma vez; apenas 1.063 estiveram nas seis, e 771 apareceram em uma única lista. O movimento da lista é, em sua maior parte, retirada e recolocação dos mesmos imóveis, não oferta nova.
- Entre os 2.657 imóveis que permaneceram na lista, 1.314 tiveram o preço reduzido e nenhum teve aumento: a Caixa reprecifica para baixo ao longo das campanhas, o que faz da mudança de preço um gatilho de notificação tão relevante quanto a entrada.
- Pela primeira vez desde 07/08 há imóveis da Caixa nos bairros-alvo: dois em Copacabana (um apartamento de 77 m² na Rua Rodolfo Dantas, em "Licitação Aberta", por R$ 592.995, sem número de quartos informado; e uma unidade de 11 m² na Rua Leopoldo Miguez, em "Leilão SFI", por R$ 503.798, acima da avaliação de R$ 470.000, registro a conferir na fonte). A Zona Sul passou de 1 para 8 (Glória 2, Santa Teresa 2, Copacabana 2, Cosme Velho 1, São Conrado 1). O caso de uso continua dependente da via judicial, mas a Caixa deixou de ser zero.
- Bairro novo na lista: Sepetiba (geocodificado). O número de quartos segue ausente em 14% dos registros da Caixa.
- Judicial: 69 anúncios analisados nos 32 sites (106 em 14/10), 17 nos bairros-alvo, 14 bens distintos após a consolidação de 3 anúncios repetidos (Copacabana 6, Botafogo 6, Flamengo 1, Laranjeiras 1).
- Movimento desde 14/10: 8 anúncios saíram (7 com praça entre 19 e 29/10 e 1 retirado do site na véspera da praça de 03/11, o apartamento da Av. Rainha Elizabeth 151, cujo edital era escaneado); 7 entraram, dos quais 2 são relistagens: a casa da Rua Senador Correia 37 (coletada em 25/07, ausente de 08/08 a 14/10, de volta com praças em 30/11 e 02/12 e a mesma avaliação) e o apartamento da Av. Atlântica 2172 (coletado em 25/07 e 08/08, de volta com avaliação atualizada de R$ 10,88 para R$ 11,52 milhões). Os 10 anúncios que permaneceram não mudaram de praça, lance ou status.
- 2ª praça: 8 dos 14 bens têm segunda data; 5 a 50% da avaliação. As três exceções seguem regras distintas, todas lidas do edital: 100% (sala em Copacabana, 4ª Vara de Família), 60% por decisão do juízo (Av. Atlântica 2172) e 83% por reserva de cota-parte de coproprietários (duplex da Rua República do Peru 72, 3ª Vara Federal: 66,67% do bem reservados e 50% aplicados apenas à fração executada, art. 843, § 2º, do CPC). O desconto da 2ª praça é um dado do edital, não uma fórmula.
- Teto da extração: dos 7 anúncios novos, 1 edital é PDF escaneado (Rua Muniz Barreto 330: 736 imagens, sem fontes) e 1 (Justiça Federal) usa fontes com codificação por glifo (Identity-H), que o extrator próprio do projeto não decodifica e a biblioteca pypdf lê integralmente. O instrumento tem, portanto, dois tipos de cegueira, um deles sanável por troca de biblioteca. O número de quartos é conhecido em 4 dos 11 bens residenciais; entre os novos, só o duplex da República do Peru informa (3 quartos, 1 suíte); nos demais o laudo descreve área e prédio, não cômodos. O conjugado da Praia de Botafogo 356 (21 m²) foi registrado como 1 quarto, pela convenção já adotada.
- Chave de identidade: o apartamento da Rua Bambina 114 não tem matrícula individualizada (alienam-se direitos possessórios; a matrícula anexa é do terreno), e o edital da Praia de Botafogo 356 grafa a própria matrícula de duas formas (18.117 e 18.177). A inscrição imobiliária do IPTU, presente em todos os editais lidos, é a chave de reserva para a consolidação.
- Observação dos desfechos: das 8 páginas de anúncios que saíram do site, 7 respondem erro HTTP 500 (removidas) e a única acessível informa "Leilão Suspenso" (terreno em Laranjeiras, avaliação R$ 4 milhões). Arrematação, ausência de lances e suspensão não são recuperáveis depois da praça: o protocolo de observação previsto no projeto precisa ser executado em tempo real, no dia de cada praça. A primeira praça entre os bens atuais é 16/11/2026 (Praia de Botafogo 356); as praças de novembro e dezembro são a primeira oportunidade de aplicá-lo.
- Informação que só o edital traz: débitos de IPTU (R$ 203 mil na Av. Atlântica 2172; vários exercícios na Praça José de Alencar 5), indisponibilidade averbada, direito de preferência de condôminos e parcelamento. São os dados que compõem o custo total da compra e não aparecem no anúncio.
- Instrumento: o adaptador vlance não lê o campo `anexos` da API (onde está o edital); registrado à mão nesta rodada.

## 6. Limitações e correções de instrumento

- **Cobertura parcial:** 32 dos 77 sites; os números judiciais refletem essa fatia, não o mercado inteiro. O patamar do projeto (60% dos leiloeiros com site ativo) ainda não foi alcançado.
- **Extração assistida:** quartos, área e tipo foram extraídos com apoio de modelo de linguagem e revisados manualmente, registrados em arquivo versionado. O protocolo automatizado de extração (modelo, versão, prompt, esquema, temperatura zero, medição de acurácia e de preenchimentos indevidos) é a etapa seguinte do projeto.
- **2ª praça antes de 04/10/2026:** subestimada pela falha de leitura descrita na seção 3.2; os números das rodadas de 25/07 a 27/08 são limites inferiores.
- **Definição de giro:** as leituras narrativas anteriores usaram ora saídas/lista anterior (47% entre 27/08 e 02/10), ora (saídas + entradas)/lista anterior (41% entre 02/10 e 13/10). Neste registro a série usa uma definição única (seção 3.2); os textos do site devem ser lidos com essa ressalva.
- **Catete:** incluído no coletor, excluído do caso de uso de quatro bairros; as tabelas separam os dois.
- **Número do processo no arquivo público:** `mapa/judicial.json`, publicado no mapa, contém os campos `processo` e `vara`. O projeto de pesquisa declara que o número do processo é usado apenas como chave interna de consolidação e não é divulgado. Pendência: retirar o campo do arquivo publicado (mantendo-o apenas na coleta bruta e na extração), para alinhar o instrumento ao projeto.
- **Observação dos leilões:** o coletor registra o status do leilão, mas o protocolo de observação das praças (número de lances, valor final e desfecho) previsto no projeto ainda não foi implementado nem registrado.
- **Editais ilegíveis para o extrator próprio:** além dos PDFs escaneados, PDFs com fontes Identity-H (codificação por glifo) saem como lixo em `ler_edital.py`; a biblioteca pypdf, já disponível, lê esses casos. Até a troca, a conferência manual usa pypdf quando o extrator devolve texto vazio ou ilegível.
- **Adaptador vlance sem edital:** a API traz o edital no campo `anexos`, que o adaptador não lê; o campo `edital_url` desses lotes é preenchido à mão em `extracao_manual.json`.
- **Concorrentes:** os números das plataformas agregadoras vêm de leitura direta em 25/07/2026 e não passaram por verificação independente.

## 7. Próximos passos da coleta

1. Rodadas quinzenais a partir de novembro de 2026, com este protocolo.
2. Reconciliar 77 × 78 leiloeiros com a planilha atual da CGJ.
3. Retirar `processo` e `vara` do arquivo publicado.
4. Definir e registrar o protocolo de observação das praças (data, nº da praça, lance mínimo, nº de lances, valor final, desfecho) e acompanhar os lotes com praça no período.
5. Trocar a extração de texto de `ler_edital.py` por pypdf (ou usá-la como alternativa) e fazer o adaptador vlance ler o campo `anexos`.
6. Aplicar o protocolo de observação nas praças de 16/11 a 17/12/2026 (onze bens com data marcada).
7. Especificar o protocolo de extração por modelo de linguagem (modelo, versão, prompt, esquema, parâmetros) e a amostra de conferência para medir acurácia e preenchimentos indevidos.
