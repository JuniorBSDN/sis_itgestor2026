from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Inicialização do Firebase
if not firebase_admin._apps:
    # Tenta carregar das variáveis de ambiente do Vercel
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        print("Erro: Variável FIREBASE_CREDENTIALS não encontrada.")

db = firestore.client()


# --- ROTAS PARA ATIVOS ---

@app.route('/api/ativos', methods=['GET', 'POST'])
def gerenciar_ativos():
    if request.method == 'POST':
        try:
            dados = request.json
            id_ativo = dados.get('id_ativo')
            if not id_ativo:
                return jsonify({"status": "erro", "mensagem": "ID do ativo é obrigatório"}), 400

            # Salva ou atualiza usando o ID fornecido como nome do documento
            db.collection('ativos').document(id_ativo).set(dados)
            return jsonify({"status": "sucesso", "mensagem": "Ativo salvo com sucesso"}), 200
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


# --- ROTAS PARA ATIVIDADES (CHAMADOS) ---

@app.route('/api/atividades', methods=['GET', 'POST'])
def gerenciar_atividades():
    if request.method == 'POST':
        try:
            dados = request.json
            dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            db.collection('atividades').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            docs = db.collection('atividades').order_by('data_registro', direction=firestore.Query.DESCENDING).stream()
            atividades = [doc.to_dict() for doc in docs]
            return jsonify(atividades), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500


# --- ROTAS PARA APP HOSPITAL SEGURO (RELATOS) ---

@app.route('/api/relatos', methods=['GET', 'POST'])  # Adicionado POST aqui
def gerenciar_relatos():
    if request.method == 'POST':
        try:
            dados = request.json
            # Adiciona data de registro se não vier do front
            if 'data_registro' not in dados:
                dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            # Salva na coleção 'relatos'
            db.collection('relatos').add(dados)
            return jsonify({"status": "sucesso", "mensagem": "Relato enviado com sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            docs = db.collection('relatos').stream()
            relatos = [doc.to_dict() for doc in docs]
            return jsonify(relatos), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()
            dados['status'] = 'Pendente'
            # Data completa para exibição
            dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
            # Campo extra apenas com a data (AAAA-MM-DD) para o filtro diário
            dados['data_busca'] = agora.strftime("%Y-%m-%d")
            
            db.collection('atividades').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            # Captura a data enviada pelo front (ex: ?data=2024-05-20)
            data_filtro = request.args.get('data')
            
            # Se não houver data na URL, assume o dia de hoje
            if not data_filtro:
                data_filtro = datetime.now().strftime("%Y-%m-%d")

            # Filtra pela data de busca para o relatório diário
            docs = db.collection('atividades')\
                     .where('data_busca', '==', data_filtro)\
                     .order_by('data_registro', direction=firestore.Query.DESCENDING)\
                     .stream()
            
            atividades = []
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id # ID essencial para a atualização funcionar
                atividades.append(item)
            return jsonify(atividades), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ROTA DE ATUALIZAÇÃO CONFORME O SEU EXEMPLO
@app.route('/api/helpdesk/<id_doc>', methods=['PATCH'])
def atualizar_status(id_doc):
    try:
        dados = request.json
        novo_status = dados.get('status')
        db.collection('atividades').document(id_doc).update({'status': novo_status})
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
# Rota padrão para teste
@app.route('/')
def home():
    return "API Central de TI rodando!"


if __name__ == '__main__':
    app.run(debug=True)
