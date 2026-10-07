# API externa: REST Countries (https://restcountries.com)

import os
import sqlite3
import requests
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request

load_dotenv()

app = Flask(__name__)
app.json.ensure_ascii = False
app.json.sort_keys = False

DB_PATH = 'countries.db'

URL_API = "https://api.restcountries.com/countries/v5"
CAMPOS_API = (
    "codes.alpha_3,names.common,names.official,capitals,"
    "region,subregion,population,area,languages"
)
LIMITE_POR_PAGINA = 100
API_KEY = os.environ.get("RESTCOUNTRIES_API_KEY")

REGIOES_VALIDAS = {"africa", "americas", "antarctic", "asia", "europe", "oceania"}
CAMPOS_OBRIGATORIOS = ["nome", "regiao", "populacao"]
CAMPOS_TEXTO = ["nome", "nome_oficial", "capital", "regiao", "subregiao", "idiomas"]
CAMPOS_NUMERICOS = ["populacao", "area"]

# Banco de dados
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(_exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def criar_tabela():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paises (
                codigo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                nome_oficial TEXT,
                capital TEXT,
                regiao TEXT NOT NULL,
                subregiao TEXT,
                populacao INTEGER NOT NULL,
                area REAL,
                idiomas TEXT
            )
        """)

def linha_para_dict(linha):
    return dict(linha) if linha else None

# Coleta
def transformar_pais(item):
    nomes = item.get("names") or {}
    capitais = item.get("capitals") or []
    idiomas = [i.get("name") for i in item.get("languages") or [] if i.get("name")]
    return (
        (item.get("codes") or {}).get("alpha_3"),
        nomes.get("common"),
        nomes.get("official"),
        capitais[0].get("name") if capitais else None,
        item.get("region"),
        item.get("subregion"),
        item.get("population") or 0,
        (item.get("area") or {}).get("kilometers"),
        ", ".join(sorted(idiomas)) if idiomas else None,
    )

def buscar_paises():
    """Percorre as páginas da API. Retorna None se o formato da resposta for inesperado."""
    paises = []
    offset = 0
    while True:
        response = requests.get(
            URL_API,
            params={"limit": LIMITE_POR_PAGINA, "offset": offset, "response_fields": CAMPOS_API},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30,
        )
        response.raise_for_status()
        dados = response.json()
        objetos = dados.get("data", {}).get("objects") if isinstance(dados, dict) else None
        if not isinstance(objetos, list):
            return None
        paises.extend(objetos)
        if len(objetos) < LIMITE_POR_PAGINA:
            return paises
        offset += LIMITE_POR_PAGINA

@app.route("/coletas", methods=["POST"])
def criar_coleta():
    if not API_KEY:
        return jsonify({
            "erro": "Chave da API não configurada",
            "detalhes": "Defina a variável de ambiente RESTCOUNTRIES_API_KEY",
        }), 500

    try:
        dados = buscar_paises()

    except requests.exceptions.Timeout:
        return jsonify({"erro": "Tempo limite de conexão excedido."}), 504

    except requests.exceptions.HTTPError as e:
        return jsonify({
            "erro": "A API externa retornou erro",
            "status_api_externa": e.response.status_code if e.response is not None else None,
        }), 502

    except ValueError:
        return jsonify({"erro": "A API externa retornou um conteúdo que não é JSON válido"}), 502

    except requests.exceptions.RequestException as e:
        return jsonify({"erro": "Erro ao conectar à API externa", "detalhes": str(e)}), 502

    if not isinstance(dados, list):
        return jsonify({"erro": "A API externa retornou um conteúdo inesperado"}), 502

    linhas = [linha for linha in map(transformar_pais, dados) if linha[0]]

    db = get_db()
    antes = db.execute("SELECT COUNT(*) FROM paises").fetchone()[0]
    db.executemany(
        "INSERT OR IGNORE INTO paises VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", linhas
    )
    db.commit()
    depois = db.execute("SELECT COUNT(*) FROM paises").fetchone()[0]

    return jsonify({
        "mensagem": "Coleta realizada com sucesso",
        "total_registros_antes": antes,
        "total_registros_depois": depois,
        "total_registros_inseridos": depois - antes,
    }), 201


# Validacao
def validar_corpo(corpo):
    if not isinstance(corpo, dict):
        return ["O corpo da requisição deve ser um objeto JSON"]

    erros = []
    for campo in CAMPOS_OBRIGATORIOS:
        if corpo.get(campo) in (None, ""):
            erros.append(f"Campo obrigatório ausente: '{campo}'")

    for campo in CAMPOS_TEXTO:
        if campo in corpo and corpo[campo] is not None and not isinstance(corpo[campo], str):
            erros.append(f"'{campo}' deve ser texto")

    for campo in CAMPOS_NUMERICOS:
        valor = corpo.get(campo)
        if valor is None:
            continue
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
            erros.append(f"'{campo}' deve ser um número maior ou igual a zero")

    return erros

def valores_do_corpo(corpo):
    return (
        corpo.get("nome"),
        corpo.get("nome_oficial"),
        corpo.get("capital"),
        corpo.get("regiao"),
        corpo.get("subregiao"),
        corpo.get("populacao"),
        corpo.get("area"),
        corpo.get("idiomas"),
    )


#CRUD

@app.route("/paises", methods=["GET"])
def listar_paises():
    linhas = get_db().execute("SELECT * FROM paises").fetchall()
    return jsonify({"total": len(linhas), "paises": [dict(l) for l in linhas]}), 200

@app.route("/paises/<codigo>", methods=["GET"])
def obter_pais(codigo):
    linha = get_db().execute("SELECT * FROM paises WHERE codigo = ?", (codigo.upper(),)).fetchone()
    if linha is None:
        return jsonify({"erro": f"País '{codigo.upper()}' não encontrado"}), 404
    return jsonify(linha_para_dict(linha)), 200

@app.route("/paises", methods=["POST"])
def criar_pais():
    corpo = request.get_json(silent=True)
    erros = validar_corpo(corpo)
 
    codigo = corpo.get("codigo") if isinstance(corpo, dict) else None
    if not isinstance(codigo, str) or len(codigo) != 3 or not codigo.isalpha():
        erros.insert(0, "'codigo' é obrigatório e deve ter 3 letras (ex: BRA)")
 
    if erros:
        return jsonify({"erro": "Dados inválidos", "detalhes": erros}), 400
 
    codigo = codigo.upper()
    db = get_db()
    if db.execute("SELECT 1 FROM paises WHERE codigo = ?", (codigo,)).fetchone():
        return jsonify({"erro": f"Já existe um país com o código '{codigo}'"}), 409
 
    db.execute(
        "INSERT INTO paises VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (codigo, *valores_do_corpo(corpo)),
    )
    db.commit()
    criado = db.execute("SELECT * FROM paises WHERE codigo = ?", (codigo,)).fetchone()
    return jsonify(linha_para_dict(criado)), 201, {"Location": f"/paises/{codigo}"}
 
 
@app.route("/paises/<codigo>", methods=["PUT"])
def atualizar_pais(codigo):
    codigo = codigo.upper()
    db = get_db()
    if not db.execute("SELECT 1 FROM paises WHERE codigo = ?", (codigo,)).fetchone():
        return jsonify({"erro": f"País '{codigo}' não encontrado"}), 404
 
    corpo = request.get_json(silent=True)
    erros = validar_corpo(corpo)
    if isinstance(corpo, dict) and "codigo" in corpo and str(corpo["codigo"]).upper() != codigo:
        erros.append("O 'codigo' do corpo não pode ser diferente do código da URL")
    if erros:
        return jsonify({"erro": "Dados inválidos", "detalhes": erros}), 400
 
    db.execute(
        """
        UPDATE paises
           SET nome = ?, nome_oficial = ?, capital = ?, regiao = ?,
               subregiao = ?, populacao = ?, area = ?, idiomas = ?
         WHERE codigo = ?
        """,
        (*valores_do_corpo(corpo), codigo),
    )
    db.commit()
    atualizado = db.execute("SELECT * FROM paises WHERE codigo = ?", (codigo,)).fetchone()
    return jsonify(linha_para_dict(atualizado)), 200
 
 
@app.route("/paises/<codigo>", methods=["DELETE"])
def remover_pais(codigo):
    codigo = codigo.upper()
    db = get_db()
    cursor = db.execute("DELETE FROM paises WHERE codigo = ?", (codigo,))
    db.commit()
    if cursor.rowcount == 0:
        return jsonify({"erro": f"País '{codigo}' não encontrado"}), 404
    return jsonify({"mensagem": f"País '{codigo}' removido com sucesso"}), 200

# Filtros
 
@app.route("/regioes/<regiao>/paises", methods=["GET"])
def filtrar_por_regiao(regiao):
    """Filtro 1: países de uma região (Africa, Americas, Antarctic, Asia, Europe, Oceania)."""
    if regiao.lower() not in REGIOES_VALIDAS:
        return jsonify({
            "erro": f"Região inválida: '{regiao}'",
            "regioes_validas": sorted(r.capitalize() for r in REGIOES_VALIDAS),
        }), 400
 
    linhas = get_db().execute(
        "SELECT * FROM paises WHERE LOWER(regiao) = ? ORDER BY nome", (regiao.lower(),)
    ).fetchall()
    return jsonify({
        "regiao": regiao.capitalize(),
        "total": len(linhas),
        "paises": [dict(l) for l in linhas],
    }), 200
 
 
@app.route("/paises/populacao", methods=["GET"])
def filtrar_por_populacao():
    """Filtro 2: países com população dentro de uma faixa (?min=...&max=...)."""
    minimo_txt = request.args.get("min")
    maximo_txt = request.args.get("max")
 
    if minimo_txt is None and maximo_txt is None:
        return jsonify({
            "erro": "Informe ao menos um dos parâmetros 'min' ou 'max'",
            "exemplo": "/paises/populacao?min=1000000&max=10000000",
        }), 400
 
    try:
        minimo = int(minimo_txt) if minimo_txt is not None else 0
        maximo = int(maximo_txt) if maximo_txt is not None else None
    except ValueError:
        return jsonify({"erro": "'min' e 'max' devem ser números inteiros"}), 400
 
    if minimo < 0 or (maximo is not None and maximo < 0):
        return jsonify({"erro": "'min' e 'max' não podem ser negativos"}), 400
    if maximo is not None and minimo > maximo:
        return jsonify({"erro": "'min' não pode ser maior que 'max'"}), 400
 
    sql = "SELECT * FROM paises WHERE populacao >= ?"
    params = [minimo]
    if maximo is not None:
        sql += " AND populacao <= ?"
        params.append(maximo)
    sql += " ORDER BY populacao DESC"
 
    linhas = get_db().execute(sql, params).fetchall()
    return jsonify({
        "faixa": {"min": minimo, "max": maximo},
        "total": len(linhas),
        "paises": [dict(l) for l in linhas],
    }), 200
 
 
 
@app.errorhandler(404)
def rota_nao_encontrada(_e):
    return jsonify({"erro": "Rota nao encontrada"}), 404
 
 
@app.errorhandler(405)
def metodo_nao_permitido(_e):
    return jsonify({"erro": "Método HTTP não permitido para esta rota"}), 405
 
 
@app.errorhandler(500)
def erro_interno(_e):
    return jsonify({"erro": "Erro interno do servidor"}), 500
 
 
criar_tabela()
 
if __name__ == "__main__":
    app.run(debug=True)
 