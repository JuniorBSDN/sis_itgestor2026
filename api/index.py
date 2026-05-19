import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
import pandas as pd
import os
import io

# Configuração exata para ler a sua pasta public
app = Flask(__name__, template_folder='public', static_folder='public')
app.config['JSON_AS_ASCII'] = False
CORS(app)

TZ_PA = timezone(timedelta(hours=-3))

if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
    else:
        if os.path.exists("chave-firebase.json"):
            cred = credentials.Certificate("chave-firebase.json")
            firebase_admin.initialize_app(cred)

db = firestore.client()
COLECAO_AVALIACOES = "avaliacoes"

@app.route('/totem')
def abrir_totem():
    return render_template('feed.html')

@app.route('/admin')
def abrir_admin():
    return render_template('feedAdmin.html')

@app.route('/api/avaliacoes', methods=['POST'])
def salvar_avaliacao():
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"status": "erro", "mensagem": "Dados ausentes"}), 400

        agora = datetime.now(TZ_PA)

        payload = {
            "setor": str(dados.get("setor", "Não Informado")),
            "nota": int(dados.get("nota", 0)),
            "rotulo_nota": str(dados.get("rotulo_nota", "Sem Rótulo")),
            "motivos": list(dados.get("motivos", [])),
            "timestamp": agora.isoformat(),
            "data_busca": agora.strftime("%Y-%m-%d")
        }

        db.collection(COLECAO_AVALIACOES).add(payload)
        return jsonify({"status": "sucesso"}), 201
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 400

@app.route('/api/indicadores', methods=['GET'])
def buscar_indicadores():
    try:
        docs = db.collection(COLECAO_AVALIACOES).stream()

        total_votos = 0
        soma_notas = 0
        distribuicao_notas = {"Péssimo": 0, "Ruim": 0, "Regular": 0, "Bom": 0, "Excelente": 0}

        # Alinhado perfeitamente com os valores gerados pelo feed.html
        setores = {
            "Pronto Atendimento": {"soma": 0, "votos": 0, "media": 0},
            "Ambulatório / Consultas": {"soma": 0, "votos": 0, "media": 0},
            "Exames / Laboratório": {"soma": 0, "votos": 0, "media": 0},
            "Internação": {"soma": 0, "votos": 0, "media": 0}
        }

        for doc in docs:
            data = doc.to_dict()
            nota = int(data.get("nota", 0))
            rotulo = data.get("rotulo_nota")
            setor = data.get("setor")

            total_votos += 1
            soma_notas += nota

            if rotulo in distribuicao_notas:
                distribuicao_notas[rotulo] += 1

            if setor in setores:
                setores[setor]["votos"] += 1
                setores[setor]["soma"] += nota

        for s in setores:
            if setores[s]["votos"] > 0:
                setores[s]["media"] = round(setores[s]["soma"] / setores[s]["votos"], 2)

        media_geral = (soma_notas / total_votos) if total_votos > 0 else 0

        resposta = {
            "total_votos": total_votos,
            "media_geral": round(media_geral, 2),
            "distribuicao_notas": distribuicao_notas,
            "setores": setores
        }
        return jsonify(resposta), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- PRESERVAÇÃO INTEGRAL DOS SEUS OUTROS MÓDULOS ---
