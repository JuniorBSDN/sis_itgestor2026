from flask import Flask, request, jsonify, send_file
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from io import BytesIO
from datetime import datetime
import pytz

app = Flask(__name__)

@app.route("/api/login", methods=["POST"])
def login():
    try:
        dados = request.json
        senha_enviada = dados.get("senha")
        # Puxa a variável de ambiente configurada no Vercel
        senha_correta = os.environ.get("SENHA_SUPORTE")

        if senha_enviada == senha_correta:
            # Retorna um token simples para o frontend armazenar
            return jsonify({"status": "sucesso", "token": "acesso_permitido_hmv"}), 200
        else:
            return jsonify({"status": "erro", "mensagem": "Senha incorreta"}), 401
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 1. INICIALIZAÇÃO DO FIREBASE (Mantendo sua lógica original de segurança)
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

# ==========================================
# 2. ROTA: CADASTRAR / ALTERAR ATIVO (Restaurada)
# ==========================================
@app.route("/api/ativos", methods=["POST"])
def gerenciar_ativo():
    try:
        dados = request.json
        id_ativo = dados.get("id_ativo")

        if not id_ativo:
            return jsonify({"status": "erro", "mensagem": "ID do Ativo é obrigatório"}), 400

        # Adiciona timestamp de atualização
        dados["ultima_atualizacao"] = firestore.SERVER_TIMESTAMP

        # .set com merge=True garante que ele crie ou atualize sem apagar campos antigos
        db.collection("ativos").document(id_ativo).set(dados, merge=True)

        return jsonify({"status": "sucesso", "mensagem": "Registro processado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ==========================================
# 3. ROTA: BUSCAR ATIVO (Restaurada para o seu index.html)
# ==========================================
@app.route("/api/ativos/<id_busca>", methods=["GET"])
def buscar_ativo(id_busca):
    try:
        doc_ref = db.collection("ativos").document(id_busca).get()
        if doc_ref.exists:
            # Retorna exatamente o formato que seu formulário espera
            return jsonify({"status": "sucesso", "ativo": doc_ref.to_dict()}), 200
        else:
            return jsonify({"status": "erro", "mensagem": "Ativo não encontrado"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ==========================================
# 4. ROTA: LISTAR TODOS OS ATIVOS (Para rat.html)
# ==========================================
@app.route("/api/lista-ativos", methods=["GET"])
def listar_todos_ativos():
    try:
        ativos_ref = db.collection("ativos").stream()
        lista = [doc.to_dict() for doc in ativos_ref]
        return jsonify({"status": "sucesso", "ativos": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ==========================================
# 5. NOVO MÓDULO: REGISTRAR ATIVIDADE (Chamados)
# ==========================================
@app.route("/api/atividades", methods=["POST"])
def cadastrar_atividade():
    try:
        dados = request.json
        fuso = pytz.timezone('America/Belem')
        agora = datetime.now(fuso)

        dados["data_registro"] = agora.strftime("%d/%m/%Y")
        dados["hora_registro"] = agora.strftime("%H:%M:%S")
        dados["timestamp"] = firestore.SERVER_TIMESTAMP

        # Salva em uma coleção separada
        db.collection("atividades").add(dados)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ==========================================
# 6. NOVO MÓDULO: LISTAR ATIVIDADES (Para rat_ativos.html)
# ==========================================
@app.route("/api/lista-atividades", methods=["GET"])
def listar_atividades():
    try:
        # Busca atividades sem obrigatoriedade de índice inicial
        docs = db.collection("atividades").stream()
        lista = [doc.to_dict() for doc in docs]
        return jsonify({"status": "sucesso", "atividades": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# ==========================================
# 7. RELATÓRIO TXT E EXCLUSÃO (Mantidos)
# ==========================================
@app.route("/api/ativos/<id_delete>", methods=["DELETE"])
def excluir_ativo(id_delete):
    try:
        db.collection("ativos").document(id_delete).delete()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro"}), 500

@app.route("/api/relatorio/txt", methods=["GET"])
def gerar_relatorio_txt():
    try:
        ativos_ref = db.collection("ativos").stream()
        fuso = pytz.timezone('America/Belem')
        data_hora = datetime.now(fuso).strftime('%d/%m/%Y %H:%M')
        relatorio = f"RELATÓRIO TI - {data_hora}\n" + "="*30 + "\n"
        for doc in ativos_ref:
            a = doc.to_dict()
            relatorio += f"ID: {a.get('id_ativo')} | SETOR: {a.get('setor')}\n"
        return send_file(BytesIO(relatorio.encode('utf-8')), mimetype="text/plain", as_attachment=True, download_name="relatorio.txt")
    except: return "Erro ao gerar", 500

# Rota que alimenta a Lupa (Envia os dados + ID único do documento)
@app.route("/api/lista-atividades-full", methods=["GET"])
def listar_atividades_full():
    try:
        docs = db.collection("atividades").stream()
        lista = []
        for doc in docs:
            item = doc.to_dict()
            item["doc_id"] = doc.id  # Esse ID é o que permite a alteração/exclusão
            lista.append(item)
        return jsonify({"status": "sucesso", "atividades": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# Rota para Atualizar (PUT) - Usada após você selecionar na lupa e editar
@app.route("/api/atividades/update/<id_doc>", methods=["PUT"])
def atualizar_atividade(id_doc):
    try:
        dados = request.json
        # Removemos o doc_id dos dados para não salvar o ID dentro do próprio documento
        if "doc_id" in dados: del dados["doc_id"]
        
        db.collection("atividades").document(id_doc).update(dados)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# Rota para Excluir (DELETE)
@app.route("/api/atividades/<id_doc>", methods=["DELETE"])
def excluir_atividade_chamado(id_doc):
    try:
        db.collection("atividades").document(id_doc).delete()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro"}), 500

if __name__ == "__main__":
    app.run(debug=True)
