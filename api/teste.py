from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import json

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)

# --- CONEXÃO COM VERCEL POSTGRES ---
def get_db_connection():
    url = os.environ.get('POSTGRES_URL')
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    # Adicionando parâmetros de conexão para garantir estabilidade no Vercel
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

# --- INICIALIZAÇÃO DO BANCO ---
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Tabela de Funcionários (Chave Primária é o CPF)
    cur.execute('''CREATE TABLE IF NOT EXISTS funcionarios (
        cpf TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        tel TEXT,
        funcao TEXT,
        turno TEXT
    );''')

    # Tabela de Atividades (RAT)
    cur.execute('''CREATE TABLE IF NOT EXISTS atividades (
        id SERIAL PRIMARY KEY,
        nome_solicitante TEXT,
        setor_sala TEXT,
        tipo_servico TEXT,
        descricao TEXT,
        status TEXT DEFAULT 'Pendente',
        data_abertura TEXT,
        tecnico_conclusao TEXT,
        data_conclusao TEXT
    );''')

    # Tabelas Extras (Ativos, Relatos e Fila)
    cur.execute('CREATE TABLE IF NOT EXISTS ativos (id_ativo TEXT PRIMARY KEY, dados JSONB);')
    cur.execute('CREATE TABLE IF NOT EXISTS fila (id SERIAL PRIMARY KEY, senha TEXT, status TEXT, dados JSONB);')

    conn.commit()
    cur.close()
    conn.close()

# Executa a criação das tabelas ao iniciar o app
try:
    init_db()
except Exception as e:
    print(f"Erro ao iniciar banco: {e}")

# --- ROTAS DA API ---

@app.route('/')
def home():
    return "Servidor SQL Central de TI Online!"

# Login por CPF
@app.route('/api/login', methods=['POST'])
def login():
    try:
        dados = request.json
        cpf = str(dados.get('cpf', '')).replace('.', '').replace('-', '').strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT nome, funcao FROM funcionarios WHERE cpf = %s', (cpf,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return jsonify({"status": "sucesso", "nome": user['nome'], "funcao": user['funcao']}), 200
        return jsonify({"status": "erro", "mensagem": "CPF não cadastrado"}), 401
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# Gestão de Funcionários
@app.route('/api/funcionarios', methods=['GET', 'POST'])
def gerenciar_funcionarios():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        dados = request.json
        # O 'id' enviado pelo HTML é o CPF
        cpf = str(dados.get('id')).replace('.', '').replace('-', '').strip()
        cur.execute('''INSERT INTO funcionarios (cpf, nome, tel, funcao, turno) 
                       VALUES (%s, %s, %s, %s, %s) 
                       ON CONFLICT (cpf) DO UPDATE SET nome=%s, tel=%s, funcao=%s, turno=%s''',
                    (cpf, dados['nome'], dados['tel'], dados['funcao'], dados['turno'],
                     dados['nome'], dados['tel'], dados['funcao'], dados['turno']))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "sucesso"}), 200

    # Retorna todos os colaboradores
    cur.execute('SELECT cpf, nome, tel, funcao, turno FROM funcionarios ORDER BY nome ASC')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(res), 200

# Helpdesk / RAT
@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_rat():
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        dados = request.json
        data_sol = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cur.execute('''INSERT INTO atividades (nome_solicitante, setor_sala, tipo_servico, descricao, status, data_abertura)
                       VALUES (%s, %s, %s, %s, %s, %s)''',
                    (dados['nome'], dados['setor_sala'], dados['tipo_servico'], dados['descricao'], 'Pendente', data_sol))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "sucesso"}), 201

    cur.execute('SELECT * FROM atividades ORDER BY id DESC')
    res = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(res), 200

# Conclusão de RAT com Nome do Técnico
@app.route('/api/status_rat_concluir/<int:id_doc>', methods=['PATCH'])
def concluir_rat(id_doc):
    try:
        dados = request.json
        nome_tecnico = dados.get('nome_tecnico')
        data_fim = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''UPDATE atividades SET status = 'Concluido', tecnico_conclusao = %s, data_conclusao = %s 
                       WHERE id = %s''', (nome_tecnico, data_fim, id_doc))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
