# Roteiro do vídeo (máx. 15 min)

> **Regras do professor:** TODOS os integrantes aparecem com **câmera aberta e rosto visível** durante o vídeo inteiro (senão a nota é zero). Mostrar a rede e o código **ao vivo** (notebook rodando), não ficar só lendo o README. O link precisa ser do YouTube, **não listado** (privado NÃO), e precisa abrir numa janela anônima.
>
> Troque **Integrante 1/2/3** pelos nomes. Se forem só dois, junte as falas do 3 com o 1.

**Antes de gravar:** abra o `analise.ipynb` no Jupyter/VS Code com o kernel do `.venv`, rode tudo uma vez (`Run All`) e deixe as figuras de `figures/` abertas numa aba. Fonte do editor em 16pt ou mais. Grave em 1080p.

---

## 0:00–2:00 · Problema, pergunta e quem se beneficia (Integrante 1)

- Apresentação rápida: "Somos X, Y e Z, e este é o nosso projeto da Unidade 1 de Grafos."
- "Em 25 de março de 2026, o brasileiro Gui Santos fez 31 pontos pelo Golden State Warriors contra o Brooklyn, o recorde da carreira dele."
- **A pergunta:** "Nesse jogo, a bola passou a fluir por ele, ou seja, o time jogou para ele? Ou ele pontuou fora da estrutura de passes do time?"
- **Quem se beneficia:** "A comissão técnica e o scouting. Se foi estrutural, o resultado é repetível: dá para desenhar jogadas para ele. Se foi individual, foi uma noite fora da curva."
- **Por que rede:** "O box score diz *quantos* pontos. Não diz se a bola chegava até ele, nem por quem ela passava. Isso é estrutura: centralidade, núcleo, dependência."

## 2:00–5:00 · Dados e modelagem (Integrante 2)

*Na tela: README seção Dados, e depois `src/coleta.py`.*

- Fonte: stats.nba.com, a base oficial da NBA, com o rastreamento óptico dos passes, via `nba_api`. "São dados reais, de um jogo real."
- Mostrar `coletar_tudo` em `src/coleta.py`: achar o jogador → log da carreira → jogo com mais pontos (GAME_ID 0022501060) → `playerdashptpass` com DateFrom = DateTo = dia do jogo, um request por jogador.
- Contar a história técnica em 20 s: "A API passou a bloquear a biblioteca `requests`; trocamos a sessão por `curl_cffi`, que imita o Chrome."
- Mostrar a flag `BAIXAR_DADOS = False`: "O professor reproduz tudo com os CSVs salvos, mesmo que a NBA bloqueie o IP dele."
- **Modelagem** (*na tela: a célula de modelagem do notebook*):
  - Nó = os 10 jogadores do GSW que entraram em quadra.
  - Aresta **dirigida** A → B = A passou para B, porque passar e receber são papéis diferentes.
  - Peso = nº de passes; distância = 1/passes para caminhos e betweenness.
  - De fora: o adversário, a ordem dos passes (o dado é agregado), rebotes e jogadas individuais.
  - Limpeza: Curry e Butler **não jogaram** (contexto importante); a checagem feito × recebido bate 100%; a rede da temporada foi normalizada para passes por jogo.

## 5:00–10:00 · Análise, nomeando cada ferramenta do curso (Integrantes 3 e 1)

*Na tela: notebook rodando, rolar célula por célula. Ler o comentário `# Conceito: … — Semana N` em voz alta.*

- **(Int. 3) Semana 2:** densidade 0,76 → "quase todo mundo passa para quase todo mundo, então o que importa é o peso". Mostrar o **heatmap da matriz de adjacência** e apontar a coluna do Gui.
- **(Int. 3) Semana 3:** força de entrada/saída. "O Gui recebeu 61 passes, o maior número do time, e isso continua no topo **por 36 minutos**." Mostrar o gráfico recebe × passa. BFS/snowball a partir do Gui.
- **(Int. 3) Semana 4:** uma SCC só, diâmetro 2. "A distância ponderada média até o Gui é a menor do time."
- **(Int. 1) Semana 4, centralidades:** mostrar a figura da rede jogo × temporada lado a lado. "Betweenness com distância = 1/passes: o Gui é o nº 1 no jogo e tem zero na temporada." Explicar o eigenvector de entrada (prestígio de quem recebe).
- **(Int. 1) Robustez:** "Tirar o Gui derruba a eficiência da rede em cerca de 16%, o mesmo que tirar o Podziemski, o organizador do time. Tirar qualquer outro jogador praticamente não muda nada. Na temporada, tirar o Gui quase não muda a eficiência."
- **(Int. 1) Semana 5:** k-core. "Com o limiar de ligações fortes, o Gui continua no núcleo mais coeso, junto com Green, Podziemski, Melton e Porziņģis."
- **(Int. 1) Semana 6:** esqueleto por limiar k = 1, 2, 3, 5 e a figura de sensibilidade. "A conclusão não muda com o limiar." Jaccard: "com k = 5, só 17% das ligações fortes do Gui no jogo existem na temporada, então é uma estrutura nova."

## 10:00–13:00 · Resposta e limitações (Integrante 2)

*Na tela: figura `03_centralidades_gui_jogo_vs_temporada.png`, depois `08_percentil_temporada.png`.*

- **Resposta:** "O time jogou para ele. No jogo do recorde, o Gui foi o 1º em passes recebidos, betweenness, closeness e PageRank, e o 2º em eigenvector. Na temporada, ele fica entre o 4º e o 6º. Das 11 cestas dele, 6 foram assistidas, e ele não pontuou de rebote ofensivo nem de roubo: todos os arremessos vieram depois de receber um passe."
- Mostrar o histograma: "Comparado com os outros jogos dele na temporada, o recorde está no topo da distribuição de passes recebidos." (ler o percentil impresso no notebook)
- **Limitações** (escolher 4 e falar como contornar): n = 1 jogo (contornado em parte com a distribuição); dado agregado, sem sequência; minutos confundem (usamos por 36 min); **Curry e Butler fora** libera posses (comparamos com jogos sem eles); passe ≠ qualidade do passe; sensibilidade ao limiar (testada).
- "Então, para o scouting: foi estrutural **naquele contexto de desfalques**. O sistema sem as estrelas o escolheu como destino da bola."

## 13:00–15:00 · Quem fez o quê e próximos passos (todos)

- **Integrante 1:** _(ex.: coleta e limpeza dos dados, `src/coleta.py`)_
- **Integrante 2:** _(ex.: modelagem, métricas, `src/rede.py`)_
- **Integrante 3:** _(ex.: notebook, figuras, README e vídeo)_
- Próximos passos: rede completa em todos os jogos (centralidade por jogo em vez de só passes recebidos); usar o play-by-play para separar por quarto e tirar o garbage time; normalizar por minutos **juntos em quadra** (lineups); ver se o padrão se repetiu nos jogos seguintes (27 pts contra WAS, 25 contra CLE).
- Encerramento: "Obrigado! Código, dados e figuras estão no repositório, e o link está no README."
