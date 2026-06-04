import os
import sqlite3
import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime

# Importações para geração de PDF do Relatório
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURAÇÃO DE IDENTIDADE VISUAL INSTITUCIONAL HMV ---
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


class MODULO_CADASTRO_PRESTADORES_ENTERPRISE:
    def __init__(self, root):
        self.root = root
        self.root.title("SISTGESTOR HMV - CADASTRO REGULAMENTAR DE OPERADORES")
        self.root.geometry("1340x860")
        self.root.configure(fg_color="#cbd5e1")

        self.prestador_selecionado_id = None
        self.nome_coluna_especialidade = "especialidade"

        # Caminhos do Banco de Dados Unificado
        self.base_dir = os.path.join(os.path.expanduser("~"), "Documents", "SISTGESTOR_HMV")
        self.db_path = os.path.join(self.base_dir, "banco_hmv.db")
        os.makedirs(self.base_dir, exist_ok=True)

        self.inicializar_banco_completo()
        self.configurar_estilo_tabelas()
        self.init_ui()
        self.atualizar_tabela_prestadores()
        self.ajustar_formulario_por_perfil()

    def inicializar_banco_completo(self):
        """Inicializa a estrutura da tabela no SQLite de forma segura"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''CREATE TABLE IF NOT EXISTS prestadores (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                nome TEXT NOT NULL,
                                cpf TEXT NOT NULL UNIQUE,
                                categoria TEXT NOT NULL,
                                conselho_nome TEXT,
                                conselho_numero TEXT,
                                status TEXT DEFAULT 'ATIVO',
                                acesso_recepcao INTEGER DEFAULT 0,
                                acesso_triagem INTEGER DEFAULT 0,
                                acesso_medico INTEGER DEFAULT 0,
                                acesso_admin INTEGER DEFAULT 0
                             )''')

            cursor.execute("PRAGMA table_info(prestadores)")
            colunas_existentes = [coluna[1] for coluna in cursor.fetchall()]

            if "specialty" in colunas_existentes:
                self.nome_coluna_especialidade = "specialty"
            elif "especialidade" in colunas_existentes:
                self.nome_coluna_especialidade = "especialidade"
            else:
                cursor.execute("ALTER TABLE prestadores ADD COLUMN especialidade TEXT")
                conn.commit()
                self.nome_coluna_especialidade = "especialidade"

            conn.close()
        except Exception as e:
            messagebox.showerror("Erro de Banco", f"Falha na inicialização da tabela: {e}")

    def configurar_estilo_tabelas(self):
        """Força as cores nativas do Treeview para evitar cabeçalhos invisíveis"""
        style = ttk.Style()
        style.theme_use("default")

        style.configure("Treeview",
                        background="#ffffff",
                        foreground="#0f172a",
                        fieldbackground="#ffffff",
                        rowheight=30,
                        font=("Segoe UI", 10))

        style.configure("Treeview.Heading",
                        background="#0f172a",
                        foreground="#ffffff",
                        font=("Segoe UI", 10, "bold"))

        style.map("Treeview.Heading",
                  background=[('active', '#1e293b')],
                  foreground=[('active', '#ffffff')])

    def init_ui(self):
        # Topbar Institucional
        topbar = ctk.CTkFrame(self.root, height=60, corner_radius=0, fg_color="#0f172a")
        topbar.pack(fill="x", side="top")
        ctk.CTkLabel(topbar, text="👥 CONTROLE E CADASTRO DE PERFIS OPERACIONAIS - HMV",
                     font=("Segoe UI", 15, "bold"), text_color="white").pack(side="left", padx=20)

        # PAINEL DE FILTROS SUPERIOR (Para Relatório e Pesquisa)
        filter_frame = ctk.CTkFrame(self.root, height=75, fg_color="#e2e8f0", corner_radius=8, border_width=1,
                                    border_color="#cbd5e1")
        filter_frame.pack(fill="x", padx=15, pady=(15, 0))

        ctk.CTkLabel(filter_frame, text="🔍 Buscar Nome/CPF:", font=("Segoe UI", 10, "bold"),
                     text_color="#475569").place(x=15, y=10)
        self.filtro_busca = ctk.CTkEntry(filter_frame, width=220, height=30, fg_color="#ffffff",
                                         placeholder_text="Digite para buscar...")
        self.filtro_busca.place(x=15, y=32)
        self.filtro_busca.bind("<KeyRelease>", lambda e: self.atualizar_tabela_prestadores())

        ctk.CTkLabel(filter_frame, text="🎭 Filtrar Perfil:", font=("Segoe UI", 10, "bold"), text_color="#475569").place(
            x=255, y=10)
        self.filtro_perfil = ctk.CTkComboBox(filter_frame, width=160, height=30,
                                             values=["TODOS", "RECEPCIONISTA", "ENFERMEIRO", "MEDICO", "ADMINISTRADOR"],
                                             fg_color="#ffffff", dropdown_fg_color="#ffffff",
                                             command=lambda v: self.atualizar_tabela_prestadores())
        self.filtro_perfil.place(x=255, y=32)
        self.filtro_perfil.set("TODOS")

        ctk.CTkLabel(filter_frame, text="🟢 Status:", font=("Segoe UI", 10, "bold"), text_color="#475569").place(x=430,
                                                                                                                y=10)
        self.filtro_status = ctk.CTkComboBox(filter_frame, width=110, height=30, values=["TODOS", "ATIVO", "INATIVO"],
                                             fg_color="#ffffff", dropdown_fg_color="#ffffff",
                                             command=lambda v: self.atualizar_tabela_prestadores())
        self.filtro_status.place(x=430, y=32)
        self.filtro_status.set("TODOS")

        # Botão Imprimir Relatório Filtrado
        self.btn_imprimir = ctk.CTkButton(filter_frame, text="🖨️ IMPRIMIR RELATÓRIO PDF", fg_color="#0284c7",
                                          hover_color="#0369a1", font=("Segoe UI", 11, "bold"), height=34,
                                          command=self.gerar_pdf_relatorio)
        self.btn_imprimir.place(x=560, y=30)

        # Corpo Principal (Formulário + Tabela)
        corpo = ctk.CTkFrame(self.root, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=15, pady=15)

        # LADO ESQUERDO - Formulário de Cadastro
        self.form_frame = ctk.CTkFrame(corpo, width=420, fg_color="#e2e8f0", corner_radius=8, border_width=1,
                                       border_color="#cbd5e1")
        self.form_frame.pack(side="left", fill="both", padx=(0, 12))
        self.form_frame.pack_propagate(False)

        ctk.CTkLabel(self.form_frame, text="📝 DADOS REQUISITADOS PELO PERFIL", font=("Segoe UI", 12, "bold"),
                     text_color="#1e40af").pack(pady=12, padx=15, anchor="w")

        # Seletor de Perfil
        ctk.CTkLabel(self.form_frame, text="FUNÇÃO / PERFIL DO SISTEMA *", font=("Segoe UI", 10, "bold"),
                     text_color="#475569").pack(anchor="w", padx=15)
        # Substitua a linha atual do self.cb_categoria por esta:
        self.cb_categoria = ctk.CTkComboBox(self.form_frame,
                                            values=["RECEPCIONISTA", "ENFERMEIRO", "TÉCNICO DE ENFERMAGEM",
                                                    "ASSISTENTE SOCIAL", "MEDICO", "ADMINISTRADOR"],
                                            height=34, fg_color="#ffffff", dropdown_fg_color="#ffffff",
                                            command=lambda v: self.ajustar_formulario_por_perfil())
        self.cb_categoria.pack(fill="x", padx=15, pady=(2, 10))
        self.cb_categoria.set("RECEPCIONISTA")

        # Campo: Nome
        ctk.CTkLabel(self.form_frame, text="NOME COMPLETO (NOME DE USUÁRIO) *", font=("Segoe UI", 10, "bold"),
                     text_color="#475569").pack(anchor="w", padx=15)
        self.txt_nome = ctk.CTkEntry(self.form_frame, height=34, fg_color="#ffffff", placeholder_text="Ex: JOSE SILVA")
        self.txt_nome.pack(fill="x", padx=15, pady=(2, 10))

        # Campo: CPF
        ctk.CTkLabel(self.form_frame, text="CPF (SENHA DE ACESSO DE REDE) *", font=("Segoe UI", 10, "bold"),
                     text_color="#475569").pack(anchor="w", padx=15)
        self.txt_cpf = ctk.CTkEntry(self.form_frame, height=34, fg_color="#ffffff", placeholder_text="Apenas números")
        self.txt_cpf.pack(fill="x", padx=15, pady=(2, 10))



        # Elementos do Conselho
        self.lbl_conselho_nome = ctk.CTkLabel(self.form_frame, text="ÓRGÃO DE CLASSE / CONSELHO *",
                                              font=("Segoe UI", 10, "bold"), text_color="#475569")
        self.cb_conselho_nome = ctk.CTkComboBox(self.form_frame, values=["COREN", "CRM", "CRESS"], height=34,
                                                fg_color="#ffffff")

        self.lbl_conselho_num = ctk.CTkLabel(self.form_frame, text="NÚMERO DE REGISTRO PROFISSIONAL *",
                                             font=("Segoe UI", 10, "bold"), text_color="#475569")
        self.txt_conselho_num = ctk.CTkEntry(self.form_frame, height=34, fg_color="#ffffff")

        # O RÓTULO QUE ESTAVA FALTANDO (lbl_especialidade)
        self.lbl_especialidade = ctk.CTkLabel(self.form_frame, text="SETOR DE ATUAÇÃO", font=("Segoe UI", 10, "bold"),
                                              text_color="#475569")

        # O COMBOBOX DE SETORES (Lista Fixa)
        self.txt_especialidade = ctk.CTkComboBox(self.form_frame, values=[], height=34, fg_color="#ffffff",
                                                 dropdown_fg_color="#ffffff")

        # --- AQUI OS BOTÕES FORAM MANTIDOS NO FINAL E O FRAME DE PERMISSÕES FOI REMOVIDO ---

        # Botões do formulário
        self.btn_salvar = ctk.CTkButton(self.form_frame, text="💾 GRAVAR OPERADOR EM REDE", fg_color="#10b981",
                                        hover_color="#059669", font=("Segoe UI", 12, "bold"), height=40,
                                        command=self.salvar_prestador)
        self.btn_salvar.pack(fill="x", padx=15, pady=(20, 6))

        self.btn_limpar = ctk.CTkButton(self.form_frame, text="🧹 LIMPAR FORMULÁRIO", fg_color="#64748b",
                                        hover_color="#475569", font=("Segoe UI", 11, "bold"), height=32,
                                        command=self.limpar_formulario)
        self.btn_limpar.pack(fill="x", padx=15, pady=2)

        # LADO DIREITO - Quadro Geral (Tabela NAtiva)
        right_frame = ctk.CTkFrame(corpo, fg_color="#e2e8f0", corner_radius=8, border_width=1, border_color="#cbd5e1")
        right_frame.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(right_frame, text="📋 QUADRO DE OPERADORES REGISTRADOS", font=("Segoe UI", 12, "bold"),
                     text_color="#1e40af").pack(pady=12, padx=15, anchor="w")

        # --- CONTAINER DE CORREÇÃO DO TREEVIEW ---
        tabela_container = ttk.Frame(right_frame)
        tabela_container.pack(fill="both", expand=True, padx=10, pady=10)

        colunas = ("id", "nome", "cpf", "categoria", "conselho", "especialidade", "status")
        self.tabela = ttk.Treeview(tabela_container, columns=colunas, show="headings")

        self.tabela.heading("id", text="ID")
        self.tabela.heading("nome", text="NOME / USUÁRIO")
        self.tabela.heading("cpf", text="CPF (SENHA)")
        self.tabela.heading("categoria", text="PERFIL")
        self.tabela.heading("conselho", text="CONSELHO")
        self.tabela.heading("especialidade", text="SETOR / ESPECIALIDADE")
        self.tabela.heading("status", text="STATUS")

        self.tabela.column("id", width=50, anchor="center", stretch=False)
        self.tabela.column("nome", width=210, anchor="w")
        self.tabela.column("cpf", width=110, anchor="center", stretch=False)
        self.tabela.column("categoria", width=120, anchor="center")
        self.tabela.column("conselho", width=110, anchor="center")
        self.tabela.column("especialidade", width=160, anchor="w")
        self.tabela.column("status", width=90, anchor="center", stretch=False)

        scrollbar = ttk.Scrollbar(tabela_container, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=scrollbar.set)

        self.tabela.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Ações Inferiores da tabela
        btn_frame_tabela = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame_tabela.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_status = ctk.CTkButton(btn_frame_tabela, text="🚫 ALTERAR STATUS (ATIVAR/DESATIVAR)",
                                        fg_color="#dc2626", hover_color="#991b1b", font=("Segoe UI", 11, "bold"),
                                        height=36, command=self.alterar_status_prestador)
        self.btn_status.pack(side="right", padx=5)

        self.tabela.bind("<<TreeviewSelect>>", lambda e: self.carregar_registro_formulario())

    def ajustar_formulario_por_perfil(self):
        perfil = self.cb_categoria.get()

        # Remove do pack para esconder
        self.lbl_conselho_nome.pack_forget()
        self.cb_conselho_nome.pack_forget()
        self.lbl_conselho_num.pack_forget()
        self.txt_conselho_num.pack_forget()
        self.lbl_especialidade.pack_forget()
        self.txt_especialidade.pack_forget()

        # Definição da lista de setores por perfil
        setores = []
        if perfil == "RECEPCIONISTA":
            setores = ["RECEPÇÃO", "FATURAMENTO", "ADMINISTRATIVO"]
        elif perfil in ["ENFERMEIRO", "TÉCNICO DE ENFERMAGEM"]:
            setores = ["TRIAGEM", "AMBULATÓRIO", "CURATIVO", "SALA VERMELHA", "CENTRO CIRÚRGICO", "INTERNAÇÃO",
                       "OBSTETRÍCIA", "VACINA", "ELETROCARDIOGRAMA", "COLETA"]
        elif perfil == "MEDICO":
            setores = ["CONSULTÓRIO", "SALA VERMELHA", "CENTRO CIRÚRGICO", "OBSTETRÍCIA"]
        elif perfil == "ASSISTENTE SOCIAL":
            setores = ["ASSISTÊNCIA SOCIAL"]
        elif perfil == "ADMINISTRADOR":
            setores = ["ADMINISTRATIVO", "T.I.", "COORDENAÇÃO", "FARMÁCIA", "CAF", "LABORATÓRIO", "TOMOGRAFIA",
                       "RAIO X"]

        # Configura o ComboBox
        self.txt_especialidade.configure(values=setores)
        if setores: self.txt_especialidade.set(setores[0])

        # Exibe os campos necessários
        if perfil in ["ENFERMEIRO", "TÉCNICO DE ENFERMAGEM", "ASSISTENTE SOCIAL", "MEDICO"]:
            self.lbl_conselho_nome.pack(anchor="w", padx=15, pady=(5, 0))
            self.cb_conselho_nome.pack(fill="x", padx=15, pady=(2, 8))
            self.lbl_conselho_num.pack(anchor="w", padx=15, pady=(5, 0))
            self.txt_conselho_num.pack(fill="x", padx=15, pady=(2, 8))

        # Exibe o rótulo e o seletor de setor
        self.lbl_especialidade.pack(anchor="w", padx=15, pady=(5, 0))
        self.txt_especialidade.pack(fill="x", padx=15, pady=(2, 10))
    def carregar_registro_formulario(self):
        item = self.tabela.selection()
        if not item: return

        valores = self.tabela.item(item)['values']
        if not valores: return
        self.prestador_selecionado_id = valores[0]

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM prestadores WHERE id=?", (self.prestador_selecionado_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            self.txt_nome.delete(0, 'end')
            self.txt_nome.insert(0, row['nome'])
            self.txt_cpf.delete(0, 'end')
            self.txt_cpf.insert(0, row['cpf'])

            self.cb_categoria.set(row['categoria'])
            self.ajustar_formulario_por_perfil()

            if row['conselho_nome']:
                self.cb_conselho_nome.set(row['conselho_nome'])

            self.txt_conselho_num.delete(0, 'end')
            if row['conselho_numero']:
                self.txt_conselho_num.insert(0, row['conselho_numero'])

            self.txt_especialidade.delete(0, 'end')
            if row[self.nome_coluna_especialidade]:
                self.txt_especialidade.insert(0, row[self.nome_coluna_especialidade])

            self.btn_salvar.configure(text="🔄 ATUALIZAR OPERADOR", fg_color="#2563eb", hover_color="#1d4ed8")

    def salvar_prestador(self):
        nome = self.txt_nome.get().strip().upper()
        cpf = self.txt_cpf.get().strip().replace('.', '').replace('-', '')
        categoria = self.cb_categoria.get()

        if not nome or not cpf:
            messagebox.showwarning("Aviso de Validação", "Nome Completo e CPF são campos obrigatórios.")
            return

        # Definição automática de acessos baseada no perfil
        acesso_rec, acesso_tri, acesso_med, acesso_adm = 0, 0, 0, 0
        if categoria == "RECEPCIONISTA":
            acesso_rec = 1
        elif categoria in ["ENFERMEIRO", "TÉCNICO DE ENFERMAGEM"]:
            acesso_tri = 1
        elif categoria == "ASSISTENTE SOCIAL":
            # Acesso ao perfil de enfermeiro (triagem) e médico (consultório)
            acesso_tri = 1
            acesso_med = 1
        elif categoria == "MEDICO":
            acesso_med = 1
        elif categoria == "ADMINISTRADOR":
            acesso_rec, acesso_tri, acesso_med, acesso_adm = 1, 1, 1, 1

        conselho_nome, conselho_num, valor_especialidade = None, None, None

        if categoria == "RECEPCIONISTA":
            valor_especialidade = self.txt_especialidade.get().strip().upper() or "RECEPÇÃO CENTRAL"
        elif categoria == "ENFERMEIRO":
            conselho_nome = self.cb_conselho_nome.get()
            conselho_num = self.txt_conselho_num.get().strip().upper()
            valor_especialidade = self.txt_especialidade.get().strip().upper() or "TRIAGEM GERAL"
            if not conselho_num:
                messagebox.showwarning("Exigência Legal", "O número do COREN é obrigatório.")
                return
        elif categoria == "MEDICO":
            conselho_nome = self.cb_conselho_nome.get()
            conselho_num = self.txt_conselho_num.get().strip().upper()
            valor_especialidade = self.txt_especialidade.get().strip().upper() or "CLÍNICA GERAL"
            if not conselho_num:
                messagebox.showwarning("Exigência Legal", "O número do CRM é obrigatório.")
                return
        elif categoria == "ADMINISTRADOR":
            valor_especialidade = "DIREÇÃO E TI"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if self.prestador_selecionado_id:
                query_update = f"""UPDATE prestadores SET 
                                 nome=?, cpf=?, categoria=?, conselho_nome=?, conselho_numero=?, {self.nome_coluna_especialidade}=?,
                                 acesso_recepcao=?, acesso_triagem=?, acesso_medico=?, acesso_admin=?
                                 WHERE id=?"""
                cursor.execute(query_update,
                               (nome, cpf, categoria, conselho_nome, conselho_num, valor_especialidade,
                                acesso_rec, acesso_tri, acesso_med, acesso_adm, self.prestador_selecionado_id))
                msg = "Cadastro do operador atualizado com sucesso!"
            else:
                query_insert = f"""INSERT INTO prestadores 
                                 (nome, cpf, categoria, conselho_nome, conselho_numero, {self.nome_coluna_especialidade}, status, 
                                 acesso_recepcao, acesso_triagem, acesso_medico, acesso_admin)
                                 VALUES (?, ?, ?, ?, ?, ?, 'ATIVO', ?, ?, ?, ?)"""
                cursor.execute(query_insert,
                               (nome, cpf, categoria, conselho_nome, conselho_num, valor_especialidade,
                                acesso_rec, acesso_tri, acesso_med, acesso_adm))
                msg = "Novo operador registrado com sucesso!"

            conn.commit()
            conn.close()

            messagebox.showinfo("Sucesso", msg)
            self.limpar_formulario()
            self.atualizar_tabela_prestadores()
        except sqlite3.IntegrityError:
            messagebox.showerror("Erro", "Este CPF já está cadastrado.")
        except Exception as e:
            messagebox.showerror("Erro Crítico", f"Falha ao salvar dados: {e}")

    def alterar_status_prestador(self):
        if not self.prestador_selecionado_id:
            messagebox.showwarning("Seleção Requerida", "Selecione um operador na tabela da direita.")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT status, nome FROM prestadores WHERE id=?", (self.prestador_selecionado_id,))
            resultado = cursor.fetchone()

            if resultado:
                status_atual, nome_colaborador = resultado[0], resultado[1]
                novo_status = "INATIVO" if status_atual == "ATIVO" else "ATIVO"
                termo_acao = "DESATIVAR" if novo_status == "INATIVO" else "REATIVAR"

                if messagebox.askyesno("Confirmar", f"Deseja {termo_acao} o colaborador {nome_colaborador}?"):
                    cursor.execute("UPDATE prestadores SET status=? WHERE id=?",
                                   (novo_status, self.prestador_selecionado_id))
                    conn.commit()
                    messagebox.showinfo("Sucesso", f"Colaborador alterado para {novo_status}.")

            conn.close()
            self.limpar_formulario()
            self.atualizar_tabela_prestadores()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível modificar o status: {e}")

    def atualizar_tabela_prestadores(self):
        """Limpa e preenche o Treeview aplicando as regras de filtros ativos"""
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        busca = self.filtro_busca.get().strip().upper()
        perfil = self.filtro_perfil.get()
        status = self.filtro_status.get()

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = f"""SELECT id, nome, cpf, categoria, 
                        IFNULL(conselho_nome || ' ' || conselho_numero, '---'), 
                        IFNULL({self.nome_coluna_especialidade}, '---'), 
                        status FROM prestadores WHERE 1=1"""
            parametros = []

            if busca:
                query += " AND (nome LIKE ? OR cpf LIKE ?)"
                parametros.append(f"%{busca}%")
                parametros.append(f"%{busca}%")

            if perfil != "TODOS":
                query += " AND categoria = ?"
                parametros.append(perfil)

            if status != "TODOS":
                query += " AND status = ?"
                parametros.append(status)

            query += " ORDER BY nome ASC"

            cursor.execute(query, parametros)
            for r in cursor.fetchall():
                self.tabela.insert('', 'end', values=(r[0], r[1], r[2], r[3], r[4], r[5], r[6]))

            conn.close()
        except Exception as e:
            print(f"Erro ao carregar a lista: {e}")

    def gerar_pdf_relatorio(self):
        """Gera um PDF profissional com base nos registros que estão visíveis na tabela com os filtros"""
        registros = [self.tabela.item(item)['values'] for item in self.tabela.get_children()]

        if not registros:
            messagebox.showwarning("Relatório Vazio",
                                   "Não existem registros na tabela com os filtros atuais para imprimir.")
            return

        pdf_dir = os.path.join(self.base_dir, "Relatorios")
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, "relatorio_prestadores.pdf")

        try:
            c = canvas.Canvas(pdf_path, pagesize=A4)
            largura, altura = A4

            # --- Configuração de Páginas ---
            def desenhar_cabecalho(p):
                c.setFillColorRGB(0.06, 0.09, 0.16)  # Azul escuro institucional #0f172a
                c.rect(0, altura - 60, largura, 60, fill=True, stroke=False)

                c.setFillColorRGB(1, 1, 1)
                c.setFont("Helvetica-Bold", 14)
                c.drawString(20, altura - 35, "HOSPITAL MUNICIPAL DE VIGIA (HMV)")
                c.setFont("Helvetica", 9)
                c.drawString(20, altura - 50, "SISTGESTOR HMV - RELATÓRIO REGULAMENTAR DE OPERADORES DE REDE")

                # Data de emissão
                c.drawRightString(largura - 20, altura - 35, datetime.now().strftime("%d/%m/%Y %H:%M"))

                # Linha divisória dos filtros aplicados
                c.setFillColorRGB(0.2, 0.2, 0.2)
                c.setFont("Helvetica-Oblique", 9)
                filtros_str = f"Filtros aplicados - Perfil: {self.filtro_perfil.get()} | Status: {self.filtro_status.get()}"
                c.drawString(20, altura - 80, filtros_str)

                # Cabeçalho da Tabela no PDF
                c.setFillColorRGB(0.09, 0.16, 0.27)
                c.rect(20, altura - 110, largura - 40, 20, fill=True, stroke=False)
                c.setFillColorRGB(1, 1, 1)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(25, altura - 104, "ID")
                c.drawString(60, altura - 104, "NOME / USUÁRIO")
                c.drawString(230, altura - 104, "CPF")
                c.drawString(320, altura - 104, "PERFIL")
                c.drawString(420, altura - 104, "CONSELHO")
                c.drawString(515, altura - 104, "STATUS")

            desenhar_cabecalho(1)

            y = altura - 130
            pagina = 1

            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 9)

            for reg in registros:
                if y < 50:  # Se atingir o limite inferior, cria nova página
                    c.showPage()
                    pagina += 1
                    desenhar_cabecalho(pagina)
                    y = altura - 130
                    c.setFillColorRGB(0, 0, 0)
                    c.setFont("Helvetica", 9)

                # Renderiza os dados limpando Strings longas se necessário
                c.drawString(25, y, str(reg[0]))
                c.drawString(60, y, str(reg[1])[:32])
                c.drawString(230, y, str(reg[2]))
                c.drawString(320, y, str(reg[3]))
                c.drawString(420, y, str(reg[4])[:18])
                c.drawString(515, y, str(reg[6]))

                # Linha fina divisória de registro
                c.setStrokeColorRGB(0.8, 0.8, 0.8)
                c.setLineWidth(0.5)
                c.line(20, y - 5, largura - 20, y - 5)

                y -= 22

            # Rodapé final informativo
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(20, 25, f"Total de operadores listados: {len(registros)}")
            c.drawRightString(largura - 20, 25, f"Página {pagina}")

            c.save()

            # Abre o PDF gerado automaticamente na tela do Windows
            os.startfile(pdf_path)

        except Exception as e:
            messagebox.showerror("Erro Impressão", f"Não foi possível gerar o arquivo PDF: {e}")

    def limpar_formulario(self):
        self.prestador_selecionado_id = None
        self.btn_salvar.configure(text="💾 GRAVAR OPERADOR EM REDE", fg_color="#10b981", hover_color="#059669")
        self.txt_nome.delete(0, 'end')
        self.txt_cpf.delete(0, 'end')
        self.txt_conselho_num.delete(0, 'end')
        self.txt_especialidade.delete(0, 'end')
        self.cb_categoria.set("RECEPCIONISTA")
        self.ajustar_formulario_por_perfil()


if __name__ == "__main__":
    root = ctk.CTk()
    app = MODULO_CADASTRO_PRESTADORES_ENTERPRISE(root)
    root.mainloop()
