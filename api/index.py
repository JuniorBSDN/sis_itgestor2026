from flask import Flask, request, jsonify, send_file
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from io import BytesIO
from datetime import datetime
import pytz

app = Flask(__name__)

# --- 1. CONFIGURAÇÃO E INICIALIZAÇÃO ---
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        # Para produção no Vercel
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        # Para desenvolvimento local
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)

db = firestore.client()
fuso_belem = pytz.timezone('America/Belem')

# --- 2. ROTA DE LOGIN ---
@app.route("/api/login", methods=["POST"])
def login():
    try:
        dados = request.json
        senha_enviada = dados.get("senha")
        senha_correta = os.environ.get("SENHA_SUPORTE", "#suportetihmv") # Default caso não configurado

        if senha_enviada == senha_correta:
            return jsonify({"status": "sucesso", "token": "acesso_permitido_hmv"}), 200
        return jsonify({"status": "erro", "mensagem": "Senha incorreta"}), 401
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- 3. GESTÃO DE ATIVOS (INVENTÁRIO) ---
@app.route("/api/ativos", methods=["POST"])
def gerenciar_ativo():
    try:
        dados = request.json
        id_ativo = dados.get("id_ativo")
        if not id_ativo:
            return jsonify({"status": "erro", "mensagem": "ID do Ativo é obrigatório"}), 400

        dados["ultima_atualizacao"] = datetime.now(fuso_belem).strftime("%d/%m/%Y %H:%M:%S")
        db.collection("ativos").document(id_ativo).set(dados, merge=True)
        return jsonify({"status": "sucesso", "mensagem": "Ativo guardado!"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/ativos/<id_busca>", methods=["GET"])
def buscar_ativo(id_busca):
    try:
        doc = db.collection("ativos").document(id_busca).get()
        if doc.exists:
            return jsonify({"status": "sucesso", "ativo": doc.to_dict()}), 200
        return jsonify({"status": "erro", "mensagem": "Não encontrado"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/ativos/<id_delete>", methods=["DELETE"])
def excluir_ativo(id_delete):
    try:
        db.collection("ativos").document(id_delete).delete()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/lista-ativos", methods=["GET"])
def listar_todos_ativos():
    try:
        docs = db.collection("ativos").stream()
        lista = [doc.to_dict() for doc in docs]
        return jsonify({"status": "sucesso", "ativos": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- 4. GESTÃO DE ATIVIDADES / HELPDESK (CHAMADOS) ---
# Esta rota unifica o que os seus ficheiros chamam de /api/helpdesk e /api/atividades
@app.route("/api/atividades", methods=["POST"])
@app.route("/api/helpdesk", methods=["POST"])
def cadastrar_atividade():
    try:
        dados = request.json
        agora = datetime.now(fuso_belem)
        
        dados["data_registro"] = agora.strftime("%d/%m/%Y")
        dados["hora_registro"] = agora.strftime("%H:%M:%S")
        dados["timestamp"] = firestore.SERVER_TIMESTAMP # Para ordenação precisa
        
        db.collection("atividades").add(dados)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/lista-atividades-full", methods=["GET"])
def listar_atividades_full():
    try:
        # Ordenado por data decrescente
        docs = db.collection("atividades").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        lista = []
        for doc in docs:
            item = doc.to_dict()
            item["doc_id"] = doc.id
            # Limpeza de timestamp para JSON
            if "timestamp" in item: del item["timestamp"]
            lista.append(item)
        return jsonify({"status": "sucesso", "atividades": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/atividades/update/<id_doc>", methods=["PUT"])
def atualizar_atividade(id_doc):
    try:
        dados = request.json
        if "doc_id" in dados: del dados["doc_id"]
        db.collection("atividades").document(id_doc).update(dados)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/atividades/<id_doc>", methods=["DELETE"])
def excluir_atividade_chamado(id_doc):
    try:
        db.collection("atividades").document(id_doc).delete()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- 5. RELATÓRIOS ---
@app.route("/api/relatorio/txt", methods=["GET"])
def gerar_relatorio_txt():
    try:
        ativos_ref = db.collection("ativos").stream()
        data_hora = datetime.now(fuso_belem).strftime('%d/%m/%Y %H:%M')
        
        relatorio = f"RELATÓRIO TI - {data_hora}\n" + "="*40 + "\n"
        for doc in ativos_ref:
            a = doc.to_dict()
            relatorio += f"ID: {a.get('id_ativo', '--')} | SETOR: {a.get('setor', '--')} | STATUS: {a.get('status_fisico', '--')}\n"
        
        return send_file(
            BytesIO(relatorio.encode('utf-8')), 
            mimetype="text/plain", 
            as_attachment=True, 
            download_name="relatorio_ativos.txt"
        )
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(debug=True)
