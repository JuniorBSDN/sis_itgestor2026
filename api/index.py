from flask import Flask, request, jsonify, send_file
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from io import BytesIO
from datetime import datetime
import pytz

app = Flask(__name__)

# 1. INICIALIZAÇÃO DO FIREBASE
if not firebase_admin._apps:
    # No Vercel, a variável FIREBASE_CREDENTIALS deve conter o JSON completo da chave
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
    else:
        # Fallback para desenvolvimento local caso o arquivo exista
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)

db = firestore.client()


# ----------------------------------------------------------------
# 6. ROTA: CADASTRAR RELATO DE FALHA/MELHORIA (POST)
# ----------------------------------------------------------------
@app.route("/api/relatos", methods=["POST"])
def cadastrar_relato():
    try:
        dados = request.json
        fuso = pytz.timezone('America/Belem')
        agora = datetime.now(fuso)

        # Determina se é anônimo ou identificado
        is_anonimo = dados.get("is_anonimo", True)

        doc_relato = {
            "setor": dados.get("setor"),
            "tipo_falha": dados.get("tipo"),
            "descricao": dados.get("descricao"),
            "data_registro": agora.strftime("%d/%m/%Y"),
            "hora_registro": agora.strftime("%H:%M:%S"),
            "timestamp": firestore.SERVER_TIMESTAMP,
            "status": "Pendente",
            "is_anonimo": is_anonimo
        }

        # Se não for anônimo, inclui os dados do autor
        if not is_anonimo:
            doc_relato["autor_nome"] = dados.get("nome", "Não informado")
            doc_relato["autor_cargo"] = dados.get("cargo", "Não informado")
        else:
            doc_relato["autor_nome"] = "Anônimo"

        # Salva na coleção exclusiva de relatos
        db.collection("relatos").add(doc_relato)

        return jsonify({"status": "sucesso", "mensagem": "Relato enviado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# 2. ROTA: CADASTRAR OU ALTERAR ATIVO (POST)
@app.route("/api/ativos", methods=["POST"])
def gerenciar_ativo():
    try:
        dados = request.json
        id_ativo = dados.get("id_ativo")

        if not id_ativo:
            return jsonify({"status": "erro", "mensagem": "ID do Ativo é obrigatório"}), 400

        # Mapeamento completo de campos para o Firestore
        doc_data = {
            "id_ativo": id_ativo,
            "patrimonio": dados.get("patrimonio"),
            "ip_rede": dados.get("ip_rede"),
            "anydesk_id": dados.get("anydesk_id"),
            "anydesk_senha": dados.get("anydesk_senha"),
            "setor": dados.get("setor"),
            "sala_bloco": dados.get("sala_bloco"),
            "criticidade": dados.get("criticidade"),
            "itens_requeridos": dados.get("itens_requeridos", []),
            "tipo": dados.get("tipo"),
            "hostname": dados.get("hostname"),
            "configuracao": dados.get("configuracao"),
            "sistema_operacional": dados.get("sistema_operacional"),
            "status_saude": dados.get("status_saude"),
            "compatibilidade": dados.get("compatibilidade"),
            "observacoes": dados.get("observacoes"),
            "ultima_atualizacao": firestore.SERVER_TIMESTAMP
        }

        # .set com merge=True cria se não existir ou atualiza se já existir
        db.collection("ativos").document(id_ativo).set(doc_data, merge=True)

        return jsonify({"status": "sucesso", "mensagem": "Registro processado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# 3. ROTA: BUSCAR ATIVO POR ID (GET)
@app.route("/api/ativos/<id_busca>", methods=["GET"])
def buscar_ativo(id_busca):
    try:
        doc_ref = db.collection("ativos").document(id_busca).get()
        if doc_ref.exists:
            return jsonify({"status": "sucesso", "ativo": doc_ref.to_dict()}), 200
        else:
            return jsonify({"status": "erro", "mensagem": "Ativo não encontrado"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# 4. ROTA: EXCLUIR ATIVO (DELETE)
@app.route("/api/ativos/<id_delete>", methods=["DELETE"])
def excluir_ativo(id_delete):
    try:
        db.collection("ativos").document(id_delete).delete()
        return jsonify({"status": "sucesso", "mensagem": "Ativo removido com sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# 5. ROTA: GERAR RELATÓRIO TXT COMPLETO
@app.route("/api/relatorio/txt", methods=["GET"])
def gerar_relatorio_txt():
    try:
        ativos_ref = db.collection("ativos").stream()
        fuso = pytz.timezone('America/Belem')
        data_hora = datetime.now(fuso).strftime('%d/%m/%Y %H:%M')

        relatorio = f"### GESTÃO DE ATIVOS / IDENTIFICAÇÃO - {data_hora} ###\n"
        relatorio += "=" * 50 + "\n\n"

        for doc in ativos_ref:
            a = doc.to_dict()
            relatorio += f"*USUARIO: {a.get('usuario', '--')}\n"
            relatorio += f"*SETOR: {a.get('setor', '--')}\n"
            relatorio += f"*ID: {a.get('id_ativo', '--')}\n"
            relatorio += f"*EQUIPAMENTO: {a.get('equipamento', '--')}\n"
            relatorio += f"*MODELO: {a.get('modelo', '--')}\n"
            relatorio += f"*N/S: {a.get('ns_serial', '--')}\n"
            relatorio += f"*PATRIMONIO: {a.get('patrimonio', '--')}\n"
            relatorio += f"*HARDWARE: {a.get('hardware', '--')}\n"
            relatorio += f"*SOFTWARE: {a.get('software', '--')}\n"
            relatorio += f"*ID SUPORTE: {a.get('id_suporte', '--')}\n"
            relatorio += f"*IPV4: {a.get('ipv4', '--')}\n"
            relatorio += f"*HOSTNAME: {a.get('hostname', '--')}\n"
            relatorio += f"*STATUS FISICO: {a.get('status_fisico', '--')}\n"
            relatorio += f"*ITENS: {', '.join(a.get('itens_requeridos', [])) if isinstance(a.get('itens_requeridos'), list) else '--'}\n"
            relatorio += f"*OBS: {a.get('obs', '--')}\n"
            relatorio += "-" * 30 + "\n\n"

        return send_file(
            BytesIO(relatorio.encode('utf-8')),
            mimetype="text/plain",
            as_attachment=True,
            download_name=f"relatorio_ativos_{datetime.now().strftime('%Y%m%d')}.txt"
        )
    except Exception as e:
        return f"Erro ao gerar: {str(e)}", 500


@app.route("/api/lista-ativos", methods=["GET"])
def listar_todos_ativos():
    try:
        ativos_ref = db.collection("ativos").stream()
        lista = []
        for doc in ativos_ref:
            lista.append(doc.to_dict())

        return jsonify({"status": "sucesso", "ativos": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


from datetime import datetime
import pytz


@app.route("/api/atividades", methods=["POST"])
def cadastrar_atividade():
    try:
        dados = request.json
        # Ajuste para o fuso horário local (ex: Belém/PA)
        fuso = pytz.timezone('America/Belem')
        agora = datetime.now(fuso)

        dados["data_registro"] = agora.strftime("%d/%m/%Y")
        dados["hora_registro"] = agora.strftime("%H:%M:%S")
        dados["timestamp"] = firestore.SERVER_TIMESTAMP

        db.collection("atividades").add(dados)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/rat_app", methods=["GET"])
def listar_relatos_painel():
    try:
        # Busca os relatos na coleção "relatos" do Firestore
        relatos_ref = db.collection("relatos").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        lista = []
        for doc in relatos_ref:
            lista.append(doc.to_dict())
        
        return jsonify({"status": "sucesso", "relatos": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/api/lista-relatos", methods=["GET"])
def listar_relatos_hospitalares():
    try:
        # Busca os documentos na coleção "relatos" ordenando pelos mais recentes
        relatos_ref = db.collection("relatos").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        lista = []
        for doc in relatos_ref:
            lista.append(doc.to_dict())
        
        return jsonify({"status": "sucesso", "relatos": lista}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
