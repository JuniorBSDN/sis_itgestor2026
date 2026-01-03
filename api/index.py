from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

app = Flask(__name__)
# Garante que acentos e caracteres especiais sejam exibidos corretamente
app.config['JSON_AS_ASCII'] = False 
CORS(app)

# Inicialização do Firebase
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        print("Erro: Variável FIREBASE_CREDENTIALS não encontrada.")

db = firestore.client()

# --- MÓDULO: ATIVOS ---
@app.route('/api/ativos', methods=['GET', 'POST'])
def gerenciar_ativos():
    if request.method == 'POST':
        try:
            dados = request.json
            id_ativo = dados.get('id_ativo')
            if not id_ativo:
                return jsonify({"status": "erro", "mensagem": "ID do ativo é obrigatório"}), 400
            db.collection('ativos').document(id_ativo).set(dados)
            return jsonify({"status": "sucesso"}), 200
        except Exception as e: 
            return jsonify({"status": "erro", "mensagem": str(e)}), 500
    elif request.method == 'GET':
        docs = db.collection('ativos').stream()
        return jsonify([doc.to_dict() for doc in docs]), 200

# --- MÓDULO: RELATOS ---
@app.route('/api/relatos', methods=['GET', 'POST'])
def gerenciar_relatos():
    if request.method == 'POST':
        try:
            dados = request.json
            if 'data_registro' not in dados:
                dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            db.collection('relatos').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500
    elif request.method == 'GET':
        docs = db.collection('relatos').stream()
        return jsonify([doc.to_dict() for doc in docs]), 200

# --- MÓDULO: HELPDESK (RAT) ---
@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()
            # Garante campos obrigatórios para o funcionamento do painel
            dados['status'] = dados.get('status', 'Pendente')
            dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
            # Campo crucial para o filtro de busca por data
            dados['data_busca'] = agora.strftime("%Y-%m-%d")

            db.collection('atividades').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            data_filtro = request.args.get('data') # Recebe a data do frontend
            query = db.collection('atividades')
            
            # Aplica o filtro se a data for fornecida, caso contrário traz tudo
            if data_filtro:
                query = query.where('data_busca', '==', data_filtro)
            
            # Importante: Exige o índice composto no Firestore (data_busca + data_registro)
            docs = query.order_by('data_registro', direction=firestore.Query.DESCENDING).stream()
            
            atividades = []
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id # ID necessário para a rota PATCH
                atividades.append(item)
            return jsonify(atividades), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ROTA PARA ATUALIZAR STATUS DO HELPDESK
@app.route('/api/helpdesk/<id_doc>', methods=['PATCH'])
def atualizar_status(id_doc):
    try:
        dados = request.json
        novo_status = dados.get('status')
        if not novo_status:
            return jsonify({"status": "erro", "mensagem": "Novo status não informado"}), 400
            
        db.collection('atividades').document(id_doc).update({'status': novo_status})
        return jsonify({"status": "sucesso"}), 200
    except Exception as e: 
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
