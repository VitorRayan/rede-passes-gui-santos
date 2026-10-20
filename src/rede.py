"""Construção da rede de passes e cálculo das métricas (NetworkX).

Convenções:
- G (DiGraph): aresta A -> B com atributo `peso` (passes ou assistências) e
  `distancia` = 1 / peso (muitos passes = conexão "curta"), usada em caminhos,
  closeness e betweenness.
- U (Graph): versão não dirigida, peso(A,B) = peso(A->B) + peso(B->A),
  usada em clustering e k-core.
"""
import itertools
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROCESSED = RAIZ / "data" / "processed"


def nome_curto(nome):
    """'Brandin Podziemski' -> 'Podziemski'; 'Gui Santos' -> 'G. Santos'."""
    partes = nome.split()
    if nome == "Gui Santos":
        return "Gui Santos"
    if partes[-1] in {"II", "III", "Jr.", "Sr."}:  # Gary Payton II -> Payton II
        return " ".join(partes[-2:])
    return partes[-1] if len(partes) > 1 else nome


# ---------------------------------------------------------------- construção

def montar_rede(arestas, jogadores, coluna_peso="passes"):
    """DiGraph a partir da lista de arestas e da tabela de jogadores (nós)."""
    G = nx.DiGraph()
    for _, j in jogadores.iterrows():
        G.add_node(int(j["player_id"]), nome=j["nome"], rotulo=nome_curto(j["nome"]),
                   minutos=float(j["minutos"]), pontos=float(j["pontos"]),
                   posicao=j.get("posicao", ""))
    for _, a in arestas.iterrows():
        w = float(a[coluna_peso])
        if w <= 0:
            continue
        G.add_edge(int(a["origem_id"]), int(a["destino_id"]), peso=w, distancia=1.0 / w,
                   passes=float(a["passes"]), assistencias=float(a["assistencias"]))
    return G


def normalizar_temporada(arestas, jogadores_temp):
    """Passes por jogo para a rede da temporada.

    O par A->B só pode trocar passes nos jogos em que os dois estavam no time e
    em quadra. Aproximamos esse número por min(jogos de A, jogos de B).
    Ex.: Porziņģis jogou 15 jogos pelo GSW; sem isso, todas as arestas dele
    pareceriam fracas só porque ele chegou tarde.
    """
    jogos = jogadores_temp.set_index("player_id")["jogos"]
    ar = arestas.copy()
    ar["jogos_par"] = [min(jogos[o], jogos[d]) for o, d in zip(ar["origem_id"], ar["destino_id"])]
    for col in ["passes", "assistencias", "fgm", "fga"]:
        ar[col + "_total"] = ar[col]
        ar[col] = ar[col] / ar["jogos_par"]
    return ar


def nao_dirigida(G, atributo="peso"):
    """Soma A->B + B->A numa aresta não dirigida."""
    U = nx.Graph()
    U.add_nodes_from(G.nodes(data=True))
    for a, b, d in G.edges(data=True):
        w = d[atributo]
        if U.has_edge(a, b):
            U[a][b]["peso"] += w
        else:
            U.add_edge(a, b, peso=w)
    for a, b, d in U.edges(data=True):
        d["distancia"] = 1.0 / d["peso"]
    return U


def esqueleto(G, k):
    """Esqueleto por limiar (semana 6): mantém só arestas com peso >= k."""
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes(data=True))
    H.add_edges_from((a, b, d) for a, b, d in G.edges(data=True) if d["peso"] >= k)
    return H


def matriz_adjacencia(G, ordem=None):
    """Matriz de adjacência ponderada (linhas = quem passa, colunas = quem recebe)."""
    ordem = ordem or list(G.nodes)
    M = nx.to_pandas_adjacency(G, nodelist=ordem, weight="peso")
    rot = [G.nodes[n]["rotulo"] for n in ordem]
    M.index, M.columns = rot, rot
    return M


# ---------------------------------------------------------------- métricas

def eficiencia_ponderada(G):
    """Eficiência global dirigida com distância = 1/passes.

    E = média sobre pares ordenados (u != v) de 1 / d(u, v); pares sem caminho
    contam 0. Versão ponderada da eficiência de Latora & Marchiori.
    """
    n = G.number_of_nodes()
    if n < 2:
        return 0.0
    dist = dict(nx.all_pairs_dijkstra_path_length(G, weight="distancia"))
    soma = sum(1.0 / dist[u][v] for u in G for v in dist[u] if u != v and dist[u][v] > 0)
    return soma / (n * (n - 1))


def resumo(G):
    """Medidas globais da rede (semanas 2 e 4)."""
    U = nao_dirigida(G)
    scc = list(nx.strongly_connected_components(G))
    wcc = list(nx.weakly_connected_components(G))
    fortemente = len(scc) == 1
    out = {
        "nos": G.number_of_nodes(),
        "arestas": G.number_of_edges(),
        "densidade": nx.density(G),
        "passes_totais": G.size(weight="peso"),
        "n_wcc": len(wcc),
        "n_scc": len(scc),
        "maior_scc": max(len(c) for c in scc),
        "diametro_saltos": nx.diameter(G) if fortemente else np.nan,
        "dist_media_saltos": nx.average_shortest_path_length(G) if fortemente else np.nan,
        "eficiencia_global_nao_ponderada": nx.global_efficiency(U),
        "eficiencia_global_ponderada": eficiencia_ponderada(G),
        "reciprocidade": nx.reciprocity(G),
        "clustering_medio_ponderado": nx.average_clustering(U, weight="peso"),
        "degeneracy": max(nx.core_number(U).values()) if U.number_of_edges() else 0,
    }
    return out


