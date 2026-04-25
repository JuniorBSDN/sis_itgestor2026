from fpdf import FPDF
from io import BytesIO
import smtplib
from email.mime.mixed import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
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


# --- MÓDULO: HELPDESK (RAT) - CORREÇÃO SEM ÍNDICE ---
@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()
            dados['status'] = dados.get('status', 'Pendente')
            dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
            # Campo para o filtro por dia
            dados['data_busca'] = agora.strftime("%Y-%m-%d")
            db.collection('atividades').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            data_filtro = request.args.get('data')
            # Busca simples: Apenas filtro (não exige índice composto)
            if data_filtro:
                query = db.collection('atividades').where('data_busca', '==', data_filtro)
            else:
                query = db.collection('atividades').limit(50)

            docs = query.stream()

            # Converte documentos para lista e inclui o ID
            atividades = []
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id
                atividades.append(item)

            # ORDENAÇÃO MANUAL: Substitui o 'order_by' do Firebase para evitar erro de índice
            atividades.sort(key=lambda x: x.get('data_registro', ''), reverse=True)

            return jsonify(atividades), 200
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

            # Padronização de datas para busca e exibição
            if 'data_registro' not in dados:
                dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")

            # Campo crucial para o filtro do JS (formato YYYY-MM-DD)
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

            # Ordenação manual para evitar erro de índice composto no Firebase
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


# ----MECANISMO QUE GERA SENHAS
# --- MÓDULO: FLUXO DE PACIENTES (SENHAS) ---

@app.route('/api/fila', methods=['GET', 'POST'])
def gerenciar_fila():
    if request.method == 'POST':
        try:
            dados = request.json
            agora = datetime.now()

            # Formatação da Senha (Ex: M-001)
            # Você pode enviar a senha pronta do Totem ou gerar aqui
            dados['status'] = 'aguardando'
            dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")
            dados['timestamp'] = firestore.SERVER_TIMESTAMP  # Para ordenação precisa

            db.collection('fila').add(dados)
            return jsonify({"status": "sucesso"}), 201
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500

    elif request.method == 'GET':
        try:
            # Busca pacientes aguardando para o Widget do Médico
            docs = db.collection('fila').where('status', '==', 'aguardando').order_by('timestamp').stream()
            fila = [doc.to_dict() for doc in docs]
            return jsonify(fila), 200
        except Exception as e:
            return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/chamar_proximo', methods=['PATCH'])
def chamar_proximo():
    try:
        # 1. Pega o paciente mais antigo que está aguardando
        query = db.collection('fila').where('status', '==', 'aguardando').order_by('timestamp').limit(1).get()

        if not query:
            return jsonify({"status": "vazio", "mensagem": "Ninguém na fila"}), 200

        doc = query[0]
        dados_chamada = {
            "status": "chamado",
            "data_chamada": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "chamada_timestamp": firestore.SERVER_TIMESTAMP  # Isso dispara a TV e o Rodapé
        }

        db.collection('fila').document(doc.id).update(dados_chamada)

        return jsonify({
            "status": "sucesso",
            "senha": doc.to_dict().get('senha')
        }), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/ultima_chamada', methods=['GET'])
def ultima_chamada():
    try:
        # Endpoint para a TV ou Rodapé consultar via Polling (se não usar Listener)
        query = db.collection('fila').where('status', '==', 'chamado').order_by('chamada_timestamp',
                                                                                direction=firestore.Query.DESCENDING).limit(
            1).get()
        if query:
            return jsonify(query[0].to_dict()), 200
        return jsonify({}), 204
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# --- ATUALIZAÇÃO DE STATUS ---
@app.route('/api/status_rat/<id_doc>', methods=['PATCH'])
def atualizar_status_rat(id_doc):
    try:
        dados = request.json
        novo_status = dados.get('status')
        db.collection('atividades').document(id_doc).update({'status': novo_status})
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# --- CONFIGURAÇÕES DE APOIO (Certificados) ---
GMAIL_USER = "juniordomundo@gmail.com"
GMAIL_PASS = os.environ.get('GMAIL_PASS')
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD')


