from flask import Flask, request, jsonify, send_file
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from io import BytesIO
from datetime import datetime
import pytz

app = Flask(__name__)

# --- CONFIGURAÇÃO DO FIREBASE ---
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
    else:
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)

db = firestore.client()
fuso_belem = pytz.timezone('America/Belem')

# --- ROTA DE LOGIN ---
@app.route("/api/login", methods=["POST"])
def login():
    try:
        dados = request.json
        senha_enviada = dados.get("senha")
        senha_correta = os.environ.get("SENHA_SUPORTE")
        if senha_enviada == senha_correta:
            return jsonify({"status": "sucesso", "token": "acesso_permitido_hmv"}), 200
        return jsonify({"status": "erro", "mensagem": "Senha incorreta"}), 401
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- GESTÃO DE ATIVOS (Inventário) ---
@app.route("/api/ativos", methods=["POST"])
def gerenciar_ativo():
    try:
        dados = request.json
        id_ativo = dados.get("id_ativo")
        if not id_ativo:
            return jsonify({"status": "erro", "mensagem": "ID do Ativo obrigatório"}), 400
        
        dados["ultima_atualizacao"] = datetime.now(fuso_belem).strftime("%d/%m/%Y %H:%M:%S")
        db.collection("ativos").document(id_ativo).set(dados, merge=True)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ROTA CRUCIAL: Esta é a que carrega a lista no rat_ativos.html
@app.route("/api/lista-ativos", methods=["GET"])
def listar_ativos():
    try:
        # Busca todos os documentos da coleção ativos
        docs = db.collection("ativos").stream()
        lista = [doc.to_dict() for doc in docs]
        return jsonify({"status": "sucesso", "ativos": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/ativos/<id_busca>", methods=["GET"])
def buscar_ativo(id_busca):
    try:
        doc = db.collection("ativos").document(id_busca).get()
        if doc.exists:
            return jsonify({"status": "sucesso", "ativo": doc.to_dict()}), 200
        return jsonify({"status": "erro", "mensagem": "Ativo não encontrado"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- GESTÃO DE ATIVIDADES (Chamados/RAT) ---
@app.route("/api/helpdesk", methods=["POST"])
@app.route("/api/atividades", methods=["POST"])
def cadastrar_atividade():
    try:
        dados = request.json
        agora = datetime.now(fuso_belem)
        dados["data_registro"] = agora.strftime("%d/%m/%Y")
        dados["hora_registro"] = agora.strftime("%H:%M:%S")
        dados["timestamp"] = firestore.SERVER_TIMESTAMP
        db.collection("atividades").add(dados)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/lista-atividades-full", methods=["GET"])
def listar_atividades_full():
    try:
        # Ordena para que os mais recentes apareçam primeiro
        docs = db.collection("atividades").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        lista = []
        for doc in docs:
            item = doc.to_dict()
            item["doc_id"] = doc.id
            if "timestamp" in item: del item["timestamp"]
            lista.append(item)
        return jsonify({"status": "sucesso", "atividades": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