def _normaliza_peso(U):
    """Cópia de U com pesos em [0, 1] (exigência do clustering ponderado)."""
    V = U.copy()
    wmax = max((d["peso"] for _, _, d in V.edges(data=True)), default=1)
    for _, _, d in V.edges(data=True):
        d["peso"] = d["peso"] / wmax
    return V


def medidas_nos(G):
    """Tabela com todas as medidas por jogador."""
    U = nao_dirigida(G)
    n = G.number_of_nodes()
    total = G.size(weight="peso") or 1.0

    forca_in = dict(G.in_degree(weight="peso"))
    forca_out = dict(G.out_degree(weight="peso"))
    # closeness dirigida: o NetworkX usa as distâncias que CHEGAM ao nó,
    # ou seja, "quão fácil é a bola chegar até ele" a partir dos outros.
    clo_in = nx.closeness_centrality(G, distance="distancia")
    clo_out = nx.closeness_centrality(G.reverse(copy=True), distance="distancia")
    btw = nx.betweenness_centrality(G, weight="distancia", normalized=True)
    try:
        # Em DiGraph o NetworkX calcula o autovetor à ESQUERDA: a importância de
        # um nó vem das arestas de ENTRADA (prestígio de quem recebe passes de
        # quem também recebe muitos passes).
        eig = nx.eigenvector_centrality(G, weight="peso", max_iter=5000)
    except nx.PowerIterationFailedConvergence:
        eig = {v: np.nan for v in G}
    pr = nx.pagerank(G, weight="peso")
    clus = nx.clustering(_normaliza_peso(U), weight="peso") if U.number_of_edges() else {v: 0 for v in G}
    core = nx.core_number(U) if U.number_of_edges() else {v: 0 for v in G}

    linhas = []
    for v in G:
        m = G.nodes[v]["minutos"] or np.nan
        linhas.append({
            "player_id": v,
            "jogador": G.nodes[v]["rotulo"],
            "minutos": G.nodes[v]["minutos"],
            "pontos": G.nodes[v]["pontos"],
            "grau_entrada": G.in_degree(v),
            "grau_saida": G.out_degree(v),
            "centralidade_grau": nx.degree_centrality(U)[v] if n > 1 else 0,
            "forca_entrada": forca_in[v],
            "forca_saida": forca_out[v],
            "parcela_recebida": forca_in[v] / total,
            "parcela_feita": forca_out[v] / total,
            "closeness_entrada": clo_in[v],
            "closeness_saida": clo_out[v],
            "betweenness": btw[v],
            "eigenvector_entrada": eig[v],
            "pagerank": pr[v],
            "clustering": clus[v],
            "core_number": core[v],
        })
    df = pd.DataFrame(linhas).set_index("jogador")
    return df


def forca_por_36(df, minutos):
    """Força de entrada/saída por 36 minutos em quadra (controle de minutos)."""
    out = df.copy()
    m = out.index.map(minutos)
    out["recebidos_36"] = out["forca_entrada"] / m * 36
    out["feitos_36"] = out["forca_saida"] / m * 36
    return out


def ranks(df, colunas):
    """Rank (1 = maior) de cada jogador em cada medida.

    Empates recebem a PIOR posição do grupo (method="max"): se 7 jogadores têm
    betweenness 0, todos ficam em 10º, e não em 4º. É a escolha conservadora."""
    return df[colunas].rank(ascending=False, method="max").astype(int)


def nucleo_periferia(df, coluna="forca_total"):
    """Núcleo x periferia (semana 3): núcleo = quem concentra a força total
    acima da mediana do time; periferia = o resto."""
    tot = df["forca_entrada"] + df["forca_saida"]
    return np.where(tot >= tot.median(), "núcleo", "periferia")


# ---------------------------------------------------------------- robustez

def robustez(G, remover):
    """Remove um nó e mede o efeito na rede e nos outros jogadores."""
    antes = resumo(G)
    H = G.copy()
    H.remove_node(remover)
    depois = resumo(H)
    m_antes = medidas_nos(G).drop(index=G.nodes[remover]["rotulo"])
    m_depois = medidas_nos(H)
    return {
        "removido": G.nodes[remover]["rotulo"],
        "passes_perdidos_%": 100 * (1 - depois["passes_totais"] / antes["passes_totais"]),
        "eficiencia_antes": antes["eficiencia_global_ponderada"],
        "eficiencia_depois": depois["eficiencia_global_ponderada"],
        "queda_eficiencia_%": 100 * (1 - depois["eficiencia_global_ponderada"]
                                     / antes["eficiencia_global_ponderada"]),
        "n_scc_depois": depois["n_scc"],
        "n_wcc_depois": depois["n_wcc"],
        "densidade_depois": depois["densidade"],
        "variacao_media_betweenness_outros": (m_depois["betweenness"]
                                              - m_antes["betweenness"]).abs().mean(),
    }


def robustez_media_aleatoria(G, excluir=(), rodadas=None):
    """Efeito médio de remover cada um dos outros jogadores (linha de base)."""
    linhas = [robustez(G, v) for v in G if v not in excluir]
    return pd.DataFrame(linhas)
