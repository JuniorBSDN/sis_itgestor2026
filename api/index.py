from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import json

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)

# Inicialização do Firebase
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)

db = firestore.client()

# --- MÓDULO: ATIVOS ---
@app.route('/api/ativos', methods=['GET', 'POST'])
def gerenciar_ativos():
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/ativos/<id_ativo>', methods=['DELETE'])
def excluir_ativo(id_ativo):
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


# --- MÓDULO: RELATOS ---
@app.route('/api/relatos', methods=['GET', 'POST'])
def gerenciar_relatos():
    return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/')
def home():
    return "API Central de TI rodando!"

@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()
            dados['status'] = dados.get('status', 'Pendente')
            dados['tecnico_responsavel'] = None
            dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
            dados['data_busca'] = agora.strftime("%Y-%m-%d")
            db.collection('atividades').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            data_filtro = request.args.get('data')
            if data_filtro:
                query = db.collection('atividades').where('data_busca', '==', data_filtro)
            else:
                query = db.collection('atividades').limit(100)

            docs = query.stream()
            atividades = []
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id
                atividades.append(item)

            atividades.sort(key=lambda x: x.get('data_registro', ''), reverse=True)
            return jsonify(atividades), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/status_rat/<id_doc>', methods=['PATCH'])
def atualizar_status_rat(id_doc):
    try:
        dados = request.json
        update_data = {}

        if 'status' in dados:
            update_data['status'] = dados['status']
        
        if dados.get('status') == 'Concluido':
            # Usa o nome enviado ou um padrão
            update_data['tecnico_responsavel'] = dados.get('tecnico_responsavel', 'Técnico Externo')
            update_data['data_conclusao'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        elif dados.get('status') == 'Pendente':
            update_data['tecnico_responsavel'] = None

        db.collection('atividades').document(id_doc).update(update_data)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
