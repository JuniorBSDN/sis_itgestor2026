import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
import pandas as pd
import os
import io
from flask import send_file, request, jsonify
from datetime import datetime

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)

# Configuração de Fuso Horário (Vigia - Pará)
TZ_PA = timezone(timedelta(hours=-3))

# Inicialização do Firebase
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)

db = firestore.client()



# --- MÓDULO: ADMISSÃO HOSPITALAR (SISTGESTOR2026 - EXCEL LOCAL) ---

EXCEL_PATH = 'SISTGESTOR2026_ADMISSAO_LOG.xlsx'


def garantir_excel_existe():
    """Cria o arquivo Excel com cabeçalhos se ele não existir."""
    if not os.path.exists(EXCEL_PATH):
        colunas = [
            'rm', 'nome', 'documento', 'nascimento', 'sexo',
            'naturalidade', 'cor', 'estado_civil', 'telefone',
            'nome_mae', 'nome_pai', 'ocupacao', 'escolaridade',
            'responsavel', 'endereco', 'municipio', 'data_registro'
        ]
        df_vazio = pd.DataFrame(columns=colunas)
        df_vazio.to_excel(EXCEL_PATH, index=False)
        print(f"Arquivo {EXCEL_PATH} criado com sucesso.")


@app.route('/api/buscar_paciente', methods=['GET'])
def buscar_paciente():
    try:
        garantir_excel_existe()  # Verifica antes de buscar
        termo = request.args.get('q', '').upper()
        if not termo:
            return jsonify({"encontrado": False}), 200

        df = pd.read_excel(EXCEL_PATH)

        # Busca flexível
        mask = (
                df['nome'].astype(str).str.contains(termo, na=False, case=False) |
                df['documento'].astype(str).str.contains(termo, na=False) |
                df['rm'].astype(str).str.contains(termo, na=False)
        )

        resultado = df[mask].iloc[:1]

        if not resultado.empty:
            p = resultado.to_dict(orient='records')[0]
            # Limpa valores nulos para o JSON
            p = {k: ("" if pd.isna(v) else v) for k, v in p.items()}
            return jsonify({"encontrado": True, "paciente": p}), 200

        return jsonify({"encontrado": False}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/processar_admissao', methods=['POST'])
def processar_admissao():
    try:
        garantir_excel_existe()  # Verifica antes de salvar
        dados = request.json
        agora = datetime.now(TZ_PA)

        # Normalização para Caixa Alta (Padrão Hospitalar)
        for campo, valor in dados.items():
            if isinstance(valor, str):
                dados[campo] = valor.upper()

        # RM Automático caso seja novo
        if not dados.get('rm'):
            dados['rm'] = f"RM{agora.strftime('%Y%m%d%H%M%S')}"

        dados['data_registro'] = agora.strftime("%d/%m/%Y %H:%M:%S")

        df_novo = pd.DataFrame([dados])
        df_existente = pd.read_excel(EXCEL_PATH)

        # Se o paciente já existe (pelo RM), remove a linha antiga para atualizar
        if not df_existente.empty:
            df_existente = df_existente[df_existente['rm'] != dados['rm']]

        df_final = pd.concat([df_existente, df_novo], ignore_index=True)
        df_final.to_excel(EXCEL_PATH, index=False)

        return jsonify({
            "status": "sucesso",
            "rm": dados['rm']
        }), 201

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/api/imprimir_prontuario/<rm>', methods=['GET'])
def imprimir_prontuario(rm):
    try:
        garantir_excel_existe()
        df = pd.read_excel(EXCEL_PATH)
        resultado = df[df['rm'] == rm]

        if resultado.empty:
            return "Paciente não encontrado", 404

        p = resultado.iloc[0].to_dict()

        # PDF usando fpdf (já configurado no seu código central)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, "HOSPITAL MUNICIPAL DE VIGIA DE NAZARE", ln=True, align='C')
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(200, 8, "PRONTUARIO DE ADMISSAO DE URGENCIA", ln=True, align='C')
        pdf.ln(5)
        pdf.line(10, 32, 200, 32)

        pdf.set_font("Arial", size=10)
        pdf.ln(5)
        pdf.cell(0, 8, f"REGISTRO: {p.get('rm')} | DATA: {p.get('data_registro')}", ln=True)

        # Dados do Paciente em blocos
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 10, f"PACIENTE: {str(p.get('nome')).upper()}", border=1, ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(100, 10, f"DOC: {p.get('documento')}", border=1)
        pdf.cell(90, 10, f"NASCIMENTO: {p.get('nascimento')}", border=1, ln=True)
        pdf.cell(100, 10, f"MAE: {p.get('nome_mae')}", border=1)
        pdf.cell(90, 10, f"FONE: {p.get('telefone')}", border=1, ln=True)
        pdf.multi_cell(0, 10, f"ENDERECO: {p.get('endereco')}", border=1)

        pdf.ln(20)
        pdf.cell(0, 5, "________________________________________________", ln=True, align='C')
        pdf.cell(0, 5, "ASSINATURA DO RESPONSAVEL / RECEPCAO", ln=True, align='C')

        pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
        return send_file(io.BytesIO(pdf_out), mimetype='application/pdf', as_attachment=False)

    except Exception as e:
        return str(e), 500

#GERAR CERTIFICADOS PDF DOS COLABORADORES QUE REALIZARAM O TREINAMENTO
def gerar_pdf_bytes(nome, cpf):
    # Formatação visual do CPF
    cpf_limpo = "".join(filter(str.isdigit, str(cpf)))
    cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}" if len(
        cpf_limpo) == 11 else cpf_limpo

    pdf = FPDF()
    pdf.add_page()

    # Borda decorativa
    pdf.rect(5, 5, 200, 287)

    # --- CABEÇALHO INSTITUCIONAL ---
    pdf.set_font("Arial", 'B', 12)
    pdf.ln(10)
    instituicao = "INSTITUTO IMPAR & HOSPITAL MUNICIPAL DE VIGIA DE NAZARE - RAIMUNDO VASCONCELOS"
    # Encode para evitar erro de acentuação em "NAZARÉ"
    pdf.multi_cell(0, 8, instituicao.encode('latin-1', 'replace').decode('latin-1'), align='C')

    # Linha divisória simples abaixo do nome
    pdf.line(20, 35, 190, 35)

    pdf.set_font("Arial", 'B', 20)
    pdf.ln(40)
    pdf.cell(200, 10, "CERTIFICADO DE CONCLUSAO", ln=True, align='C')

    pdf.ln(20)
    pdf.set_font("Arial", size=14)
    data_atual = datetime.now(TZ_PA).strftime('%d/%m/%Y')

    # Texto formatado (encode para latin-1 para evitar erro de acentos no FPDF)
    texto = (f"Certificamos que o colaborador(a) {nome.upper()}, inscrito sob o CPF {cpf_formatado}, "
             f"concluiu com exito o Treinamento de HelpDesk HMV no dia {data_atual}.")

    pdf.multi_cell(0, 10, texto.encode('latin-1', 'replace').decode('latin-1'), align='C')

    pdf.ln(40)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, "Validade Permanente - Sistema de Gestao IT HMV", ln=True, align='C')

    return io.BytesIO(pdf.output(dest='S').encode('latin-1'))


# ENVIAR EMAIL PARA O PRESTADOR QUE PARTICIPOU DO TREINO
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


# --- ROTAS DE TREINAMENTO ---
@app.route('/api/registrar', methods=['POST'])
def registrar():
    try:
        dados = request.get_json()
        if not dados or 'nome' not in dados:
            return jsonify({"status": "erro", "mensagem": "Dados invalidos"}), 400

        dados['data_conclusao'] = datetime.now(TZ_PA).strftime('%d/%m/%Y %H:%M')

        # Limpeza de CPF para o banco
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
        return send_file(pdf_buf, as_attachment=True, download_name=f"Certificado_{nome}.pdf",
                         mimetype='application/pdf')
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


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


# RESIDUOS E LIXO
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
    return "API Central de TI rodando!"


if __name__ == '__main__':
    app.run(debug=True)
