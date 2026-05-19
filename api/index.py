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


# --- MÓDULO: OUVIDORIA HOSPITALAR (TOTEM & DASHBOARD) ---

COLECAO_AVALIACOES = "avaliacoes"

# Rotas Web para servir os arquivos que estão no seu repositório
@app.route('/totem')
def abrir_totem():
    """Acessível via http://localhost:5000/totem"""
    return render_template('feed.html')

@app.route('/admin')
def abrir_admin():
    """Acessível via http://localhost:5000/admin"""
    return render_template('feedAdmin.html')


@app.route('/api/avaliacoes', methods=['POST'])
def salvar_avaliacao():
    try:
        dados = request.get_json()
        agora = datetime.now(TZ_PA)
        
        payload = {
            "setor": str(dados.get("setor")),
            "nota": int(dados.get("nota")),
            "rotulo_nota": str(dados.get("rotulo_nota")),
            "motivos": list(dados.get("motivos", [])),
            "timestamp": agora.isoformat(),
            "data_busca": agora.strftime("%Y-%m-%d")
        }
        
        db.collection(COLECAO_AVALIACOES).add(payload)
        return jsonify({"status": "sucesso", "mensagem": "Avaliação salva com sucesso."}), 201
        
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 400


@app.route('/api/indicadores', methods=['GET'])
def buscar_indicadores():
    try:
        docs = db.collection(COLECAO_AVALIACOES).stream()
        
        total_votos = 0
        soma_notas = 0
        distribuicao_notas = {"Péssimo": 0, "Ruim": 0, "Regular": 0, "Bom": 0, "Excelente": 0}
        
        # Setores pré-definidos para evitar erros no gráfico se o banco iniciar vazio
        setores = {
            "Pronto Atendimento": {"soma": 0, "votos": 0, "media": 0},
            "Ambulatório": {"soma": 0, "votos": 0, "media": 0},
            "Exames e Laboratório": {"soma": 0, "votos": 0, "media": 0},
            "Internação": {"soma": 0, "votos": 0, "media": 0}
        }

        for doc in docs:
            data = doc.to_dict()
            nota = data.get("nota", 0)
            rotulo = data.get("rotulo_nota")
            setor = data.get("setor")
            
            total_votos += 1
            soma_notas += nota
            
            if rotulo in distribuicao_notas:
                distribuicao_notas[rotulo] += 1
                
            if setor not in setores:
                setores[setor] = {"soma": 0, "votos": 0, "media": 0}
            
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


def gerar_pdf_bytes(nome, cpf):
    # Formatação visual do CPF
    cpf_limpo = "".join(filter(str.isdigit, str(cpf)))
    cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}" if len(cpf_limpo) == 11 else cpf_limpo
    
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


#ENVIAR EMAIL PARA O PRESTADOR QUE PARTICIPOU DO TREINO
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
        return send_file(pdf_buf, as_attachment=True, download_name=f"Certificado_{nome}.pdf", mimetype='application/pdf')
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

#RESIDUOS E LIXO
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


#----MECANISMO QUE GERA SENHAS
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
            dados['timestamp'] = firestore.SERVER_TIMESTAMP # Para ordenação precisa
            
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
            "chamada_timestamp": firestore.SERVER_TIMESTAMP # Isso dispara a TV e o Rodapé
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
    return "API Central de TI rodando!"

if __name__ == '__main__':
    app.run(debug=True)