def gerar_pdf_bytes(nome, cpf):
    cpf_limpo = "".join(filter(str.isdigit, str(cpf)))
    cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}" if len(cpf_limpo) == 11 else cpf_limpo
    pdf = FPDF()
    pdf.add_page()
    pdf.rect(5, 5, 200, 287)
    pdf.set_font("Arial", 'B', 12)
    pdf.ln(10)
    instituicao = "INSTITUTO IMPAR & HOSPITAL MUNICIPAL DE VIGIA DE NAZARE - RAIMUNDO VASCONCELOS"
    pdf.multi_cell(0, 8, instituicao.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.line(20, 35, 190, 35)
    pdf.set_font("Arial", 'B', 20)
    pdf.ln(40)
    pdf.cell(200, 10, "CERTIFICADO DE CONCLUSAO", ln=True, align='C')
    pdf.ln(20)
    pdf.set_font("Arial", size=14)
    data_atual = datetime.now(TZ_PA).strftime('%d/%m/%Y')
    texto = (f"Certificamos que o colaborador(a) {nome.upper()}, inscrito sob o CPF {cpf_formatado}, "
             f"concluiu com exito o Treinamento de HelpDesk HMV no dia {data_atual}.")
    pdf.multi_cell(0, 10, texto.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(40)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, "Validade Permanente - Sistema de Gestao IT HMV", ln=True, align='C')
    return io.BytesIO(pdf.output(dest='S').encode('latin-1'))

def enviar_email(destinatario, nome, pdf_buffer):
    try:
        remetente = os.environ.get('EMAIL_REMETENTE')
        senha = os.environ.get('EMAIL_SENHA')
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destinatario
        msg['Subject'] = f"Certificado HelpDesk HMV - {nome}"
        corpo = f"Ola {nome},\n\nSegue em anexo o seu certificado de conclusao do treinamento de HelpDesk."
        msg.attach(MIMEText(corpo, 'plain'))
        anexo = MIMEApplication(pdf_buffer.getvalue(), Name=f"Certificado_{nome}.pdf")
        anexo['Content-Disposition'] = f'attachment; filename="Certificado_{nome}.pdf"'
        msg.attach(anexo)
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(remetente, senha)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

@app.route('/api/registrar', methods=['POST'])
def registrar():
    try:
        dados = request.get_json()
        if not dados or 'nome' not in dados:
            return jsonify({"status": "erro", "mensagem": "Dados invalidos"}), 400
        dados['data_conclusao'] = datetime.now(TZ_PA).strftime('%d/%m/%Y %H:%M')
        if 'cpf' in dados:
            dados['cpf'] = "".join(filter(str.isdigit, str(dados['cpf'])))
        db.collection('treinamentos').add(dados)
        if dados.get('acao') == 'email' and dados.get('email'):
            pdf_buf = gerar_pdf_bytes(dados['nome'], dados.get('cpf', '000'))
            enviar_email(dados['email'], dados['nome'], pdf_buf)
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/listar', methods=['GET'])
def listar():
    try:
        docs = db.collection('treinamentos').stream()
        lista = [doc.to_dict() for doc in docs]
        lista.sort(key=lambda x: x.get('data_conclusao', ''), reverse=True)
        return jsonify(lista), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/certificado_download', methods=['GET'])
def download():
    try:
        nome = request.args.get('nome', 'Colaborador')
        cpf = request.args.get('cpf', '000')
        pdf_buf = gerar_pdf_bytes(nome, cpf)
        pdf_buf.seek(0)
        return send_file(pdf_buf, as_attachment=True, download_name=f"Certificado_{nome}.pdf", mimetype='application/pdf')
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

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

@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now(TZ_PA)
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

@app.route('/api/relatos', methods=['GET', 'POST'])
def gerenciar_relatos():
    if request.method == 'POST':
        try:
            dados = request.json
            if 'data_registro' not in dados:
                dados['data_registro'] = datetime.now(TZ_PA).strftime("%d/%m/%Y %H:%M:%S")
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

@app.route('/api/residuos', methods=['GET', 'POST'])
def gerenciar_residuos():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now(TZ_PA)
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
            if data_filtro:
                query = db.collection('residuos').where('data_busca', '==', data_filtro)
            else:
                query = db.collection('residuos').limit(100)
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
            dados = request.json
            db.collection('residuos').document(id_doc).update(dados)
            return jsonify({"status": "sucesso"}), 200
        elif request.method == 'DELETE':
            db.collection('residuos').document(id_doc).delete()
            return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/fila', methods=['GET', 'POST'])
def gerenciar_fila():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now(TZ_PA)
            dados['status'] = 'aguardando'
            dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
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
            return jsonify({"status": "vazio"}), 200
        doc = query[0]
        dados_chamada = {
            "status": "chamado",
            "data_chamada": datetime.now(TZ_PA).strftime("%d/%m/%Y %H:%M:%S"),
            "chamada_timestamp": firestore.SERVER_TIMESTAMP
        }
        db.collection('fila').document(doc.id).update(dados_chamada)
        return jsonify({"status": "sucesso", "senha": doc.to_dict().get('senha')}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/ultima_chamada', methods=['GET'])
def ultima_chamada():
    try:
        query = db.collection('fila').where('status', '==', 'chamado').order_by('chamada_timestamp', direction=firestore.Query.DESCENDING).limit(1).get()
        if query:
            return jsonify(query[0].to_dict()), 200
        return jsonify({}), 204
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/status_rat/<id_doc>', methods=['PATCH'])
def atualizar_status_rat(id_doc):
    try:
        dados = request.json
        novo_status = dados.get('status')
        db.collection('atividades').document(id_doc).update({'status': novo_status})
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/')
def home():
    return "API centralizada ITGestor 2026 operacional."

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
