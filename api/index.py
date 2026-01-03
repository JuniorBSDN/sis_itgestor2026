
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

# No seu index.py, substitua a rota GET de atividades por esta:
@app.route('/api/helpdesk', methods=['GET', 'POST'])
def gerenciar_helpdesk():
if request.method == 'POST':
try:
dados = request.json
            # Garante o status inicial e data
dados['status'] = 'Pendente'
dados['data_registro'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            # Salva na coleção 'atividades' (ou 'helpdesk', como preferir no Firestore)
db.collection('atividades').add(dados)
return jsonify({"status": "sucesso"}), 201
except Exception as e:
return jsonify({"status": "erro", "mensagem": str(e)}), 500

elif request.method == 'GET':
try:
            # Busca os documentos e inclui o ID para a RAT funcionar
            # Pega os documentos e injeta o ID de cada um no dicionário
docs = db.collection('atividades').order_by('data_registro', direction=firestore.Query.DESCENDING).stream()
atividades = []
for doc in docs:
item = doc.to_dict()
                item['id'] = doc.id  # Essencial para o erro que você teve
                item['id'] = doc.id  # <--- Isso resolve o erro de ID não encontrado
atividades.append(item)
return jsonify(atividades), 200
except Exception as e:
return jsonify({"status": "erro", "mensagem": str(e)}), 500

# --- ROTA PARA STATUS DA RAT (ATUALIZAÇÃO) ---

@app.route('/api/status_rat/<id_doc>', methods=['PATCH'])
def atualizar_status_rat(id_doc):
try:
dados = request.json
novo_status = dados.get('status')
        # Atualiza o documento específico usando o ID enviado pelo front-end
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
