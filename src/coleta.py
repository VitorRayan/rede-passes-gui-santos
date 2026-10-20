"""Funções de coleta de dados da NBA (stats.nba.com) via nba_api.

Todo JSON bruto é salvo em data/raw/ para que a análise possa ser refeita
sem acessar a API (o stats.nba.com costuma bloquear IPs de nuvem/universidade).
"""
import json
import time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"

GSW_TEAM_ID = 1610612744

# Headers de navegador: sem eles o stats.nba.com costuma recusar a conexão.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

PAUSA = 0.6  # segundos entre requests


def _configurar_sessao():
    """O stats.nba.com bloqueia (timeout silencioso) a impressão digital TLS da
    biblioteca `requests`. Trocamos a sessão HTTP da nba_api por uma do
    curl_cffi, que imita o TLS do Chrome. Os endpoints continuam sendo os da nba_api."""
    from curl_cffi import requests as curl_requests
    from nba_api.stats.library.http import NBAStatsHTTP
    NBAStatsHTTP.set_session(curl_requests.Session(impersonate="chrome"))


_configurar_sessao()


def chamar(endpoint_cls, nome_arquivo, tentativas=5, **kwargs):
    """Chama um endpoint da nba_api com retry e backoff exponencial.

    Salva o JSON bruto em data/raw/<nome_arquivo>.json e devolve o dict.
    Se o arquivo já existir, reaproveita (cache) em vez de baixar de novo.
    """
    RAW.mkdir(parents=True, exist_ok=True)
    destino = RAW / f"{nome_arquivo}.json"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))

    espera = 5.0
    for tentativa in range(1, tentativas + 1):
        try:
            resp = endpoint_cls(headers=HEADERS, timeout=60, **kwargs)
            dados = resp.get_dict()
            destino.write_text(json.dumps(dados), encoding="utf-8")
            time.sleep(PAUSA)
            return dados
        except Exception as erro:  # timeout, conexão recusada, JSON inválido...
            print(f"  [tentativa {tentativa}/{tentativas}] {nome_arquivo}: {erro}")
            time.sleep(espera)
            espera *= 2
    raise RuntimeError(f"Falha ao baixar {nome_arquivo} após {tentativas} tentativas")


def resultset_df(dados, nome):
    """Converte um resultSet (formato stats.nba.com) em DataFrame."""
    conjuntos = dados.get("resultSets") or dados.get("resultSet")
    if isinstance(conjuntos, dict):
        conjuntos = [conjuntos]
    for rs in conjuntos:
        if rs["name"] == nome:
            return pd.DataFrame(rs["rowSet"], columns=rs["headers"])
    raise KeyError(nome)


def temporada_str(ano_inicio):
    """2024 -> '2024-25'."""
    return f"{ano_inicio}-{str(ano_inicio + 1)[-2:]}"


# ---------------------------------------------------------------- jogador

def achar_jogador(nome="Gui Santos"):
    from nba_api.stats.static import players
    achados = players.find_players_by_full_name(nome)
    if not achados:
        raise ValueError(f"Jogador não encontrado: {nome}")
    return achados[0]


def log_carreira(player_id):
    """Log de todos os jogos (temporada regular e playoffs) da carreira."""
    from nba_api.stats.endpoints import playercareerstats, playergamelog

    carreira = chamar(playercareerstats.PlayerCareerStats, f"carreira_{player_id}",
                      player_id=player_id)
    temporadas = resultset_df(carreira, "SeasonTotalsRegularSeason")["SEASON_ID"].unique()

    logs = []
    for temp in temporadas:
        for tipo in ["Regular Season", "Playoffs"]:
            sufixo = tipo.replace(" ", "")
            dados = chamar(playergamelog.PlayerGameLog,
                           f"gamelog_{player_id}_{temp}_{sufixo}",
                           player_id=player_id, season=temp,
                           season_type_all_star=tipo)
            df = resultset_df(dados, "PlayerGameLog")
            if len(df):
                df["SEASON"] = temp
                df["SEASON_TYPE"] = tipo
                logs.append(df)
    return pd.concat(logs, ignore_index=True)