def gerar_pdf_buffer(nome, cpf):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()

    # Borda Decorativa
    pdf.set_draw_color(0, 86, 179)
    pdf.set_line_width(2)
    pdf.rect(10, 10, 277, 190)

    # Título Principal
    pdf.set_font('Arial', 'B', 32)
    pdf.set_text_color(0, 86, 179)
    pdf.ln(50)
    pdf.cell(0, 20, 'CERTIFICADO DE CONCLUSÃO', ln=True, align='C')

    # Texto do Certificado
    pdf.set_font('Arial', '', 18)
    pdf.set_text_color(50)
    pdf.ln(10)
    pdf.cell(0, 10, 'Certificamos para os devidos fins que o(a) profissional', ln=True, align='C')

    pdf.set_font('Arial', 'B', 22)
    pdf.set_text_color(0)
    pdf.cell(0, 15, nome.upper(), ln=True, align='C')

    pdf.set_font('Arial', '', 14)
    pdf.ln(10)
    pdf.multi_cell(0, 10,
                   'Concluiu com êxito o treinamento de HELPDESK HMV,\nestando apto(a) a utilizar as ferramentas de suporte da instituição.',
                   align='C')

    pdf.ln(20)
    pdf.set_font('Arial', 'I', 10)
    data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, f'Autenticado digitalmente em: {data_emissao} | CPF: {cpf}', ln=True, align='C')

    return pdf.output(dest='S').encode('latin-1')


def enviar_email_certificado(destinatario, nome, pdf_bytes):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = destinatario
    msg['Subject'] = "Certificado de Treinamento - HMV"

    corpo = f"Olá {nome},\n\nParabéns por concluir o treinamento. Segue em anexo o seu certificado de conclusão."
    msg.attach(MIMEText(corpo, 'plain'))

    anexo = MIMEApplication(pdf_bytes, Name=f"Certificado_{nome}.pdf")
    anexo['Content-Disposition'] = f'attachment; filename="Certificado_{nome}.pdf"'
    msg.attach(anexo)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)


# --- MÓDULO: TREINAMENTOS & CERTIFICADOS ---

@app.route('/api/registrar', methods=['POST'])
def registrar_treinamento():
    try:
        dados = request.json
        nome = dados.get('nome')
        cpf = dados.get('cpf')
        email = dados.get('email')
        acao = dados.get('acao')

        # Gravação no Firestore
        doc_ref = db.collection('treinamentos').document()
        doc_ref.set({
            'nome': nome,
            'cpf': cpf,
            'email': email,
            'data_conclusao': datetime.now()
        })

        # Processamento do Certificado
        if acao == 'email':
            pdf_bytes = gerar_pdf_buffer(nome, cpf)
            enviar_email_certificado(email, nome, pdf_bytes)

        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        # O que você digitou no prompt
        senha_digitada = str(data.get('senha', '')).strip()
        
        # O que está salvo na Vercel (Forçado para Texto)
        admin_pass = str(os.environ.get('ADMIN_PASSWORD', '')).strip()

        # Comparação direta de texto
        if senha_digitada == admin_pass and admin_pass != "":
            return jsonify({"status": "sucesso"}), 200
        else:
            return jsonify({"status": "erro", "mensagem": "Acesso Negado"}), 401
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/listar', methods=['GET'])
def listar_treinamentos():
    try:
        docs = db.collection('treinamentos').order_by('data_conclusao', direction=firestore.Query.DESCENDING).stream()
        lista = []
        for doc in docs:
            d = doc.to_dict()
            lista.append({
                "nome": d.get('nome'),
                "cpf": d.get('cpf'),
                "email": d.get('email'),
                "data_conclusao": d.get('data_conclusao').strftime("%d/%m/%Y %H:%M")
            })
        return jsonify(lista), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
        
@app.route('/api/certificado_download')
def certificado_download():
    nome = request.args.get('nome')
    cpf = request.args.get('cpf')
    try:
        pdf_bytes = gerar_pdf_buffer(nome, cpf)
        return send_file(
            BytesIO(pdf_bytes),
            download_name=f"Certificado_{cpf}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        return str(e), 500

@app.route('/')
def home():
    return "API Central de TI rodando!"




if __name__ == '__main__':
    app.run(debug=True)
