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

# --- MÓDULOS ATIVOS E RELATOS ---
@app.route('/api/ativos', methods=['GET', 'POST'])
def gerenciar_ativos():
    if request.method == 'POST':
        try:
            dados = request.json
            id_ativo = dados.get('id_ativo')
            db.collection('ativos').document(id_ativo).set(dados)
            return jsonify({"status": "sucesso"}), 200
        except Exception as e: return jsonify({"status": "erro", "mensagem": str(e)}), 500
    elif request.method == 'GET':
        docs = db.collection('ativos').stream()
        return jsonify([doc.to_dict() for doc in docs]), 200

@app.route('/api/relatos', methods=['GET', 'POST'])
def gerenciar_relatos():
    if request.method == 'POST':
        try:
            dados = request.json
            if 'data_registro' not in dados:
                dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            db.collection('relatos').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e: return jsonify({"status": "erro"}), 500
    elif request.method == 'GET':
        docs = db.collection('relatos').stream()
        return jsonify([doc.to_dict() for doc in docs]), 200

# --- MÓDULO HELPDESK (RAT) ---
@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()
            dados['status'] = 'Pendente'
            dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
            # Campo para o filtro por data
            dados['data_busca'] = agora.strftime("%Y-%m-%d")
            db.collection('atividades').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e: return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            data_filtro = request.args.get('data')
            if not data_filtro:
                data_filtro = datetime.now().strftime("%Y-%m-%d")

            # Tenta a busca filtrada e ordenada (Exige Índice Ativo)
            try:
                docs = db.collection('atividades') \
                    .where('data_busca', '==', data_filtro) \
                    .order_by('data_registro', direction=firestore.Query.DESCENDING) \
                    .stream()
                atividades = [dict(doc.to_dict(), id=doc.id) for doc in docs]
            except Exception:
                # Fallback: Se o índice falhar, traz os últimos 20 sem filtro para não travar a lista
                docs = db.collection('atividades').limit(20).stream()
                atividades = [dict(doc.to_dict(), id=doc.id) for doc in docs]

            return jsonify(atividades), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/helpdesk/<id_doc>', methods=['PATCH'])
def atualizar_status(id_doc):
    try:
        dados = request.json
        db.collection('atividades').document(id_doc).update({'status': dados.get('status')})
        return jsonify({"status": "sucesso"}), 200
    except Exception as e: return jsonify({"status": "erro"}), 500

if __name__ == '__main__':
    app.run(debug=True)
