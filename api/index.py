import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURAÇÃO FIREBASE ---
# Certifique-se de que o arquivo .json das credenciais está na mesma pasta que este script
# Substitua 'firebase-key.json' pelo nome do seu arquivo de credenciais
cred = credentials.Certificate('FIREBASE_CREDENTIALS')
firebase_admin.initialize_app(cred)
db = firestore.client()


# ==========================================
# 1. ATIVOS (ativos.html e rat_ativos.html)
# ==========================================

@app.route('/api/ativos', methods=['POST'])
def salvar_ativo():
    """Salva ou Atualiza um ativo usando id_ativo como chave única."""
    try:
        dados = request.json
        id_doc = str(dados.get('id_ativo')).strip()

        if not id_doc or id_doc == "undefined":
            return jsonify({"status": "erro", "mensagem": "ID do Ativo é obrigatório"}), 400

        # Adiciona timestamp de atualização
        dados['ultima_modificacao'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # document().set com merge=True permite atualizar campos existentes ou criar novos
        db.collection('ativos').document(id_doc).set(dados, merge=True)
        return jsonify({"status": "sucesso", "mensagem": "Ativo salvo com sucesso!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/ativos', methods=['GET'])
def listar_ativos():
    """Retorna todos os ativos para o relatório rat_ativos.html."""
    try:
        docs = db.collection('ativos').stream()
        ativos = [doc.to_dict() for doc in docs]
        return jsonify({"status": "sucesso", "ativos": ativos})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/ativos/<id_ativo>', methods=['GET'])
def buscar_ativo_especifico(id_ativo):
    """Busca dados de um ativo para preencher o formulário de edição."""
    try:
        doc = db.collection('ativos').document(id_ativo).get()
        if doc.exists:
            return jsonify({"status": "sucesso", "ativo": doc.to_dict()})
        return jsonify({"status": "erro", "mensagem": "Ativo não encontrado"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/ativos/<id_ativo>', methods=['DELETE'])
def excluir_ativo(id_ativo):
    """Exclui o ativo permanentemente."""
    try:
        db.collection('ativos').document(str(id_ativo)).delete()
        return jsonify({"status": "sucesso", "mensagem": "Ativo removido"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ==========================================
# 2. ATIVIDADES / CHAMADOS (atividade.html e ret_atividades.html)
# ==========================================

@app.route('/api/atividades', methods=['POST'])
def salvar_atividade():
    """Registra uma nova atividade de TI."""
    try:
        dados = request.json
        # Se não houver ID (novo chamado), o Firestore gera um automático
        id_doc = dados.get('id') or db.collection('atividades').document().id
        dados['id'] = id_doc

        if 'data_registro' not in dados:
            dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M")

        db.collection('atividades').document(id_doc).set(dados, merge=True)
        return jsonify({"status": "sucesso", "id": id_doc})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/atividades', methods=['GET'])
def listar_atividades():
    """Lista todas as atividades para o relatório ret_atividades.html."""
    try:
        # Ordena por data de registro (mais recentes primeiro)
        docs = db.collection('atividades').order_by('data_registro', direction=firestore.Query.DESCENDING).stream()
        atividades = [doc.to_dict() for doc in docs]
        return jsonify({"status": "sucesso", "atividades": atividades})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ==========================================
# 3. APP HOSPITAL SEGURO (app.html e rat_app.html)
# ==========================================

@app.route('/api/relatos', methods=['POST'])
def salvar_relato():
    """Recebe sugestões ou incidentes do canal de melhoria."""
    try:
        dados = request.json
        id_doc = db.collection('relatos').document().id
        dados['id'] = id_doc
        dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Garante que campos vazios de anonimato sejam tratados
        if dados.get('is_anonimo'):
            dados['nome'] = "Anônimo"
            dados['cargo'] = "N/A"

        db.collection('relatos').document(id_doc).set(dados)
        return jsonify({"status": "sucesso", "mensagem": "Relato enviado com sucesso!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/relatos', methods=['GET'])
def listar_relatos():
    """Lista relatos para o painel rat_app.html."""
    try:
        docs = db.collection('relatos').order_by('data_registro', direction=firestore.Query.DESCENDING).stream()
        relatos = [doc.to_dict() for doc in docs]
        return jsonify({"status": "sucesso", "relatos": relatos})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == '__main__':
    # debug=True facilita o desenvolvimento para ver erros no terminal
    app.run(debug=True, port=5000)
