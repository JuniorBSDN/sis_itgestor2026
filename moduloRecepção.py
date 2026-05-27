import sys
import os
import sqlite3
import requests
from io import BytesIO
from datetime import datetime
import customtkinter as ctk
from tkinter import ttk, messagebox
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURAÇÃO GLOBAL DE APARÊNCIA ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


# --- MODAL DE AUTENTICAÇÃO RESTRITA ---
class ModalLoginAdmin(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success

        self.title("ACESSO RESTRITO")
        self.geometry("380x200")
        self.resizable(False, False)

        # Centralizar o modal
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (380 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (200 // 2)
        self.geometry(f"380x200+{x}+{y}")

        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text="🔒 AUTENTICAÇÃO REQUERIDA", font=("Segoe UI", 13, "bold"), text_color="#f43f5e").pack(
            pady=(20, 10))

        self.input_senha = ctk.CTkEntry(self, placeholder_text="Digite a senha de administrador...", show="*",
                                        width=260, height=35)
        self.input_senha.pack(pady=10)
        self.input_senha.bind("<Return>", lambda e: self.verificar())

        self.btn_entrar = ctk.CTkButton(self, text="VALIDAR ACESSO", font=("Segoe UI", 12, "bold"), fg_color="#6366f1",
                                        hover_color="#4f46e5", width=160, height=35, command=self.verificar)
        self.btn_entrar.pack(pady=10)

    def verificar(self):
        # Senha padrão para acessar o painel administrativo
        if self.input_senha.get() == "11111000001":
            self.destroy()
            self.on_success()
        else:
            messagebox.showerror("Acesso Negado", "Senha administrativa incorreta!")


# --- MODAL PAINEL ADMINISTRATIVO E RELATÓRIOS ---
class ModalAdmin(ctk.CTkToplevel):
    def __init__(self, parent, db_path, pdf_folder):
        super().__init__(parent)
        self.db_path = db_path
        self.pdf_folder = pdf_folder

        self.title("PAINEL ADMINISTRATIVO - CONTROLE DE ADMISSÃO")
        self.geometry("900x650")
        self.resizable(False, False)

        # Centralizar o modal
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (900 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (650 // 2)
        self.geometry(f"900x650+{x}+{y}")

        self.transient(parent)
        self.grab_set()

        # Layout Principal
        main_frame = ctk.CTkFrame(self, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Cabeçalho
        ctk.CTkLabel(main_frame, text="📊 DASHBOARD INDICADORES & RELATÓRIOS", font=("Segoe UI", 16, "bold"),
                     text_color="#38bdf8").pack(pady=15)

        # Barra de Filtros
        filter_box = ctk.CTkFrame(main_frame, fg_color="#1e293b", corner_radius=10)
        filter_box.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(filter_box, text="Filtrar por:", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, padx=10,
                                                                                          pady=10, sticky="w")

        self.combo_tipo = ctk.CTkComboBox(filter_box, values=["Mês Atual", "Ano Atual", "Dia Específico"], width=130,
                                          command=self.alternar_filtros)
        self.combo_tipo.grid(row=0, column=1, padx=5, pady=10)

        self.input_data = ctk.CTkEntry(filter_box, placeholder_text="DD/MM/AAAA", width=120)
        self.input_data.grid(row=0, column=2, padx=5, pady=10)
        self.input_data.insert(0, datetime.now().strftime('%d/%m/%Y'))
        self.input_data.configure(state="disabled")

        btn_filtrar = ctk.CTkButton(filter_box, text="🔍 Filtrar", fg_color="#0284c7", hover_color="#0369a1", width=110,
                                    command=self.carregar_dados_admin)
        btn_filtrar.grid(row=0, column=3, padx=10, pady=10)

        self.btn_print_report = ctk.CTkButton(filter_box, text="🖨️ Imprimir Relatório", fg_color="#22c55e",
                                              hover_color="#16a34a", width=180, command=self.gerar_pdf_relatorio)
        filter_box.grid_columnconfigure(4, weight=1)
        self.btn_print_report.grid(row=0, column=5, padx=15, pady=10, sticky="e")

        # Cards de Indicadores
        cards_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        cards_frame.pack(fill="x", padx=15, pady=10)
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)

        self.card_total = ctk.CTkFrame(cards_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        self.card_total.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.lbl_total_num = ctk.CTkLabel(self.card_total, text="0", font=("Segoe UI", 24, "bold"),
                                          text_color="#4ade80")
        self.lbl_total_num.pack(pady=(10, 0))
        ctk.CTkLabel(self.card_total, text="Total de Atendimentos no Período", font=("Segoe UI", 11, "italic")).pack(
            pady=(0, 10))

        self.card_recorrencia = ctk.CTkFrame(cards_frame, fg_color="#0f172a", border_width=1, border_color="#334155")
        self.card_recorrencia.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.lbl_recorr_num = ctk.CTkLabel(self.card_recorrencia, text="0", font=("Segoe UI", 24, "bold"),
                                           text_color="#38bdf8")
        self.lbl_recorr_num.pack(pady=(10, 0))
        ctk.CTkLabel(self.card_recorrencia, text="Pacientes Recorrentes (Retornos)",
                     font=("Segoe UI", 11, "italic")).pack(pady=(0, 10))

        # Tabela de Visualização Administrativa
        tabela_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        tabela_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        self.tabela_adm = ttk.Treeview(tabela_frame, columns=("ID", "RM", "Nome", "Data"), show="headings")
        self.tabela_adm.heading("ID", text="Nº ENTRADA")
        self.tabela_adm.heading("RM", text="RM PRONTUÁRIO")
        self.tabela_adm.heading("Nome", text="PACIENTE")
        self.tabela_adm.heading("Data", text="DATA/HORA ADMISSÃO")

        self.tabela_adm.column("ID", width=100, anchor="center")
        self.tabela_adm.column("RM", width=150, anchor="center")
        self.tabela_adm.column("Nome", width=350, anchor="w")
        self.tabela_adm.column("Data", width=200, anchor="center")
        self.tabela_adm.pack(fill="both", expand=True)

        self.carregar_dados_admin()

    def alternar_filtros(self, escolha):
        if escolha == "Dia Específico":
            self.input_data.configure(state="normal")
        else:
            self.input_data.configure(state="disabled")

    def construir_query_periodo(self):
        tipo = self.combo_tipo.get()
        hoje = datetime.now()

        if tipo == "Mês Atual":
            mes_ano = hoje.strftime('/%m/%Y')
            return "SELECT id, rm, nome, data_registro FROM atendimentos WHERE data_registro LIKE ?", (f"%{mes_ano}%",)
        elif tipo == "Ano Atual":
            ano = hoje.strftime('/%Y')
            return "SELECT id, rm, nome, data_registro FROM atendimentos WHERE data_registro LIKE ?", (f"%{ano}%",)
        else:
            data_user = self.input_data.get().strip()
            return "SELECT id, rm, nome, data_registro FROM atendimentos WHERE data_registro LIKE ?", (f"{data_user}%",)

    def carregar_dados_admin(self):
        for item in self.tabela_adm.get_children():
            self.tabela_adm.delete(item)

        query, params = self.construir_query_periodo()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        dados = cursor.fetchall()

        # Calcula o número de recorrentes (pacientes que aparecem mais de uma vez no geral)
        cursor.execute("""SELECT COUNT(id) FROM atendimentos WHERE rm IN (
                            SELECT rm FROM atendimentos GROUP BY rm HAVING COUNT(id) > 1
                          ) AND data_registro LIKE ?""", (params[0],))
        total_recorrentes = cursor.fetchone()[0] or 0
        conn.close()

        for row in dados:
            self.tabela_adm.insert('', 'end', values=row)

        self.lbl_total_num.configure(text=str(len(dados)))
        self.lbl_recorr_num.configure(text=str(total_recorrentes))

    def gerar_pdf_relatorio(self):
        tipo_filtro = self.combo_tipo.get()
        query, params = self.construir_query_periodo()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        dados = cursor.fetchall()
        conn.close()

        if not dados:
            return messagebox.showwarning("Relatório", "Não existem dados registrados neste período para exportar!")

        nome_arquivo = f"Relatorio_Admissao_{tipo_filtro.replace(' ', '_')}_{datetime.now().strftime('%d%H%M%S')}.pdf"
        path = os.path.abspath(os.path.join(self.pdf_folder, nome_arquivo))

        canvas_pdf = canvas.Canvas(path, pagesize=A4)

        # Cabeçalho Relatório Geral
        canvas_pdf.setFont("Helvetica-Bold", 11)
        canvas_pdf.drawString(40, 800, "HOSPITAL MUNICIPAL DE VIGIA DE NAZARÉ - PA")
        canvas_pdf.setFont("Helvetica", 9)
        canvas_pdf.drawString(40, 785, f"RELATÓRIO ADMINISTRATIVO DE ADMISSÕES - FILTRO: {tipo_filtro.upper()}")
        canvas_pdf.drawString(40, 772,
                              f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Total do Período: {len(dados)} atendimentos")
        canvas_pdf.line(40, 765, 555, 765)

        # Cabeçalho da Tabela do PDF
        canvas_pdf.setFont("Helvetica-Bold", 8)
        canvas_pdf.drawString(40, 750, "Nº ENTRADA")
        canvas_pdf.drawString(120, 750, "RM (PRONTUÁRIO)")
        canvas_pdf.drawString(240, 750, "NOME DO PACIENTE")
        canvas_pdf.drawString(450, 750, "DATA/HORA ADMISSÃO")
        canvas_pdf.line(40, 743, 555, 743)

        y = 728
        canvas_pdf.setFont("Helvetica", 8)
        for row in dados:
            canvas_pdf.drawString(40, y, f"{row[0]:06d}")
            canvas_pdf.drawString(120, y, str(row[1]))
            canvas_pdf.drawString(240, y, str(row[2])[:40])
            canvas_pdf.drawString(450, y, str(row[3]))
            y -= 18
            if y < 50:
                canvas_pdf.showPage()
                y = 780
                canvas_pdf.setFont("Helvetica", 8)

        canvas_pdf.save()
        if os.path.exists(path):
            os.startfile(path)


# --- MODAL DE DETALHES E NOVA ENTRADA ---
class ModalDetalhesPaciente(ctk.CTkToplevel):
    def __init__(self, dados, parent, callback_novo_atendimento):
        super().__init__(parent)
        self.dados = dados
        self.callback_novo_atendimento = callback_novo_atendimento

        self.title(f"HISTÓRICO CLÍNICO - RM: {dados.get('rm', '---')}")
        self.geometry("600x680")
        self.resizable(False, False)

        # Centralizar o modal
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (600 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (680 // 2)
        self.geometry(f"600x680+{x}+{y}")

        self.transient(parent)
        self.grab_set()

        frame = ctk.CTkScrollableFrame(self, corner_radius=15)
        frame.pack(pady=15, padx=15, fill="both", expand=True)

        ctk.CTkLabel(frame, text="PRONTUÁRIO INTEGRAL DO PACIENTE", font=("Segoe UI", 16, "bold"),
                     text_color="#38bdf8").pack(pady=(10, 5))

        recorrencias = dados.get('total_entradas', 1)
        alerta_txt = f"⚠️ HISTÓRICO: ESTE PACIENTE JÁ DEU ENTRADA {recorrencias} VEZES NO HOSPITAL" if recorrencias > 1 else "ℹ️ PACIENTE POSSUI APENAS 1 ENTRADA REGISTRADA"
        alerta_cor = "#eab308" if recorrencias > 1 else "#22c55e"
        ctk.CTkLabel(frame, text=alerta_txt, font=("Segoe UI", 11, "bold"), text_color=alerta_cor).pack(pady=5)

        grid_dados = ctk.CTkFrame(frame, fg_color="transparent")
        grid_dados.pack(fill="both", expand=True, padx=10, pady=5)
        grid_dados.columnconfigure(1, weight=1)

        exibir = [
            ('RM (Prontuário):', 'rm'), ('Nome do Paciente:', 'nome'), ('CPF:', 'cpf'),
            ('Cartão SUS:', 'sus'), ('RG:', 'rg'), ('Nascimento:', 'nascimento'),
            ('Sexo:', 'sexo'), ('Naturalidade:', 'naturalidade'), ('Estado Civil:', 'est_civil'),
            ('Cor/Raça:', 'cor'), ('Profissão/Ocupação:', 'ocupacao'), ('Mãe:', 'mae'),
            ('Pai:', 'pai'), ('Endereço:', 'endereco'), ('Telefone:', 'telefone')
        ]

        for idx, (label, chave) in enumerate(exibir):
            lbl = ctk.CTkLabel(grid_dados, text=label, font=("Segoe UI", 11, "bold"), anchor="w")
            lbl.grid(row=idx, column=0, padx=10, pady=4, sticky="w")

            val = ctk.CTkLabel(grid_dados, text=str(dados.get(chave, "---")), font=("Segoe UI", 12), anchor="w",
                               justify="left", wraplength=350)
            val.grid(row=idx, column=1, padx=10, pady=4, sticky="w")

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", pady=15, padx=20)

        self.btn_novo_atendimento = ctk.CTkButton(btn_box, text="🔄 REAPROVEITAR REGISTRO (GERAR RETORNO)",
                                                  font=("Segoe UI", 13, "bold"),
                                                  fg_color="#0284c7", hover_color="#0369a1", command=self.gerar_retorno)
        self.btn_novo_atendimento.pack(fill="x", pady=5)


        self.btn_fechar = ctk.CTkButton(btn_box, text="FECHAR JANELA", font=("Segoe UI", 13),
                                        fg_color="#34495e", hover_color="#2c3e50", command=self.destroy)
        self.btn_fechar.pack(fill="x")

    def gerar_retorno(self):
        self.callback_novo_atendimento(self.dados)
        self.destroy()

class ModalSobre(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sobre o Sistema")
        self.geometry("500x550")
        self.transient(parent)
        self.grab_set()

        # Centralizar
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (500 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (550 // 2)
        self.geometry(f"500x550+{x}+{y}")

        scroll = ctk.CTkScrollableFrame(self, label_text="Informações do Sistema")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        texto = """
🏥 MODULO RECEPÇÃO
Desenvolvido para o Hospital Municipal de Vigia de Nazaré - PA.

👨‍💻 DESENVOLVEDOR:
Setor de Tecnologia da Informação (T.I.)
Suporte Técnico: (91) 98325-2639

📖 TUTORIAL RÁPIDO:
1. Preencha os campos do paciente.
2. O sistema gera um RM automático.
3. Clique em 'Imprimir e Enviar' para registrar.
4. Use a busca à direita para encontrar históricos.
5. Selecione um paciente na tabela para ver o prontuário.

⚖️ CONFORMIDADES JURÍDICAS:
Este sistema respeita a LGPD (Lei Geral de Proteção de Dados). 
Os dados aqui inseridos são de responsabilidade da unidade de saúde. 
O uso indevido é passível de punições administrativas e legais.
        """
        ctk.CTkLabel(scroll, text=texto, justify="left", font=("Segoe UI", 12)).pack(padx=10, pady=10)

        ctk.CTkButton(self, text="FECHAR", command=self.destroy).pack(pady=10)


# --- CLASSE PRINCIPAL DO SISTEMA ---
class SISTGESTOR_HMV_V4:
    def __init__(self, root):
        self.root = root
        self.root.title("MODULO RECEPÇÃO - SETOR DE TÉCNOLOIA DA INFORMAÇÃO - T.I - INSTITUTO IMPAR - SUPORTE: 91983252639 ")
        self.root.geometry("1340x840")

        self.logo_bytes = None
        self.campos = {}

        base_dir = os.path.join(os.path.expanduser("~"), "Documents", "SISTGESTOR_HMV")
        if not os.path.exists(base_dir): os.makedirs(base_dir)
        self.db_path = os.path.join(base_dir, "banco_hmv.db")
        self.pdf_folder = os.path.join(base_dir, "atendimentos_pdf")
        if not os.path.exists(self.pdf_folder): os.makedirs(self.pdf_folder)

        self.criar_banco()
        self.ajustar_estilo_tabelas()
        self.init_ui()

    def criar_banco(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 1. Cria a tabela base inicial caso não exista
            cursor.execute('''CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, rm TEXT, nome TEXT, sus TEXT, 
            rg TEXT, cpf TEXT, nascimento TEXT, sexo TEXT, naturalidade TEXT, 
            est_civil TEXT, cor TEXT, telefone TEXT, mae TEXT, pai TEXT, 
            ocupacao TEXT, endereco TEXT, data_registro TIMESTAMP)''')
            conn.commit()

            # 2. Migration: Adiciona as novas colunas que faltavam nos bancos antigos
            cursor.execute("PRAGMA table_info(atendimentos)")
            colunas_existentes = [coluna[1] for coluna in cursor.fetchall()]

            novas_colunas = ['solicitante', 'procedencia', 'responsavel']
            for nova_coluna in novas_colunas:
                if nova_coluna not in colunas_existentes:
                    try:
                        cursor.execute(f"ALTER TABLE atendimentos ADD COLUMN {nova_coluna} TEXT")
                        conn.commit()
                    except sqlite3.OperationalError:
                        # Se já existir no arquivo DB físico mas não na lista pragma, ignora
                        pass

            conn.close()
        except Exception as e:
            print(f"Erro ao inicializar ou atualizar banco: {e}")

    def ajustar_estilo_tabelas(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1e293b", foreground="#f8fafc", rowheight=32, fieldbackground="#1e293b",
                        font=("Segoe UI", 11))
        style.configure("Treeview.Heading", background="#0f172a", foreground="#ffffff", font=("Segoe UI", 11, "bold"),
                        bordercolor="#0f172a", thickness=35)
        style.map("Treeview", background=[("selected", "#1f538d")], foreground=[("selected", "#ffffff")])

    def init_ui(self):
        header = ctk.CTkFrame(master=self.root, height=60, corner_radius=0, fg_color=("#1e3d59", "#0f172a"))
        header.pack(fill="x", side="top")

        ctk.CTkLabel(header, text="🏥 URGÊNCIA/EMERGÊNCIA", font=("Segoe UI", 15, "bold"),
                     text_color="white").pack(side="left", padx=20, pady=15)

        self.btn_admin_modal = ctk.CTkButton(header, text="📊 PAINEL GERAL ADM", font=("Segoe UI", 12, "bold"),
                                             fg_color="#6366f1", hover_color="#4f46e5", height=32,
                                             command=self.solicitar_acesso_adm)
        self.btn_admin_modal.pack(side="right", padx=15, pady=15)

        # No seu header:
        self.btn_sobre = ctk.CTkButton(header, text="ℹ️ SOBRE", font=("Segoe UI", 12, "bold"),
                                       fg_color="#334155", hover_color="#475569", width=100, height=32,
                                       command=lambda: ModalSobre(self.root))
        self.btn_sobre.pack(side="right", padx=5, pady=15)

        ctk.CTkLabel(header, text="Vigia de Nazaré - PA/ COD01 ", font=("Segoe UI", 12, "italic"), text_color="#ecf0f1").pack(
            side="right", padx=20, pady=15)

        main_body = ctk.CTkFrame(master=self.root, fg_color="transparent")
        main_body.pack(fill="both", expand=True, padx=15, pady=15)

        left_column = ctk.CTkFrame(master=main_body, width=460, corner_radius=12)
        left_column.pack(side="left", fill="both", padx=(0, 10), pady=0)

        ctk.CTkLabel(left_column, text="📋 RECEPCIONAR PACIENTE", font=("Segoe UI", 14, "bold"),
                     text_color="#38bdf8").pack(pady=12, padx=20, anchor="w")

        grid_frame = ctk.CTkFrame(left_column, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=15, pady=5)
        for i in range(4): grid_frame.columnconfigure(i, weight=1)

        def add_input(label, chave, row, col, span=1, r_only=False, combo=None, placeholder=""):
            lbl = ctk.CTkLabel(grid_frame, text=label, font=("Segoe UI", 10, "bold"), text_color="gray")
            lbl.grid(row=row, column=col, columnspan=span, padx=5, pady=(5, 1), sticky="w")
            if combo:
                w = ctk.CTkComboBox(grid_frame, values=combo, height=32)
            else:
                w = ctk.CTkEntry(grid_frame, height=32, placeholder_text=placeholder)
                if r_only:
                    w.insert(0, "GERANDO...")
                    w.configure(state="readonly", text_color="#f43f5e", font=("Segoe UI", 12, "bold"))
            w.grid(row=row + 1, column=col, columnspan=span, padx=5, pady=(0, 5), sticky="ew")
            self.campos[chave] = w

        add_input("RM", "rm", 0, 0, 1, r_only=True)
        add_input("NOME DO PACIENTE", "nome", 0, 1, 3, placeholder="Nome Completo")

        add_input("CARTÃO SUS", "sus", 2, 0, 1, placeholder="000 0000...")
        add_input("RG", "rg", 2, 1, 1, placeholder="Nº Identidade")
        add_input("CPF", "cpf", 2, 2, 2, placeholder="000.000.000-00")

        add_input("NASCIMENTO", "nasc", 4, 0, 1, placeholder="DD/MM/AAAA")
        add_input("SEXO", "sexo", 4, 1, 1, combo=["MASCULINO", "FEMININO"])
        add_input("ESTADO CIVIL", "est_civil", 4, 2, 1, combo=["SOL", "CAS", "DIV", "VIU", "UNIÃO"])
        add_input("COR/RAÇA", "cor", 4, 3, 1, combo=["BRA", "PAR", "PRE", "AMA", "IND"])

        add_input("NATURALIDADE", "naturalidade", 6, 0, 2, placeholder="Cidade de Origem")
        add_input("PROFISSÃO/OCUPAÇÃO", "ocupacao", 6, 2, 2, placeholder="Trabalho atual")

        add_input("MÃE", "mae", 8, 0, 2, placeholder="Nome da Mãe")
        add_input("PAI", "pai", 8, 2, 2, placeholder="Nome do Pai")

        add_input("ENDEREÇO RESIDENCIAL", "end", 10, 0, 3, placeholder="Rua, Número e Bairro")
        add_input("TELEFONE", "tel", 10, 3, 1, placeholder="(91) 90000-0000")

        self.btn_salvar = ctk.CTkButton(left_column, text="💾 IMPRIMIR E ENVIAR PARA A TRIAGEM",
                                        font=("Segoe UI", 13, "bold"), fg_color="#22c55e", hover_color="#16a34a",
                                        height=42, command=self.processo_novo_cadastro)
        self.btn_salvar.pack(fill="x", padx=20, pady=15)

        right_column = ctk.CTkFrame(master=main_body, corner_radius=12)
        right_column.pack(side="right", fill="both", expand=True)

        search_frame = ctk.CTkFrame(right_column, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(search_frame, text="🔍 PESQUISAR PACIENTE:", font=("Segoe UI", 12, "bold"), text_color="gray").pack(
            side="left", padx=(5, 10))
        self.input_busca = ctk.CTkEntry(search_frame, placeholder_text="Busque por nome, CPF ou número de RM...",
                                        height=35)
        self.input_busca.pack(side="left", fill="x", expand=True)
        self.input_busca.bind("<KeyRelease>", lambda e: self.pesquisar_paciente())

        tabela_frame = ctk.CTkFrame(right_column, fg_color="transparent")
        tabela_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.tabela = ttk.Treeview(tabela_frame, columns=("RM", "Nome", "CPF", "Última Admissão", "Retornos"),
                                   show="headings")
        self.tabela.heading("RM", text="RM")
        self.tabela.heading("Nome", text="NOME DO PACIENTE")
        self.tabela.heading("CPF", text="CPF")
        self.tabela.heading("Última Admissão", text="ÚLTIMA ADMISSÃO")
        self.tabela.heading("Retornos", text="RETORNOS")

        self.tabela.column("RM", width=130, anchor="center")
        self.tabela.column("Nome", width=250, anchor="w")
        self.tabela.column("CPF", width=120, anchor="center")
        self.tabela.column("Última Admissão", width=140, anchor="center")
        self.tabela.column("Retornos", width=90, anchor="center")

        self.tabela.pack(fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", lambda event: self.abrir_modal_detalhes())

        self.reset_rm()
        self.pesquisar_paciente()

    def solicitar_acesso_adm(self):
        ModalLoginAdmin(self.root, self.abrir_painel_adm)

    def abrir_painel_adm(self):
        ModalAdmin(self.root, self.db_path, self.pdf_folder)

    def reset_rm(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM atendimentos")
        res = cursor.fetchone()[0]
        conn.close()
        prox = (res + 1) if res else 1

        self.campos['rm'].configure(state="normal")
        self.campos['rm'].delete(0, 'end')
        self.campos['rm'].insert(0, f"{prox:05d}")
        self.campos['rm'].configure(state="readonly")

    def pesquisar_paciente(self):
        termo = self.input_busca.get()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''SELECT rm, nome, cpf, MAX(data_registro), COUNT(id) FROM atendimentos 
                          WHERE nome LIKE ? OR rm LIKE ? OR cpf LIKE ?
                          GROUP BY rm ORDER BY id DESC''', (f'%{termo}%', f'%{termo}%', f'%{termo}%'))
        dados = cursor.fetchall()
        conn.close()

        for item in self.tabela.get_children():
            self.tabela.delete(item)

        for row in dados:
            self.tabela.insert('', 'end', values=row)

    def processo_novo_cadastro(self):
        try:
            d = {k: (v.get().upper() if isinstance(v, (ctk.CTkEntry, ctk.CTkComboBox)) else v.get()) for k, v in
                 self.campos.items()}

            if not d['nome'].strip():
                return messagebox.showwarning("Validação", "Campo 'Nome do Paciente' não pode ficar em branco!")

            horario_atual = datetime.now().strftime('%d/%m/%Y %H:%M')

            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT INTO atendimentos (rm, nome, sus, rg, cpf, nascimento, sexo, naturalidade, est_civil, cor, mae, pai, ocupacao, endereco, telefone, data_registro)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (d['rm'], d['nome'], d['sus'], d['rg'], d['cpf'], d['nasc'], d['sexo'], d['naturalidade'],
                       d['est_civil'], d['cor'], d['mae'], d['pai'], d['ocupacao'], d['end'], d['tel'], horario_atual))
            id_atendimento = c.lastrowid
            conn.commit()
            conn.close()

            d['id_atendimento'] = f"{id_atendimento:06d}"
            d['data_atendimento'] = horario_atual

            path = self.gerar_pdf_completo(d)
            if path and os.path.exists(path): os.startfile(path)

            for k, w in self.campos.items():
                if k != 'rm' and isinstance(w, ctk.CTkEntry): w.delete(0, 'end')

            self.reset_rm()
            self.pesquisar_paciente()
            messagebox.showinfo("Sucesso", "Ficha impressa e paciente indexado!")

        except Exception as e:
            messagebox.showerror("Erro de Gravação", f"Houve uma falha interna ao salvar: {e}")

    def abrir_modal_detalhes(self):
        item_selecionado = self.tabela.selection()
        if not item_selecionado: return

        valores = self.tabela.item(item_selecionado)['values']

        # Correção definitiva: Trata o RM puramente como texto sem tentar converter int()
        rm_linha = str(valores[0]).strip()
        nome_linha = str(valores[1]).strip()
        cpf_linha = str(valores[2]).strip()

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''SELECT *, (SELECT COUNT(*) FROM atendimentos WHERE rm = t.rm) as total_entradas 
                              FROM atendimentos t
                              WHERE (nome = ? AND cpf = ?) OR rm = ? 
                              ORDER BY id DESC LIMIT 1''', (nome_linha, cpf_linha, rm_linha))
            p = cursor.fetchone()
            conn.close()

            if p:
                def obtener(row, chave):
                    try:
                        # Proteção contra erros de índice se o banco estiver corrompido
                        return row[chave] if row[chave] is not None else "---"
                    except (IndexError, KeyError):
                        return "---"

                dados = {
                    'rm': obtener(p, 'rm'), 'nome': obtener(p, 'nome'), 'sus': obtener(p, 'sus'),
                    'rg': obtener(p, 'rg'), 'cpf': obtener(p, 'cpf'), 'nascimento': obtener(p, 'nascimento'),
                    'sexo': obtener(p, 'sexo'), 'naturalidade': obtener(p, 'naturalidade'),
                    'est_civil': obtener(p, 'est_civil'),
                    'cor': obtener(p, 'cor'), 'telefone': obtener(p, 'telefone'), 'mae': obtener(p, 'mae'),
                    'pai': obtener(p, 'pai'), 'ocupacao': obtener(p, 'ocupacao'), 'endereco': obtener(p, 'endereco'),
                    'total_entradas': p['total_entradas']
                }
                ModalDetalhesPaciente(dados, self.root, self.processo_nova_entrada_retorno)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao renderizar dados do paciente: {e}")

    def processo_nova_entrada_retorno(self, dados_paciente):
        try:
            horario_atual = datetime.now().strftime('%d/%m/%Y %H:%M')

            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT INTO atendimentos (rm, nome, sus, rg, cpf, nascimento, sexo, naturalidade, est_civil, cor, mae, pai, ocupacao, endereco, telefone, data_registro)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (dados_paciente['rm'], dados_paciente['nome'], dados_paciente['sus'], dados_paciente['rg'],
                       dados_paciente['cpf'],
                       dados_paciente['nascimento'], dados_paciente['sexo'], dados_paciente['naturalidade'],
                       dados_paciente['est_civil'], dados_paciente['cor'], dados_paciente['mae'], dados_paciente['pai'],
                       dados_paciente['ocupacao'], dados_paciente['endereco'], dados_paciente['telefone'],
                       horario_atual))
            id_novo_atendimento = c.lastrowid
            conn.commit()
            conn.close()

            dados_pdf = dados_paciente.copy()
            dados_pdf['id_atendimento'] = f"{id_novo_atendimento:06d}"
            dados_pdf['data_atendimento'] = horario_atual

            path = self.gerar_pdf_completo(dados_pdf)
            if path and os.path.exists(path): os.startfile(path)

            self.pesquisar_paciente()
            messagebox.showinfo("Re-Admissão",
                                f"Novo atendimento gerado com sucesso!\nNº Entrada: {id_novo_atendimento:06d}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao criar registro de retorno: {e}")

    def gerar_pdf_completo(self, d):
        nome_arquivo = f"Atend_{d['id_atendimento']}_RM_{d['rm']}.pdf"
        path = os.path.abspath(os.path.join(self.pdf_folder, nome_arquivo))

        c = canvas.Canvas(path, pagesize=A4)

        # --- CABEÇALHO INSTITUCIONAL REDESENHADO (LADO ESQUERDO) ---
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(40, 815, "HOSPITAL MUNICIPAL DE VIGIA DE NAZARE")
        c.setFont("Helvetica", 6.5)
        c.drawString(40, 805, "AVENIDA: BARÃO DE GUAJARA, SN - CASTANHEIRA - VIGIA/PA")
        c.drawString(40, 796, "CNPJ: 05.351.606/0001-95 ")

        # --- INSERÇÃO DA LOGO LOCAL EXTENDIDA (LADO DIREITO - ALINHADO) ---
        # Certifique-se de que a imagem combinada Prefeitura/HMRV esteja salva como 'logo.jpg'
        base_dir = os.path.join(os.path.expanduser("~"), "Documents", "SISTGESTOR_HMV")
        caminho_logo = os.path.join(base_dir, "logo.jpg")

        if os.path.exists(caminho_logo):
            try:
                # X=365 posiciona o início do bloco de logos estendido logo após o texto institucional
                # Y=793 com altura=32 mantém a proporção horizontal idêntica ao modelo real
                c.drawImage(caminho_logo, 365, 793, width=190, height=32, mask='auto', preserveAspectRatio=True)
            except Exception as e:
                print(f"Erro ao renderizar a imagem logo.jpg: {e}")
        else:
            print(f"Aviso: O arquivo {caminho_logo} não foi encontrado.")

        # Linha divisória logo abaixo do bloco de identificação e das logos
        c.line(40, 788, 555, 788)

        # --- DADOS DA ADMISSÃO ATUALIZADOS ---
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, 773, f"PRONTUÁRIO: {d['rm']}")
        c.drawString(170, 773, f"Nº ATENDIMENTO: {d['id_atendimento']}")
        c.drawString(300, 773, f"DATA/HORA: {d['data_atendimento']}")
        c.drawString(470, 773, f"SEXO: {d.get('sexo', '')[:1]}")

        # ... (restante do código do ReportLab permanece igual para triagem e prescrição)
        c.drawString(40, 756, f"PACIENTE: {d['nome']}")
        c.drawString(470, 756, f"EST. CIVIL: {d.get('est_civil', '')}")
        c.drawString(40, 741, f"CPF: {d.get('cpf', '')}")
        c.drawString(170, 741, f"RG: {d.get('rg', '')}")
        c.drawString(300, 741, f"SUS: {d.get('sus', '')}")
        c.drawString(470, 741, f"NASC.: {d.get('nascimento', '')}")

        c.drawString(40, 726, f"NATURALIDADE: {d.get('naturalidade', '')}")
        c.drawString(300, 726, f"RAÇA/COR: {d.get('cor', '')}")
        c.drawString(470, 726, f"FONE: {d.get('telefone', '')}")

        c.drawString(40, 711, f"MÃE: {d.get('mae', '')}")
        c.drawString(300, 711, f"PAI: {d.get('pai', '')}")

        c.drawString(40, 696, f"ENDEREÇO: {d.get('endereco', '')}")
        c.drawString(300, 696, f"OCUPAÇÃO: {d.get('ocupacao', '')}")

        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, 666, "CARÁTER DO ATENDIMENTO:  [  ] URGÊNCIA   [  ] EMERGÊNCIA   [  ] ELETIVO")
        c.line(40, 661, 555, 661)

        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(40, 643, 515, 12, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(297, 646, "CLASSIFICAÇÃO DE RISCO / TRIAGEM")
        c.setFont("Helvetica", 7)
        c.drawString(45, 628,
                     "PA: ________ X ________  FC: ________  GLICEMIA: ________  PESO: ________  TEMP: ________  SpO2: ________")
        c.drawString(45, 613,
                     "ALERGIAS: _________________________________________________________________________________")
        c.drawString(45, 598,
                     "QUEIXAS PRINCIPAIS: ________________________________________________________________________")

        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(40, 578, 515, 12, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(297, 581, "ATENDIMENTO MÉDICO / EXAME CLÍNICO")
        c.rect(40, 433, 515, 140)

        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(40, 413, 515, 12, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(297, 416, "PRESCRIÇÃO MÉDICA / CONDUTA INTERNA")
        for i in range(8):
            y = 393 - (i * 18)
            c.line(40, y, 480, y)
            c.drawString(485, y + 2, "HORA: ______")

        c.setFont("Helvetica-Bold", 7)
        c.drawString(45, 243,
                     "HIPÓTESE DIAGNÓSTICA: _________________________________________________  CID: __________")
        c.drawString(45, 228,
                     "OBSERVAÇÕES: _______________________________________________________________________________")
        c.drawString(45, 213, "TIPO DE ALTA: [ ] MELHORADA [ ] INTERNAÇÃO [ ] ÓBITO [ ] EVASÃO [ ] TRANSFERÊNCIA")
        c.drawString(45, 198,
                     "PROCEDIMENTOS EXECUTADOS: _________________________________________________________________")

        c.line(50, 60, 180, 60)
        c.drawCentredString(115, 52, "ASSINATURA PACIENTE")
        c.line(230, 60, 360, 60)
        c.drawCentredString(295, 52, "ENFERMAGEM")
        c.line(410, 60, 540, 60)
        c.drawCentredString(475, 52, "MÉDICO")

        c.save()
        return path


if __name__ == "__main__":
    root = ctk.CTk()
    app = SISTGESTOR_HMV_V4(root)
    root.mainloop()
