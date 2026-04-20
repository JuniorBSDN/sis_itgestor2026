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

# --- INICIALIZAÇÃO DO FIREBASE ---
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        try:
            cred = credentials.Certificate(json.loads(cred_json))
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"Erro ao carregar credenciais: {e}")

db = firestore.client()

# --- MÓDULO: ATIVOS ---
@app.route('/api/ativos', methods=['GET', 'POST'])
def gerenciar_ativos():
    if request.method == 'POST':
        try:
            dados = request.json
            id_ativo = dados.get('id_ativo')
            db.collection('ativos').document(id_ativo).set(dados)
            return jsonify({"status": "sucesso"}), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500
    elif request.method == 'GET':
        try:
            docs = db.collection('ativos').stream()
            ativos = [doc.to_dict() for doc in docs]
            return jsonify(ativos), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/ativos/<id_ativo>', methods=['DELETE'])
def excluir_ativo(id_ativo):
    try:
        db.collection('ativos').document(id_ativo).delete()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- MÓDULO: HELPDESK (RAT) ---
@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()
            dados['status'] = dados.get('status', 'Pendente')
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
                query = db.collection('atividades').limit(50)
            
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

# ROTA DE ATUALIZAÇÃO CONSOLIDADA (STATUS + TÉCNICO + DATA)
# --- ROTA: ATUALIZAR STATUS (FINALIZAR) ---
@app.route('/api/status_rat/<id_doc>', methods=['PATCH'])
def atualizar_status_rat(id_doc):
    try:
        dados = request.json # Recebe: status, tecnico_responsavel, data_conclusao
        db.collection('atividades').document(id_doc).update(dados)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

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
        try:
            docs = db.collection('relatos').stream()
            relatos = [doc.to_dict() for doc in docs]
            return jsonify(relatos), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- MÓDULO: RESÍDUOS HOSPITALARES ---
@app.route('/api/residuos', methods=['GET', 'POST'])
def gerenciar_residuos():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()
            if 'data_registro' not in dados:
                dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
            if 'data_busca' not in dados:
                dados['data_busca'] = agora.strftime("%Y-%m-%d")
            db.collection('residuos').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500
    elif request.method == 'GET':
        try:
            data_filtro = request.args.get('data')
            query = db.collection('residuos').where('data_busca', '==', data_filtro) if data_filtro else db.collection('residuos').limit(100)
            docs = query.stream()
            residuos = []
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id
                residuos.append(item)
            residuos.sort(key=lambda x: x.get('data_registro', ''), reverse=True)
            return jsonify(residuos), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/residuos/<id_doc>', methods=['PATCH', 'DELETE'])
def acoes_residuos(id_doc):
    try:
        if request.method == 'PATCH':
            db.collection('residuos').document(id_doc).update(request.json)
        elif request.method == 'DELETE':
            db.collection('residuos').document(id_doc).delete()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- MÓDULO: FLUXO DE PACIENTES (SENHAS) ---
@app.route('/api/fila', methods=['GET', 'POST'])
def gerenciar_fila():
    if request.method == 'POST':
        try:
            dados = request.json
            dados['status'] = 'aguardando'
            dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            dados['timestamp'] = firestore.SERVER_TIMESTAMP
            db.collection('fila').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500
    elif request.method == 'GET':
        try:
            docs = db.collection('fila').where('status', '==', 'aguardando').order_by('timestamp').stream()
            fila = [doc.to_dict() for doc in docs]
            return jsonify(fila), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/chamar_proximo', methods=['PATCH'])
def chamar_proximo():
    try:
        query = db.collection('fila').where('status', '==', 'aguardando').order_by('timestamp').limit(1).get()
        if not query:
            return jsonify({"status": "vazio", "mensagem": "Ninguém na fila"}), 200
        doc = query[0]
        db.collection('fila').document(doc.id).update({
            "status": "chamado",
            "data_chamada": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "chamada_timestamp": firestore.SERVER_TIMESTAMP
        })
        return jsonify({"status": "sucesso", "senha": doc.to_dict().get('senha')}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/ultima_chamada', methods=['GET'])
def ultima_chamada():
    try:
        query = db.collection('fila').where('status', '==', 'chamado').order_by('chamada_timestamp', direction=firestore.Query.DESCENDING).limit(1).get()
        if query: return jsonify(query[0].to_dict()), 200
        return jsonify({}), 204
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/')
def home():
    return "API Central de TI - Instituto Impar rodando!"

if __name__ == '__main__':
    app.run(debug=True)