def jogo_recorde(log):
    """Linha do jogo com mais pontos (desempate: mais minutos)."""
    return log.sort_values(["PTS", "MIN"], ascending=False).iloc[0]


# ---------------------------------------------------------------- jogo

def box_score(game_id):
    """Box score tradicional do jogo (minutos, pontos, posição de titular)."""
    from nba_api.stats.endpoints import boxscoretraditionalv3
    return chamar(boxscoretraditionalv3.BoxScoreTraditionalV3, f"boxscore_{game_id}",
                  game_id=game_id)


def passes_jogador(player_id, temporada, tipo, data=None, team_id=GSW_TEAM_ID):
    """playerdashptpass de um jogador (num dia específico ou na temporada)."""
    from nba_api.stats.endpoints import playerdashptpass
    sufixo = data.replace("/", "-") if data else "temporada"
    kwargs = dict(player_id=player_id, team_id=team_id, season=temporada,
                  season_type_all_star=tipo, per_mode_simple="Totals")
    if data:
        kwargs.update(date_from_nullable=data, date_to_nullable=data)
    return chamar(playerdashptpass.PlayerDashPtPass,
                  f"passes_{player_id}_{temporada}_{sufixo}", **kwargs)


def play_by_play(game_id):
    from nba_api.stats.endpoints import playbyplayv3
    return chamar(playbyplayv3.PlayByPlayV3, f"pbp_{game_id}", game_id=game_id)


def log_time(temporada, tipo="Regular Season", team_id=GSW_TEAM_ID):
    from nba_api.stats.endpoints import teamgamelog
    sufixo = tipo.replace(" ", "")
    dados = chamar(teamgamelog.TeamGameLog, f"teamlog_{team_id}_{temporada}_{sufixo}",
                   team_id=team_id, season=temporada, season_type_all_star=tipo)
    return resultset_df(dados, "TeamGameLog")


def stats_jogadores_temporada(temporada, tipo="Regular Season", team_id=GSW_TEAM_ID):
    """Totais da temporada por jogador do time (GP, MIN, PTS)."""
    from nba_api.stats.endpoints import leaguedashplayerstats
    sufixo = tipo.replace(" ", "")
    dados = chamar(leaguedashplayerstats.LeagueDashPlayerStats,
                   f"leaguedash_{team_id}_{temporada}_{sufixo}",
                   season=temporada, season_type_all_star=tipo,
                   team_id_nullable=team_id, per_mode_detailed="Totals")
    return resultset_df(dados, "LeagueDashPlayerStats")


def elenco(temporada, team_id=GSW_TEAM_ID):
    """Elenco do time na temporada (traz a POSIÇÃO de cada jogador)."""
    from nba_api.stats.endpoints import commonteamroster
    dados = chamar(commonteamroster.CommonTeamRoster, f"elenco_{team_id}_{temporada}",
                   team_id=team_id, season=temporada)
    return resultset_df(dados, "CommonTeamRoster")


def passes_time_dia(data, temporada, tipo="Regular Season", team_id=GSW_TEAM_ID):
    """teamdashptpass num dia: total de passes feitos/recebidos por jogador do time."""
    from nba_api.stats.endpoints import teamdashptpass
    return chamar(teamdashptpass.TeamDashPtPass,
                  f"passes_time_{team_id}_{data.replace('/', '-')}",
                  team_id=team_id, season=temporada, season_type_all_star=tipo,
                  per_mode_simple="Totals", date_from_nullable=data, date_to_nullable=data)


# ---------------------------------------------------------------- limpeza

def _minutos(valor):
    """'34:54' -> 34.9 ; '' -> 0.0"""
    if not valor:
        return 0.0
    m, s = str(valor).split(":")
    return int(m) + int(s) / 60


