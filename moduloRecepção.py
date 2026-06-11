
import os
import sys
import sqlite3
import requests
from io import BytesIO
from datetime import datetime
import customtkinter as ctk
from tkinter import ttk, messagebox
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import threading
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# --- CONFIGURAÇÃO GLOBAL DE APARÊNCIA ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


# --- FUNÇÕES AUXILIARES ---

def caminho_recurso(relative_path):
    """ Retorna o caminho absoluto para o recurso, tanto em desenvolvimento quanto no .exe """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def calcular_idade(data_nasc_str):
    """Calcula a idade exata em anos a partir do formato DD/MM/AAAA"""
    if not data_nasc_str or data_nasc_str.strip() in ("", "---"):
        return "---"
    try:
        data_nasc = datetime.strptime(data_nasc_str.strip(), '%d/%m/%Y')
        hoje = datetime.now()
        idade = hoje.year - data_nasc.year - ((hoje.month, hoje.day) < (data_nasc.month, data_nasc.day))
        return f"{idade} ANOS"
    except Exception:
        return data_nasc_str


# --- MODAL DE AUTENTICAÇÃO RESTRITA ---
class ModalLoginAdmin(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success

        self.title("ACESSO RESTRITO")
        self.geometry("380x200")
        self.resizable(False, False)

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
        if self.input_senha.get() == "SUA SENHA AQUI":
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

        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (900 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (650 // 2)
        self.geometry(f"900x650+{x}+{y}")

        self.transient(parent)
        self.grab_set()

        main_frame = ctk.CTkFrame(self, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(main_frame, text="📊 DASHBOARD INDICADORES & RELATÓRIOS", font=("Segoe UI", 16, "bold"),
                     text_color="#38bdf8").pack(pady=15)

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
        conn = sqlite3.connect(self.db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute(query, params)
        dados = cursor.fetchall()

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
        canvas_pdf.setFont("Helvetica-Bold", 11)
        canvas_pdf.drawString(40, 800, "HOSPITAL MUNICIPAL DE VIGIA DE NAZARÉ - PA")
        canvas_pdf.setFont("Helvetica", 9)
        canvas_pdf.drawString(40, 785, f"RELATÓRIO ADMINISTRATIVO DE ADMISSÕES - FILTRO: {tipo_filtro.upper()}")
        canvas_pdf.drawString(40, 772,
                              f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Total do Período: {len(dados)} atendimentos")
        canvas_pdf.line(40, 765, 555, 765)

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


# --- MODAL DE DETALHES E HISTÓRICO CLINICO ---
class ModalDetalhesPaciente(ctk.CTkToplevel):
    def __init__(self, dados, parent, callback_novo_atendimento, callback_reimprimir):
        super().__init__(parent)
        self.dados = dados
        self.callback_novo_atendimento = callback_novo_atendimento
        self.callback_reimprimir = callback_reimprimir

        self.title(f"HISTÓRICO CLÍNICO - RM: {dados.get('rm', '---')}")
        self.geometry("600x720")
        self.resizable(False, False)

        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (600 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (720 // 2)
        self.geometry(f"600x720+{x}+{y}")

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

        idade_visual = calcular_idade(dados.get('nascimento', ''))

        exibir = [
            ('RM (Prontuário):', 'rm'), ('Nome do Paciente:', 'nome'), ('CPF:', 'cpf'),
            ('Cartão SUS:', 'sus'), ('RG:', 'rg'), ('Idade:', 'idade_calculada'),
            ('Sexo:', 'sexo'), ('Naturalidade:', 'naturalidade'), ('Estado Civil:', 'est_civil'),
            ('Cor/Raça:', 'cor'), ('Profissão/Ocupação:', 'ocupacao'), ('Mãe:', 'mae'),
            ('Pai:', 'pai'), ('Endereço:', 'endereco'), ('Telefone:', 'telefone')
        ]

        for idx, (label, chave) in enumerate(exibir):
            lbl = ctk.CTkLabel(grid_dados, text=label, font=("Segoe UI", 11, "bold"), anchor="w")
            lbl.grid(row=idx, column=0, padx=10, pady=4, sticky="w")

            if chave == 'idade_calculada':
                texto_val = idade_visual
            else:
                texto_val = str(dados.get(chave, "---"))

            val = ctk.CTkLabel(grid_dados, text=texto_val, font=("Segoe UI", 12), anchor="w", justify="left",
                               wraplength=350)
            val.grid(row=idx, column=1, padx=10, pady=4, sticky="w")

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", pady=15, padx=20)

        self.btn_reimprimir = ctk.CTkButton(btn_box, text="🖨️ REIMPRIMIR ÚLTIMA FICHA DESTE PACIENTE",
                                            font=("Segoe UI", 13, "bold"), fg_color="#eab308", hover_color="#ca8a04",
                                            text_color="#1e293b", command=self.reimprimir_ficha)
        self.btn_reimprimir.pack(fill="x", pady=5)

        self.btn_novo_atendimento = ctk.CTkButton(btn_box, text="🔄 REAPROVEITAR REGISTRO (GERAR RETORNO)",
                                                  font=("Segoe UI", 13, "bold"), fg_color="#0284c7",
                                                  hover_color="#0369a1", command=self.gerar_retorno)
        self.btn_novo_atendimento.pack(fill="x", pady=5)

        self.btn_fechar = ctk.CTkButton(btn_box, text="FECHAR JANELA", font=("Segoe UI", 13), fg_color="#34495e",
                                        hover_color="#2c3e50", command=self.destroy)
        self.btn_fechar.pack(fill="x")

    def gerar_retorno(self):
        self.callback_novo_atendimento(self.dados)
        self.destroy()

    def reimprimir_ficha(self):
        self.callback_reimprimir(self.dados)
        self.destroy()


class ModalSobre(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sobre o Sistema")
        self.geometry("500x550")
        self.transient(parent)
        self.grab_set()

        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (500 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (550 // 2)
        self.geometry(f"500x550+{x}+{y}")

        scroll = ctk.CTkScrollableFrame(self, label_text="Informações do Sistema")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        texto = """
🏥 MODULO RECEPÇÃO
Desenvolvido para o Hospital Municipal de Vigia de Nazaré - PA.

👨‍💻 DESENVOLVEDOR: JOSE AIRTON B. S. JUNIOR
Setor de Tecnologia da Informação (T.I.)
Fone/ZAP: (91) 98325-2639

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
        self.root.title("MODULO RECEPÇÃO - HOSPITAL MUNICIPAL DE VIGIA DE NAZARÉ - PA - SUPORTE - 91 983252639 ")
        self.root.geometry("1340x840")

        self.campos = {}

        base_dir = os.path.join(os.path.expanduser("~"), "Documents", "SISTGESTOR_HMV")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        self.db_path = os.path.join(base_dir, "banco_hmv.db")
        self.pdf_folder = os.path.join(base_dir, "atendimentos_pdf")
        if not os.path.exists(self.pdf_folder):
            os.makedirs(self.pdf_folder)

        self.criar_banco()
        self.ajustar_estilo_tabelas()
        self.init_ui()

    def criar_banco(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, rm TEXT, nome TEXT, sus TEXT, 
            rg TEXT, cpf TEXT, nascimento TEXT, sexo TEXT, naturalidade TEXT, 
            est_civil TEXT, cor TEXT, telefone TEXT, mae TEXT, pai TEXT, 
            ocupacao TEXT, endereco TEXT, data_registro TIMESTAMP)''')
            conn.commit()

            cursor.execute("PRAGMA table_info(atendimentos)")
            colunas_existentes = [coluna[1] for coluna in cursor.fetchall()]

            novas_colunas = ['solicitante', 'procedencia', 'responsavel']
            for nova_coluna in novas_colunas:
                if nova_coluna not in colunas_existentes:
                    try:
                        cursor.execute(f"ALTER TABLE atendimentos ADD COLUMN {nova_coluna} TEXT")
                        conn.commit()
                    except sqlite3.OperationalError:
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

        ctk.CTkLabel(header, text="🏥 URGÊNCIA/EMERGÊNCIA", font=("Segoe UI", 15, "bold"), text_color="white").pack(
            side="left", padx=20, pady=15)

        self.btn_admin_modal = ctk.CTkButton(header, text="📊 PAINEL GERAL ADM", font=("Segoe UI", 12, "bold"),
                                             fg_color="#6366f1", hover_color="#4f46e5", height=32,
                                             command=self.solicitar_acesso_adm)
        self.btn_admin_modal.pack(side="right", padx=15, pady=15)

        self.btn_sobre = ctk.CTkButton(header, text="ℹ️ SOBRE", font=("Segoe UI", 12, "bold"), fg_color="#334155",
                                       hover_color="#475569", width=100, height=32,
                                       command=lambda: ModalSobre(self.root))
        self.btn_sobre.pack(side="right", padx=5, pady=15)

        ctk.CTkLabel(header, text="Vigia de Nazaré - PA / COD01", font=("Segoe UI", 12, "italic"),
                     text_color="#ecf0f1").pack(side="right", padx=20, pady=15)

        main_body = ctk.CTkFrame(master=self.root, fg_color="transparent")
        main_body.pack(fill="both", expand=True, padx=15, pady=15)

        left_column = ctk.CTkFrame(master=main_body, width=460, corner_radius=12)
        left_column.pack(side="left", fill="both", padx=(0, 10), pady=0)

        ctk.CTkLabel(left_column, text="📋 RECEPCIONAR PACIENTE", font=("Segoe UI", 14, "bold"),
                     text_color="#38bdf8").pack(pady=12, padx=20, anchor="w")

        grid_frame = ctk.CTkFrame(left_column, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=15, pady=5)

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

        # --- CONSTRUÇÃO DOS CAMPOS DE CADASTRO ---
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

        # --- COLUNA DA DIREITA (BUSCA E TABELA) ---
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

        # O clique agora chama a sua versão corrigida por ID único
        self.tabela.bind("<<TreeviewSelect>>", lambda event: self.abrir_modal_detalhes())

        # --- FINAL ABSOLUTO DA FUNÇÃO (O LUGAR CERTO) ---
        self.reset_rm()
        self.pesquisar_paciente()

        # --- ATIVAÇÃO DO BACKUP AUTOMÁTICO ---
        self.iniciar_agendador_backup()

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
        termo = self.input_busca.get().strip()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Agrupamos por NOME, CPF e SUS para separar na tabela pessoas com o mesmo nome
        # E puxamos o t.id (ID único do registro) para ser a nossa chave de busca absoluta
        cursor.execute('''
            SELECT t.rm, t.nome, t.cpf, t.data_registro, r.total_retornos, t.id
            FROM atendimentos t
            JOIN (
                SELECT nome, cpf, sus, MAX(id) as max_id, COUNT(id) as total_retornos 
                FROM atendimentos 
                GROUP BY nome, cpf, sus
            ) r ON t.id = r.max_id
            WHERE t.nome LIKE ? OR t.rm LIKE ? OR t.cpf LIKE ?
            ORDER BY t.id DESC
        ''', (f'%{termo}%', f'%{termo}%', f'%{termo}%'))

        dados = cursor.fetchall()
        conn.close()

        for item in self.tabela.get_children():
            self.tabela.delete(item)

        for row in dados:
            # O row[5] é o ID único do banco. Nós injetamos ele no 'iid' (ID interno da linha)
            self.tabela.insert('', 'end', iid=str(row[5]), values=(row[0], row[1], row[2], row[3], row[4]))

    def processo_novo_cadastro(self):
        try:
            d = {k: (v.get().upper() if isinstance(v, (ctk.CTkEntry, ctk.CTkComboBox)) else v.get()) for k, v in
                 self.campos.items()}

            nome_limpo = d['nome'].strip()
            if not nome_limpo:
                return messagebox.showwarning("Validação", "Campo 'Nome do Paciente' não pode ficar em branco!")

            # --- LOGICA ANTIDUPLICIDADE INTELIGENTE ---
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            # 1. Verifica duplicidade por nome completo exato
            c.execute("SELECT rm FROM atendimentos WHERE nome = ? LIMIT 1", (nome_limpo,))
            resultado_nome = c.fetchone()

            if resultado_nome:
                conn.close()
                return messagebox.showerror(
                    "Paciente Já Cadastrado",
                    f"Atenção! O paciente '{nome_limpo}' já possui o prontuário RM: {resultado_nome[0]}.\n\n"
                    "Para evitar duplicar o RM, use o campo de busca à direita, clique no nome do paciente e selecione 'REAPROVEITAR REGISTRO (GERAR RETORNO)'."
                )

            # 2. Verifica duplicidade secundária por CPF (se preenchido)
            cpf_limpo = d['cpf'].strip()
            if cpf_limpo and cpf_limpo not in ("", "000.000.000-00", "---"):
                c.execute("SELECT rm, nome FROM atendimentos WHERE cpf = ? LIMIT 1", (cpf_limpo,))
                resultado_cpf = c.fetchone()
                if resultado_cpf:
                    conn.close()
                    return messagebox.showerror(
                        "CPF Já Vinculado",
                        f"O CPF '{cpf_limpo}' já está cadastrado para o paciente: '{resultado_cpf[1]}' (RM: {resultado_cpf[0]}).\n\n"
                        "Por favor, use o prontuário existente."
                    )

            # 3. Verifica duplicidade secundária por Cartão SUS (se preenchido)
            sus_limpo = d['sus'].strip()
            if sus_limpo and sus_limpo not in ("", "---"):
                c.execute("SELECT rm, nome FROM atendimentos WHERE sus = ? LIMIT 1", (sus_limpo,))
                resultado_sus = c.fetchone()
                if resultado_sus:
                    conn.close()
                    return messagebox.showerror(
                        "Cartão SUS Já Vinculado",
                        f"O Cartão SUS '{sus_limpo}' já está cadastrado para o paciente: '{resultado_sus[1]}' (RM: {resultado_sus[0]}).\n\n"
                        "Por favor, use o prontuário existente."
                    )

            # Se passar por todas as travas, realiza a inserção normal
            horario_atual = datetime.now().strftime('%d/%m/%Y %H:%M')

            c.execute('''INSERT INTO atendimentos (rm, nome, sus, rg, cpf, nascimento, sexo, naturalidade, est_civil, cor, mae, pai, ocupacao, endereco, telefone, data_registro)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (d['rm'], nome_limpo, d['sus'], d['rg'], d['cpf'], d['nasc'], d['sexo'], d['naturalidade'],
                       d['est_civil'], d['cor'], d['mae'], d['pai'], d['ocupacao'], d['end'], d['tel'], horario_atual))
            id_atendimento = c.lastrowid
            conn.commit()
            conn.close()

            d['id_atendimento'] = f"{id_atendimento:06d}"
            d['data_atendimento'] = horario_atual

            path = self.gerar_pdf_completo(d)
            if path and os.path.exists(path):
                os.startfile(path)

            for k, w in self.campos.items():
                if k != 'rm' and isinstance(w, ctk.CTkEntry):
                    w.delete(0, 'end')

            self.reset_rm()
            self.pesquisar_paciente()
            messagebox.showinfo("Sucesso", "Ficha impressa e paciente indexado!")

        except Exception as e:
            messagebox.showerror("Erro de Gravação", f"Houve uma falha interna ao salvar: {e}")

    def abrir_modal_detalhes(self):
        item_selecionado = self.tabela.selection()
        if not item_selecionado:
            return

        # Captura o ID real do banco que guardamos no iid da linha
        id_registro_real = item_selecionado[0]

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Mantém a compatibilidade se seu modal usa dicionário
            cursor = conn.cursor()

            # BUSCA INFALÍVEL: Busca exatamente a linha da pessoa clicada pelo ID único
            cursor.execute("SELECT * FROM atendimentos WHERE id = ?", (id_registro_real,))
            linha_base = cursor.fetchone()

            if not linha_base:
                conn.close()
                return messagebox.showwarning("Aviso", "Não foi possível localizar o registro selecionado.")

            dados_paciente = dict(linha_base)

            # Recalcula o total de entradas para esta pessoa específica (mesmo nome + mesmos documentos)
            cursor.execute('''
                SELECT COUNT(*) FROM atendimentos 
                WHERE nome = ? AND (
                    (cpf = ? AND cpf NOT IN ('', '000.000.000-00', '---')) OR 
                    (sus = ? AND sus NOT IN ('', '---')) OR 
                    (nascimento = ?)
                )
            ''', (dados_paciente['nome'], dados_paciente['cpf'], dados_paciente['sus'], dados_paciente['nascimento']))

            dados_paciente['total_entradas'] = cursor.fetchone()[0] or 1
            conn.close()

            # Abre o seu modal original de produção passand os dados exatos e sem duplicidade
            ModalDetalhesPaciente(
                dados_paciente,
                self.root,
                self.processo_nova_entrada_retorno,
                self.processo_reimpressao_ficha
            )

        except Exception as e:
            messagebox.showerror("Erro ao renderizar dados", f"Falha no carregamento controlado: {e}")
    def processo_nova_entrada_retorno(self, dados_antigos):
        """ Método de Callback para gerar um novo atendimento a partir de dados históricos (Retorno) """
        try:
            # Limpa o formulário antes de injetar os dados para reuso
            for k, w in self.campos.items():
                if k != 'rm' and isinstance(w, ctk.CTkEntry):
                    w.delete(0, 'end')

            # Preenche o formulário com o acervo do paciente
            mapeamento = {
                'nome': dados_antigos.get('nome', ''),
                'sus': dados_antigos.get('sus', ''),
                'rg': dados_antigos.get('rg', ''),
                'cpf': dados_antigos.get('cpf', ''),
                'nasc': dados_antigos.get('nascimento', ''),
                'naturalidade': dados_antigos.get('naturalidade', ''),
                'ocupacao': dados_antigos.get('ocupacao', ''),
                'mae': dados_antigos.get('mae', ''),
                'pai': dados_antigos.get('pai', ''),
                'end': dados_antigos.get('endereco', ''),
                'tel': dados_antigos.get('telefone', '')
            }

            for chave, valor in mapeamento.items():
                if chave in self.campos and isinstance(self.campos[chave], ctk.CTkEntry):
                    self.campos[chave].insert(0, str(valor) if valor and valor != "None" else "")

            if 'sexo' in self.campos and dados_antigos.get('sexo') in ["MASCULINO", "FEMININO"]:
                self.campos['sexo'].set(dados_antigos.get('sexo'))
            if 'est_civil' in self.campos and dados_antigos.get('est_civil'):
                self.campos['est_civil'].set(dados_antigos.get('est_civil'))
            if 'cor' in self.campos and dados_antigos.get('cor'):
                self.campos['cor'].set(dados_antigos.get('cor'))

            # Força o reaproveitamento do RM original do histórico do paciente
            self.campos['rm'].configure(state="normal")
            self.campos['rm'].delete(0, 'end')
            self.campos['rm'].insert(0, str(dados_antigos.get('rm')).zfill(5))
            self.campos['rm'].configure(state="readonly")

            # Altera a ação do botão salvador para focar na execução exclusiva do retorno
            self.btn_salvar.configure(
                text="💾 CONFIRMAR RETORNO (IMPRIMIR)",
                fg_color="#0284c7", hover_color="#0369a1",
                command=lambda: self.executar_insercao_retorno(str(dados_antigos.get('rm')).zfill(5))
            )
            messagebox.showinfo("Retorno Carregado",
                                f"Prontuário RM {str(dados_antigos.get('rm')).zfill(5)} pronto para reuso. Clique em 'CONFIRMAR RETORNO' para concluir.")

        except Exception as e:
            messagebox.showerror("Erro de Retorno", f"Falha ao carregar dados antigos: {e}")

    def executar_insercao_retorno(self, rm_antigo):
        """ Insere o novo atendimento pulando as validações de bloqueio de duplicidade """
        try:
            d = {k: (v.get().upper() if isinstance(v, (ctk.CTkEntry, ctk.CTkComboBox)) else v.get()) for k, v in
                 self.campos.items()}

            nome_limpo = d['nome'].strip()
            if not nome_limpo:
                return messagebox.showwarning("Validação", "Campo 'Nome do Paciente' não pode ficar em branco!")

            horario_atual = datetime.now().strftime('%d/%m/%Y %H:%M')

            # Salva direto no banco associando ao RM antigo (Sem passar pelas travas de bloqueio)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT INTO atendimentos (rm, nome, sus, rg, cpf, nascimento, sexo, naturalidade, est_civil, cor, mae, pai, ocupacao, endereco, telefone, data_registro)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (rm_antigo, nome_limpo, d['sus'], d['rg'], d['cpf'], d['nasc'], d['sexo'], d['naturalidade'],
                       d['est_civil'], d['cor'], d['mae'], d['pai'], d['ocupacao'], d['end'], d['tel'], horario_atual))
            id_atendimento = c.lastrowid
            conn.commit()
            conn.close()

            d['id_atendimento'] = f"{id_atendimento:06d}"
            d['data_atendimento'] = horario_atual
            d['rm'] = rm_antigo

            # Gera o PDF com base nos dados capturados
            path = self.gerar_pdf_completo(d)
            if path and os.path.exists(path):
                os.startfile(path)

            # Limpa os campos após o sucesso
            for k, w in self.campos.items():
                if k != 'rm' and isinstance(w, ctk.CTkEntry):
                    w.delete(0, 'end')

            # Restaura o botão para o modo padrão (Novo cadastro)
            self.btn_salvar.configure(
                text="💾 IMPRIMIR E ENVIAR PARA A TRIAGEM",
                fg_color="#22c55e", hover_color="#16a34a",
                command=self.processo_novo_cadastro
            )

            self.reset_rm()
            self.pesquisar_paciente()
            messagebox.showinfo("Sucesso", "Nova entrada (Retorno) registrada com sucesso para este prontuário!")

        except Exception as e:
            messagebox.showerror("Erro no Retorno", f"Falha interna ao gravar retorno: {e}")

    def processo_reimpressao_ficha(self, dados_paciente):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''SELECT id, data_registro FROM atendimentos 
                              WHERE rm = ? ORDER BY id DESC LIMIT 1''', (dados_paciente['rm'],))
            resultado = cursor.fetchone()
            conn.close()

            if resultado:
                id_atendimento, data_atendimento = resultado
                dados_pdf = dados_paciente.copy()
                dados_pdf['id_atendimento'] = f"{id_atendimento:06d}"
                dados_pdf['data_atendimento'] = data_atendimento

                dados_pdf['nasc'] = dados_paciente.get('nascimento')
                dados_pdf['end'] = dados_paciente.get('endereco')
                dados_pdf['tel'] = dados_paciente.get('telefone')

                path = self.gerar_pdf_completo(dados_pdf)
                if path and os.path.exists(path):
                    os.startfile(path)
                    messagebox.showinfo("Reimpressão",
                                        f"Segunda via da Ficha Nº {id_atendimento:06d} enviada para o leitor de PDF!")
            else:
                messagebox.showwarning("Erro",
                                       "Não foi encontrado nenhum atendimento ativo no histórico para gerar a segunda via.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar segunda via da ficha: {e}")

    def gerar_pdf_completo(self, d):
        nome_arquivo = f"Atend_{d['id_atendimento']}_RM_{d['rm']}.pdf"
        path = os.path.abspath(os.path.join(self.pdf_folder, nome_arquivo))

        c = canvas.Canvas(path, pagesize=A4)

        # --- CABEÇALHO INSTITUCIONAL ---
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, 815, "HOSPITAL MUNICIPAL DE VIGIA DE NAZARE")
        c.setFont("Helvetica", 7.5)
        c.drawString(40, 804, "AVENIDA: BARÃO DE GUAJARÁ, S/N - CASTANHEIRA - VIGIA/PA")
        c.drawString(40, 794, "CNPJ: 05.351.606/0001-95")

        # Inserção das marcas consolidadas via caminho isolado (funciona em desenvolvimento e no .exe)
        caminho_logo = caminho_recurso("logo.jpg")
        if os.path.exists(caminho_logo):
            c.drawImage(caminho_logo, 380, 792, width=175, height=32, mask='auto')

        c.setLineWidth(1)
        c.line(40, 785, 555, 785)

        # --- DADOS DE IDENTIFICAÇÃO ---
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(40, 770, f"PRONTUÁRIO: {d['rm']}")
        c.drawString(170, 770, f"Nº ATENDIMENTO: {d['id_atendimento']}")
        c.drawString(320, 770, f"DATA/HORA: {d['data_atendimento']}")
        c.drawString(485, 770, f"SEXO: {d['sexo'][0] if d['sexo'] else 'M'}")

        c.drawString(40, 752, f"PACIENTE: {d['nome']}")
        c.drawString(485, 752, f"EST. CIVIL: {d['est_civil']}")

        c.drawString(40, 735, f"CPF: {d['cpf']}")
        c.drawString(180, 735, f"RG: {d['rg']}")
        c.drawString(320, 735, f"SUS: {d['sus']}")

        data_orig = d.get('nasc', d.get('nascimento', '---'))
        idade_final = calcular_idade(data_orig)
        c.drawString(485, 735, f"IDADE: {idade_final}")

        c.drawString(40, 718, f"NATURALIDADE: {d['naturalidade']}")
        c.drawString(320, 718, f"RAÇA/COR: {d['cor']}")
        c.drawString(485, 701, f"FONE: {d['tel'] if 'tel' in d else d.get('telefone', '---')}")

        c.drawString(40, 701, f"MÃE: {d['mae']}")
        c.drawString(320, 701, f"PAI: {d['pai']}")
        c.drawString(485, 718, f"NASCI: {d['nasc']}")

        c.drawString(40, 684, f"ENDEREÇO: {d['end'] if 'end' in d else d.get('endereco', '---')}")
        c.drawString(320, 684, f"OCUPAÇÃO: {d['ocupacao']}")

        c.drawString(40, 665, "CARÁTER DO ATENDIMENTO:    [  ] URGÊNCIA    [  ] EMERGÊNCIA    [  ] ELETIVO")

        c.setLineWidth(1)
        c.line(40, 655, 555, 655)

        # --- SEÇÃO 1: CLASSIFICAÇÃO DE RISCO / TRIAGEM ---
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(40, 638, 515, 14, fill=True, stroke=False)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(297, 641, "CLASSIFICAÇÃO DE RISCO / TRIAGEM")
        c.rect(40, 638, 515, 14, fill=False, stroke=True)

        c.setFont("Helvetica", 7.5)
        c.drawString(40, 622,
                     "HORA;MIN: ______:______  PA: ________ X ________   FC: ________  /GLICEMIA: ________  /PESO: ________  /TEMP: ________  /SpO2: ________")
        c.drawString(40, 607,
                     "HORA/MIN: ______:______  PA: ________ X ________   FC: _________ /GLICEMIA: ________  /PESO: ________  /TEMP: _______  /SpO2: ________")
        c.drawString(40, 589,
                     "DIABETES: [            ]           /HIPERTENSÃO: [           ]          /ASMA: [           ]          /OUTROS: ________________________________________________")
        c.drawString(40, 572,
                     "ALERGIAS: _________________________________________________________________________________________________________________ ")
        c.drawString(40, 553,
                     "QUEIXAS PRINCIPAIS: _______________________________________________________________________________________________________ ")
        c.drawString(40, 537,
                     "___________________________________________________________________________________________________________________________ ")

        # --- SEÇÃO 2: ATENDIMENTO MÉDICO / EXAME CLÍNICO ---
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(40, 518, 515, 14, fill=True, stroke=False)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(297, 521, "ATENDIMENTO MÉDICO / EXAME CLÍNICO")
        c.rect(40, 518, 515, 14, fill=False, stroke=True)

        c.setLineWidth(1)
        c.rect(40, 443, 515, 70, fill=False, stroke=True)

        # --- SEÇÃO 3: PRESCRIÇÃO MÉDICA / CONDUTA INTERNA ---
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(40, 419, 515, 14, fill=True, stroke=False)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(297, 422, "PRESCRIÇÃO MÉDICA / CONDUTA INTERNA")
        c.rect(40, 419, 515, 14, fill=False, stroke=True)

        y_linha = 400
        for _ in range(8):
            c.setLineWidth(0.5)
            c.line(40, y_linha, 490, y_linha)
            c.setFont("Helvetica", 7)
            c.drawString(495, y_linha + 2, "HORA: _________")
            y_linha -= 16

        c.setFont("Helvetica", 7.5)
        c.drawString(40, 265,
                     "HIPÓTESE DIAGNÓSTICA: _________________________________________________________________________________  CID: ______________")
        c.drawString(40, 250,
                     "OBSERVAÇÕES: ____________________________________________________________________________________________________________")
        c.drawString(40, 235,
                     "___________________________________________________________________________________________________________________________")
        c.drawString(40, 220,
                     "___________________________________________________________________________________________________________________________")

        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(40, 195,
                     "TIPO DE ALTA:   [  ] MELHORADA   [  ] INTERNAÇÃO   [  ] ÓBITO   [  ] EVASÃO   [  ] TRANSFERÊNCIA")
        c.drawString(40, 180, "PROCEDIMENTOS EXECUTADOS:")

        # --- ASSINATURAS ---
        c.setLineWidth(0.7)
        c.line(50, 75, 190, 75)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(120, 65, "ASSINATURA PACIENTE")

        c.line(245, 75, 385, 75)
        c.drawCentredString(315, 65, "ENFERMAGEM")

        c.line(430, 75, 545, 75)
        c.drawCentredString(487, 65, "MÉDICO")

        c.save()
        return path

    def iniciar_agendador_backup(self):
        """Inicializa a Thread em segundo plano para monitorar o horário do backup"""

        def loop_agendamento():
            time.sleep(10)  # Aguarda a inicialização completa do app
            while True:
                agora = datetime.now()
                # Monitora a virada da meia-noite (00:00)
                if agora.hour == 0 and agora.minute == 0:
                    self.executar_backup_email_tradicional()
                    time.sleep(60)  # Evita múltiplos disparos no mesmo minuto
                time.sleep(30)  # Checa o relógio a cada 30 segundos

        threading.Thread(target=loop_agendamento, daemon=True).start()

    def executar_backup_email_tradicional(self):
        """Gera uma cópia estática do banco e envia por e-mail via SMTP tradicional"""
        if not os.path.exists(self.db_path):
            return

        # --- CONFIGURAÇÃO DO SEU PROVEDOR DE E-MAIL ---
        SMTP_SERVER = "smtp.gmail.com"  # Para Outlook use: smtp.office365.com
        SMTP_PORT = 587  # Porta padrão para criptografia STARTTLS
        EMAIL_REMETENTE = "juniordomundo@gmail.com"
        EMAIL_DESTINATARIO = "juniordomundo@gmail.com"

        # IMPORTANTE: Se usar Gmail, esta senha deve ser uma "Senha de App" gerada
        # nas configurações de segurança da sua Conta Google, e não a sua senha padrão.
        EMAIL_SENHA = "SENHA DO APP"

        backup_temp = self.db_path + ".bak"

        try:
            # 1. Cópia segura do SQLite em tempo de execução (Hot Backup)
            conn_origem = sqlite3.connect(self.db_path)
            conn_backup = sqlite3.connect(backup_temp)
            conn_origem.backup(conn_backup)
            conn_backup.close()
            conn_origem.close()

            # 2. Montagem da estrutura do E-mail (MIME)
            data_str = datetime.now().strftime('%d/%m/%Y')
            msg = MIMEMultipart()
            msg['From'] = EMAIL_REMETENTE
            msg['To'] = EMAIL_DESTINATARIO
            msg['Subject'] = f"📦 BACKUP AUTOMÁTICO HMV - {data_str}"

            corpo_mensagem = f"""
            Prezado Administrador de T.I.,

            O backup automatizado do banco de dados do SISTGESTOR_HMV foi concluído.

            📌 Arquivo: banco_hmv.db
            📅 Data do Disparo: {data_str} às 00:00
            Status da Operação: Sucesso (Arquivo Anexo)

            Este é um e-mail automático do sistema.
            """
            msg.attach(MIMEText(corpo_mensagem, 'plain'))

            # 3. Preparação do anexo binário (.db)
            nome_anexo = f"Backup_HMV_{datetime.now().strftime('%d_%m_%Y')}.db"
            with open(backup_temp, "rb") as anexo_arquivo:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(anexo_arquivo.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f"attachment; filename= {nome_anexo}")
                msg.attach(part)

            # 4. Conexão Autenticada com o Servidor SMTP
            servidor = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            servidor.starttls()  # Ativa a camada de segurança obrigatoria
            servidor.login(EMAIL_REMETENTE, EMAIL_SENHA)
            servidor.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
            servidor.quit()

        except Exception as e:
            # Grava logs locais caso o hospital fique sem internet na hora do envio
            with open("erro_backup.log", "a") as log:
                log.write(f"[{datetime.now()}] Falha SMTP tradicional: {e}\n")

        finally:
            # Garante a limpeza do arquivo temporário para não ocupar espaço redundante
            if os.path.exists(backup_temp):
                try:
                    os.remove(backup_temp)
                except:
                    pass




# --- INICIALIZAÇÃO SEGURA DO PROJETO ---
if __name__ == "__main__":
    app = ctk.CTk()
    SISTGESTOR_HMV_V4(app)
    app.mainloop()
