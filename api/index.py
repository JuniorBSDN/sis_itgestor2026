import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- CONFIGURAÇÃO DO FIREBASE ---
# Certifique-se de que o arquivo .json das credenciais esteja na mesma pasta
try:
    cred_path = "FIREBASE_CREDENTIALS.json" # Nome do seu arquivo de chaves
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("🔥 Conexão com Firestore estabelecida com sucesso!")
except Exception as e:
    print(f"❌ Erro ao conectar ao Firebase: {e}")

# --- ROTAS DE NAVEGAÇÃO ---
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def servir_arquivos(path):
    return send_from_directory('.', path)

# --- API: ATIVOS (ativos.html / rat_ativos.html) ---
@app.route('/api/ativos', methods=['GET', 'POST'])
def gerenciar_ativos():
    col_ativos = db.collection('ativos')
    
    if request.method == 'POST':
        dados = request.json
        id_ativo = dados.get('id_ativo')
        if not id_ativo:
            return jsonify({"status": "erro", "mensagem": "ID do Ativo é obrigatório"}), 400
        
        # Salva ou Atualiza no Firestore usando o ID do ativo como nome do documento
        col_ativos.document(id_ativo).set(dados)
        return jsonify({"status": "sucesso", "mensagem": "Ativo salvo no Firestore"}), 201

    # GET: Retorna todos os ativos
    docs = col_ativos.stream()
    lista_ativos = [doc.to_dict() for doc in docs]
    return jsonify({"status": "sucesso", "ativos": lista_ativos})

@app.route('/api/ativos/<id_ativo>', methods=['DELETE'])
def excluir_ativo(id_ativo):
    db.collection('ativos').document(id_ativo).delete()
    return jsonify({"status": "sucesso", "mensagem": "Ativo removido"}), 200

# --- API: ATIVIDADES (atividade.html / ret_atividades.html) ---
@app.route('/api/atividades', methods=['GET', 'POST'])
def gerenciar_atividades():
    col_atividades = db.collection('atividades')
    
    if request.method == 'POST':
        dados = request.json
        dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        # Gera um ID automático para a atividade
        col_atividades.add(dados)
        return jsonify({"status": "sucesso"}), 201

    # GET: Busca atividades ordenadas por data
    docs = col_atividades.order_by('data_registro', direction=firestore.Query.DESCENDING).stream()
    lista = [doc.to_dict() for doc in docs]
    return jsonify({"status": "sucesso", "atividades": lista})

# --- API: RELATOS APP SEGURO (app.html / rat_app.html) ---
@app.route('/api/relatos', methods=['GET', 'POST'])
def gerenciar_relatos():
    col_relatos = db.collection('relatos')
    
    if request.method == 'POST':
        dados = request.json
        dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        col_relatos.add(dados)
        return jsonify({"status": "sucesso"}), 201

    docs = col_relatos.order_by('data_registro', direction=firestore.Query.DESCENDING).stream()
    lista = [doc.to_dict() for doc in docs]
    return jsonify({"status": "sucesso", "relatos": lista})

if __name__ == '__main__':
    # Em produção (como Vercel/PythonAnywhere), o app costuma rodar via WSGI
    app.run(debug=True, port=5000)