def _arestas(dados_por_jogador, ids_validos):
    """Junta os PassesMade de vários jogadores numa lista de arestas.

    Devolve (arestas_dentro, arestas_fora): passes para companheiros que estão
    no conjunto de nós e passes para quem está fora (descartados, mas contados).
    """
    linhas = []
    for pid, dados in dados_por_jogador.items():
        df = resultset_df(dados, "PassesMade")
        for _, r in df.iterrows():
            linhas.append({
                "origem_id": int(pid),
                "destino_id": int(r["PASS_TEAMMATE_PLAYER_ID"]),
                "destino_nome_api": r["PASS_TO"],
                "jogos_passador": int(r["G"]),
                "passes": float(r["PASS"]),
                "assistencias": float(r["AST"]),
                "fgm": float(r["FGM"]),
                "fga": float(r["FGA"]),
            })
    df = pd.DataFrame(linhas)
    dentro = df[df["destino_id"].isin(ids_validos)].reset_index(drop=True)
    fora = df[~df["destino_id"].isin(ids_validos)].reset_index(drop=True)
    return dentro, fora


def coletar_tudo(nome="Gui Santos", distribuicao=True):
    """Pipeline completo de coleta + limpeza. Grava CSVs em data/processed/."""
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # 1) jogador e jogo do recorde
    jogador = achar_jogador(nome)
    log = log_carreira(jogador["id"])
    log.to_csv(PROCESSED / "log_carreira_gui.csv", index=False)
    rec = jogo_recorde(log)
    game_id, temporada, tipo = rec["Game_ID"], rec["SEASON"], rec["SEASON_TYPE"]
    data = pd.to_datetime(rec["GAME_DATE"]).strftime("%m/%d/%Y")
    pd.DataFrame([{
        "player_id": jogador["id"], "jogador": jogador["full_name"], "game_id": game_id,
        "data": data, "temporada": temporada, "tipo": tipo, "confronto": rec["MATCHUP"],
        "resultado": rec["WL"], "pontos": rec["PTS"], "minutos": rec["MIN"],
    }]).to_csv(PROCESSED / "jogo_recorde.csv", index=False)

    # 2) quem entrou em quadra (nós) + atributos
    box = box_score(game_id)["boxScoreTraditional"]
    time_gsw = box["homeTeam"] if box["homeTeam"]["teamId"] == GSW_TEAM_ID else box["awayTeam"]
    adversario = box["awayTeam"] if time_gsw is box["homeTeam"] else box["homeTeam"]
    pos = elenco(temporada).set_index("PLAYER_ID")["POSITION"].to_dict()
    jog = []
    for i, p in enumerate(time_gsw["players"]):
        st = p["statistics"]
        jog.append({
            "player_id": p["personId"], "nome": f"{p['firstName']} {p['familyName']}",
            "posicao": pos.get(p["personId"], p["position"]),
            "titular": i < 5, "minutos": round(_minutos(st["minutes"]), 2),
            "pontos": st["points"], "assistencias": st["assists"],
            "rebotes": st["reboundsTotal"], "fga": st["fieldGoalsAttempted"],
            "fgm": st["fieldGoalsMade"],
            "comentario": p.get("comment", ""),
        })
    jog = pd.DataFrame(jog)
    jog["jogou"] = jog["minutos"] > 0
    jog.to_csv(PROCESSED / "jogadores_jogo.csv", index=False)
    pd.DataFrame([{"time": time_gsw["teamTricode"], "pontos": time_gsw["statistics"]["points"],
                   "adversario": adversario["teamTricode"],
                   "pontos_adversario": adversario["statistics"]["points"]}]
                 ).to_csv(PROCESSED / "placar.csv", index=False)
    em_quadra = jog.loc[jog["jogou"], "player_id"].tolist()

    # 3) rede de passes do jogo (um request por jogador, DateFrom = DateTo = dia)
    dados_jogo = {pid: passes_jogador(pid, temporada, tipo, data=data) for pid in em_quadra}
    ar_jogo, fora_jogo = _arestas(dados_jogo, em_quadra)
    ar_jogo.to_csv(PROCESSED / "arestas_jogo.csv", index=False)

    # checagem de consistência: PassesMade (A->B) x PassesReceived (B<-A)
    rec_linhas = []
    for pid, d in dados_jogo.items():
        r = resultset_df(d, "PassesReceived")
        for _, x in r.iterrows():
            rec_linhas.append({"origem_id": int(x["PASS_TEAMMATE_PLAYER_ID"]),
                               "destino_id": int(pid), "passes_recebido": float(x["PASS"])})
    cheque = ar_jogo.merge(pd.DataFrame(rec_linhas), on=["origem_id", "destino_id"], how="outer")
    cheque.to_csv(PROCESSED / "checagem_feito_x_recebido.csv", index=False)

    # 4) rede de referência: temporada inteira, mesmos jogadores
    dados_temp = {pid: passes_jogador(pid, temporada, tipo) for pid in em_quadra}
    ar_temp, fora_temp = _arestas(dados_temp, em_quadra)
    ar_temp.to_csv(PROCESSED / "arestas_temporada.csv", index=False)
    fora_temp.to_csv(PROCESSED / "arestas_temporada_fora_da_rede.csv", index=False)

    # passes RECEBIDOS por cada jogador, de qualquer passador (inclusive quem
    # está fora da rede), com os arremessos (FGA/FGM) que vieram logo após o passe
    for rotulo, dados in [("jogo", dados_jogo), ("temporada", dados_temp)]:
        linhas = []
        for pid, d in dados.items():
            r = resultset_df(d, "PassesReceived")
            for _, x in r.iterrows():
                linhas.append({"recebedor_id": int(pid),
                               "passador_id": int(x["PASS_TEAMMATE_PLAYER_ID"]),
                               "passador": x["PASS_FROM"], "passes": float(x["PASS"]),
                               "assistencias": float(x["AST"]), "fgm": float(x["FGM"]),
                               "fga": float(x["FGA"])})
        pd.DataFrame(linhas).to_csv(PROCESSED / f"recebidos_{rotulo}.csv", index=False)

    st = stats_jogadores_temporada(temporada, tipo)
    st = st[st["PLAYER_ID"].isin(em_quadra)][["PLAYER_ID", "PLAYER_NAME", "GP", "MIN", "PTS",
                                              "FGM", "FGA", "AST"]]
    st.columns = ["player_id", "nome", "jogos", "minutos", "pontos", "fgm", "fga", "assistencias"]
    st.to_csv(PROCESSED / "jogadores_temporada.csv", index=False)

    # 5) (melhoria) distribuição: passes do Gui em TODOS os jogos dele na temporada
    if distribuicao:
        jogos_temp = log[(log["SEASON"] == temporada) & (log["SEASON_TYPE"] == tipo)]
        linhas = []
        for _, g in jogos_temp.iterrows():
            dia = pd.to_datetime(g["GAME_DATE"]).strftime("%m/%d/%Y")
            try:
                d = passes_jogador(jogador["id"], temporada, tipo, data=dia)
                t = passes_time_dia(dia, temporada, tipo)
            except RuntimeError as erro:  # bloqueio persistente: pula e segue
                print(f"  jogo de {dia} ignorado: {erro}")
                continue
            feitos = resultset_df(d, "PassesMade")["PASS"].sum()
            recebidos = resultset_df(d, "PassesReceived")["PASS"].sum()
            time_total = resultset_df(t, "PassesMade")["PASS"].sum()
            linhas.append({"game_id": g["Game_ID"], "data": dia, "confronto": g["MATCHUP"],
                           "minutos": g["MIN"], "pontos": g["PTS"], "fga": g["FGA"],
                           "passes_feitos": feitos, "passes_recebidos": recebidos,
                           "passes_time": time_total})
        pd.DataFrame(linhas).to_csv(PROCESSED / "gui_por_jogo.csv", index=False)

    return {"jogo_fora": fora_jogo, "temporada_fora": fora_temp}
