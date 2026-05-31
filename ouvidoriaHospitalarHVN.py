import os
import sqlite3
import csv
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DE SEGURANÇA E ARQUIVOS ---
SENHA_ADMIN = "admin123"
DB_NAME = "hospital_ouvidoria.db"


# --- INTERFACE DE BANCO DE DADOS ---
def inicializar_banco():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setor TEXT NOT NULL,
            nota INTEGER NOT NULL,
            rotulo_nota TEXT NOT NULL,
            motivos TEXT,
            carta TEXT,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def salvar_no_banco(setor, nota, rotulo_nota, motivos_lista, carta_texto):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    motivos_str = ", ".join(motivos_lista) if motivos_lista else ""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT INTO avaliacoes (setor, nota, rotulo_nota, motivos, carta, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (setor, nota, rotulo_nota, motivos_str, carta_texto, agora))

    conn.commit()
    conn.close()


# --- APLICATIVO DO TOTEM ---
class OuvidoriaTotemApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Sistema de Ouvidoria Digital - Totem")
        self.attributes("-fullscreen", True)

        # Paleta de Cores Avançada (Slate/Cyber Cyan)
        self.COR_BG = "#090d16"  # Fundo principal ultra-dark
        self.COR_CARD = "#131a2a"  # Fundo dos cards e containers
        self.COR_BORDA = "#1f293d"  # Divisores sutis
        self.COR_TEXTO = "#f8fafc"  # Texto principal claro
        self.COR_MUTED = "#64748b"  # Texto secundário/opaco
        self.COR_CYAN = "#00f0ff"  # Destaques neon

        self.configure(bg=self.COR_BG)

        # Estados de Controle do Fluxo
        self.dados_ouvidoria = {"setor": "", "nota": 0, "rotulo_nota": "", "motivos": [], "carta": ""}
        self.caps_lock = True
        self.dados_locais = []

        self.container = tk.Frame(self, bg=self.COR_BG)
        self.container.pack(expand=True, fill="both", padx=40, pady=40)

        inicializar_banco()
        self.tela_setores()

    def limpar_tela(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def criar_botao_moderno(self, pai, texto, comando, cor_bg=None, cor_fg=None, font=None, width=None, height=None):
        bg = cor_bg if cor_bg else self.COR_CARD
        fg = cor_fg if cor_fg else self.COR_TEXTO
        fnt = font if font else ("Segoe UI", 16, "bold")

        btn = tk.Button(
            pai, text=texto, font=fnt, fg=fg, bg=bg,
            activebackground=self.COR_CYAN, activeforeground=self.COR_BG,
            bd=0, relief="flat", cursor="hand2", command=comando
        )
        if width and height:
            btn.config(width=width, height=height)

        btn.bind("<Enter>", lambda e: btn.config(bg=self.COR_CYAN, fg=self.COR_BG) if bg == self.COR_CARD else None)
        btn.bind("<Leave>", lambda e: btn.config(bg=bg, fg=fg) if bg == self.COR_CARD else None)
        return btn

    # ==========================================
    #             TELA 1: SELEÇÃO DE SETOR
    # ==========================================
    def tela_setores(self):
        self.limpar_tela()

        btn_admin = tk.Button(
            self.container, text="⚙️ Painel Gestor", font=("Segoe UI", 11), fg=self.COR_MUTED, bg=self.COR_BG,
            bd=0, relief="flat", activebackground=self.COR_BG, activeforeground=self.COR_TEXTO,
            command=self.tela_login_admin
        )
        btn_admin.place(relx=1.0, rely=0.0, anchor="ne")

        lbl_titulo = tk.Label(self.container, text="Sua opinião salva vidas.", font=("Segoe UI", 36, "bold"),
                              fg=self.COR_TEXTO, bg=self.COR_BG)
        lbl_titulo.pack(pady=(60, 20))

        lbl_sub = tk.Label(self.container, text="Toque no setor onde você foi atendido hoje para começar:",
                           font=("Segoe UI", 16), fg=self.COR_MUTED, bg=self.COR_BG)
        lbl_sub.pack(pady=(0, 50))

        grid_frame = tk.Frame(self.container, bg=self.COR_BG)
        grid_frame.pack(expand=True)

        setores = ["Pronto Atendimento", "Ambulatório", "Exames e Laboratório", "Internação"]
        for i, setor in enumerate(setores):
            texto_btn = "Ambulatório / Consultas" if setor == "Ambulatório" else (
                "Exames / Laboratório" if setor == "Exames e Laboratório" else setor)
            btn = self.criar_botao_moderno(grid_frame, texto_btn, lambda s=setor: self.selecionar_setor(s), width=50,
                                           height=5)
            btn.grid(row=i // 2, column=i % 2, padx=20, pady=20)

    def selecionar_setor(self, setor):
        self.dados_ouvidoria["setor"] = setor
        self.tela_notas()

    # ==========================================
    #             TELA 2: NOTAS (EMOJIS)
    # ==========================================
    def tela_notas(self):
        self.limpar_tela()

        badge_frame = tk.Frame(self.container, bg=self.COR_CARD, padx=20, pady=6)
        badge_frame.pack(pady=10)
        lbl_badge = tk.Label(badge_frame, text=self.dados_ouvidoria["setor"].upper(), font=("Segoe UI", 11, "bold"),
                             fg=self.COR_CYAN, bg=self.COR_CARD)
        lbl_badge.pack()

        lbl_pergunta = tk.Label(self.container, text="Como você avalia o atendimento geral?",
                                font=("Segoe UI", 26, "bold"), fg=self.COR_TEXTO, bg=self.COR_BG)
        lbl_pergunta.pack(pady=40)

        notas_frame = tk.Frame(self.container, bg=self.COR_BG)
        notas_frame.pack(expand=True)

        opcoes_notas = [
            (1, "Péssimo", "🤬", "#ef4444"),
            (2, "Ruim", "🙁", "#f97316"),
            (3, "Regular", "😐", "#eab308"),
            (4, "Bom", "🙂", "#10b981"),
            (5, "Excelente", "🤩", "#00f0ff")
        ]

        for val, rotulo, emoji, cor in opcoes_notas:
            btn_box = tk.Button(
                notas_frame, text=f"{emoji}\n\n{rotulo}", font=("Segoe UI", 18, "bold"), fg=cor, bg=self.COR_CARD,
                activebackground=cor, activeforeground=self.COR_BG, bd=0, relief="flat", width=14, height=6,
                command=lambda v=val, r=rotulo: self.selecionar_nota(v, r)
            )
            btn_box.pack(side="left", padx=15)

        self.criar_botao_moderno(self.container, "Voltar ao Início", self.tela_setores, cor_fg=self.COR_MUTED,
                                 font=("Segoe UI", 12)).pack(side="bottom", pady=10)

    def selecionar_nota(self, nota, rotulo):
        self.dados_ouvidoria["nota"] = nota
        self.dados_ouvidoria["rotulo_nota"] = rotulo
        self.dados_ouvidoria["motivos"] = []
        self.tela_justificativas()

    # ==========================================
    #             TELA 3: JUSTIFICATIVAS
    # ==========================================
    def tela_justificativas(self):
        self.limpar_tela()

        lbl_pergunta = tk.Label(self.container, text="O que motivou sua nota?", font=("Segoe UI", 26, "bold"),
                                fg=self.COR_TEXTO, bg=self.COR_BG)
        lbl_pergunta.pack(pady=30)

        tags_frame = tk.Frame(self.container, bg=self.COR_BG)
        tags_frame.pack(expand=True)

        if self.dados_ouvidoria["nota"] >= 4:
            motivos = ["Atendimento Rápido", "Instalações Limpas", "Médicos Atenciosos",
                       "Equipe de Enfermagem Excelente", "Recepção Cordial", "Boa Infraestrutura"]
        else:
            motivos = ["Tempo de Espera Longo", "Limpeza / Higiene", "Atendimento da Recepção", "Atendimento Médico",
                       "Atendimento da Enfermagem", "Falta de Assentos / Conforto"]

        self.botoes_tags = {}
        for i, motivo in enumerate(motivos):
            btn = tk.Button(
                tags_frame, text=motivo, font=("Segoe UI", 16), fg=self.COR_TEXTO, bg=self.COR_CARD,
                activebackground=self.COR_BORDA, activeforeground=self.COR_TEXTO, bd=0, relief="flat",
                width=38, height=3, command=lambda m=motivo: self.alternar_tag(m)
            )
            btn.grid(row=i // 2, column=i % 2, padx=15, pady=15)
            self.botoes_tags[motivo] = btn

        self.criar_botao_moderno(self.container, "Confirmar e Avançar ➔", self.tela_carta, cor_bg=self.COR_CYAN,
                                 cor_fg=self.COR_BG, width=22, height=2).pack(side="bottom", pady=20)

    def alternar_tag(self, motivo):
        if motivo in self.dados_ouvidoria["motivos"]:
            self.dados_ouvidoria["motivos"].remove(motivo)
            self.botoes_tags[motivo].configure(bg=self.COR_CARD, fg=self.COR_TEXTO)
        else:
            self.dados_ouvidoria["motivos"].append(motivo)
            self.botoes_tags[motivo].configure(bg="#083344", fg=self.COR_CYAN)

    # ==========================================
    #          TELA 4: CARTA & TECLADO
    # ==========================================
    def tela_carta(self):
        self.limpar_tela()

        lbl_titulo = tk.Label(self.container, text="Deseja deixar um relato detalhado?", font=("Segoe UI", 26, "bold"),
                              fg=self.COR_TEXTO, bg=self.COR_BG)
        lbl_titulo.pack(pady=(10, 5))

        self.txt_carta = tk.Text(
            self.container, font=("Segoe UI", 16), fg=self.COR_TEXTO, bg=self.COR_CARD,
            bd=0, highlightthickness=1, highlightbackground=self.COR_BORDA, highlightcolor=self.COR_CYAN,
            insertbackground="white", width=70, height=4
        )
        self.txt_carta.pack(pady=15)
        self.txt_carta.focus_set()

        frame_teclado = tk.Frame(self.container, bg=self.COR_BG)
        frame_teclado.pack(pady=10)
        self.construir_teclado_virtual(frame_teclado)

        botoes_frame = tk.Frame(self.container, bg=self.COR_BG)
        botoes_frame.pack(side="bottom", pady=10)

        self.criar_botao_moderno(botoes_frame, "Pular / Finalizar", self.finalizar_sem_carta, cor_bg="#1e293b",
                                 width=18, height=2).pack(side="left", padx=15)
        self.criar_botao_moderno(botoes_frame, "Enviar Depoimento ✨", self.finalizar_com_carta, cor_bg=self.COR_CYAN,
                                 cor_fg=self.COR_BG, width=24, height=2).pack(side="right", padx=15)

    def construir_teclado_virtual(self, frame_pai):
        linhas_teclado = [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "⌫"],
            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "´", "[", "]"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L", "Ç", "~", "^"],
            ["Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "CAPS"],
            ["LIMPAR", "ESPAÇO"]
        ]
        self.botoes_letras = []

        for linha in linhas_teclado:
            row_frame = tk.Frame(frame_pai, bg=self.COR_BG)
            row_frame.pack(pady=3)

            for char in linha:
                if char == "ESPAÇO":
                    btn_w, bg_k, fg_k = 48, "#1e293b", self.COR_TEXTO
                    cmd = self.gerar_comando_teclado(" ")
                elif char == "⌫":
                    btn_w, bg_k, fg_k = 8, "#ef4444", self.COR_TEXTO
                    cmd = self.executar_backspace
                elif char == "CAPS":
                    btn_w, bg_k, fg_k = 8, "#083344", self.COR_CYAN
                    cmd = self.alternar_caps_lock
                elif char == "LIMPAR":
                    btn_w, bg_k, fg_k = 10, "#334155", self.COR_TEXTO
                    cmd = self.executar_limpeza
                else:
                    btn_w, bg_k, fg_k = 4, self.COR_CARD, self.COR_TEXTO
                    cmd = self.gerar_comando_teclado(char)

                btn_key = tk.Button(
                    row_frame, text=char, font=("Segoe UI", 13, "bold"), fg=fg_k, bg=bg_k,
                    activebackground=self.COR_CYAN, activeforeground=self.COR_BG, bd=0, relief="flat",
                    width=btn_w, height=2, command=cmd
                )
                btn_key.pack(side="left", padx=3)

                if len(char) == 1 and char.isalpha():
                    self.botoes_letras.append(btn_key)

    def gerar_comando_teclado(self, valor):
        def comando():
            if valor == " ":
                self.txt_carta.insert(tk.INSERT, " ")
            else:
                self.txt_carta.insert(tk.INSERT, valor.upper() if self.caps_lock else valor.lower())
            self.txt_carta.focus_set()

        return comando

    def executar_backspace(self):
        try:
            self.txt_carta.delete("insert-1c", tk.INSERT)
        except tk.TclError:
            pass
        self.txt_carta.focus_set()

    def executar_limpeza(self):
        self.txt_carta.delete("1.0", tk.END)
        self.txt_carta.focus_set()

    def alternar_caps_lock(self):
        self.caps_lock = not self.caps_lock
        for btn in self.botoes_letras:
            t = btn.cget("text")
            btn.configure(text=t.upper() if self.caps_lock else t.lower())
        self.txt_carta.focus_set()

    def finalizar_sem_carta(self):
        self.dados_ouvidoria["carta"] = ""
        self.finalizar_fluxo()

    def finalizar_com_carta(self):
        self.dados_ouvidoria["carta"] = self.txt_carta.get("1.0", "end-1c").strip()
        self.finalizar_fluxo()

    def finalizar_fluxo(self):
        salvar_no_banco(
            self.dados_ouvidoria["setor"],
            int(self.dados_ouvidoria["nota"]),
            self.dados_ouvidoria["rotulo_nota"],
            self.dados_ouvidoria["motivos"],
            self.dados_ouvidoria["carta"]
        )
        self.limpar_tela()
        lbl_sucesso = tk.Label(self.container, text="🤩\n\nMuito obrigado!\nSeu relato foi salvo.",
                               font=("Segoe UI", 32, "bold"), fg=self.COR_CYAN, bg=self.COR_BG)
        lbl_sucesso.pack(expand=True)
        self.after(2500, self.resetar_totem)

    def resetar_totem(self):
        self.dados_ouvidoria = {"setor": "", "nota": 0, "rotulo_nota": "", "motivos": [], "carta": ""}
        self.tela_setores()

    # ==========================================
    #             PAINEL ADMINISTRATIVO
    # ==========================================
    def tela_login_admin(self):
        self.limpar_tela()
        lbl_cadeado = tk.Label(self.container, text="🔒\nAutenticação do Painel Gestor", font=("Segoe UI", 26, "bold"),
                               fg=self.COR_TEXTO, bg=self.COR_BG)
        lbl_cadeado.pack(pady=40)

        self.ent_senha = tk.Entry(
            self.container, font=("Segoe UI", 20), fg=self.COR_TEXTO, bg=self.COR_CARD,
            bd=0, highlightthickness=1, highlightbackground=self.COR_BORDA, show="*", justify="center", width=22
        )
        self.ent_senha.pack(pady=20)
        self.ent_senha.focus_set()

        self.criar_botao_moderno(self.container, "Acessar Painel", self.validar_senha, cor_bg=self.COR_CYAN,
                                 cor_fg=self.COR_BG, width=16, height=2).pack(pady=10)
        self.ent_senha.bind("<Return>", lambda e: self.validar_senha())
        self.criar_botao_moderno(self.container, "Voltar", self.tela_setores, cor_fg=self.COR_MUTED).pack(pady=10)

    def validar_senha(self):
        if self.ent_senha.get().strip() == SENHA_ADMIN:
            self.tela_dashboard_admin()
        else:
            messagebox.showerror("Erro", "Credencial inválida!")

    def tela_dashboard_admin(self):
        self.limpar_tela()

        # Configurações de Estilo Moderno para os Widgets do Painel
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=self.COR_CARD, background=self.COR_BORDA,
                        foreground=self.COR_TEXTO, arrowcolor=self.COR_CYAN)
        style.configure("Treeview", background=self.COR_CARD, foreground=self.COR_TEXTO, fieldbackground=self.COR_CARD,
                        rowheight=35, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading", background=self.COR_BORDA, foreground=self.COR_TEXTO,
                        font=("Segoe UI", 11, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", "#083344")], foreground=[("selected", self.COR_CYAN)])

        topo_frame = tk.Frame(self.container, bg=self.COR_CARD, height=60)
        topo_frame.pack(fill="x", pady=(0, 20))

        tk.Label(topo_frame, text=" 📊 PAINEL GESTOR - PERFORMANCE DA OUVIDORIA DIGITAL", font=("Segoe UI", 14, "bold"),
                 fg=self.COR_CYAN, bg=self.COR_CARD).pack(side="left", padx=20, pady=15)
        self.criar_botao_moderno(topo_frame, "Sair 🚫", self.tela_setores,font=("Segoe UI", 12, "bold") ,cor_bg="#ef4444").pack(side="right",
                                                                                                           padx=15,
                                                                                                           pady=10)

        corpo_frame = tk.Frame(self.container, bg=self.COR_BG)
        corpo_frame.pack(fill="both", expand=True)

        # Coluna da Esquerda (Filtros, KPIs e Gráfico)
        painel_esquerdo = tk.Frame(corpo_frame, bg=self.COR_BG, width=380)
        painel_esquerdo.pack(side="left", fill="both", padx=(0, 20))

        filtros_container = tk.Frame(painel_esquerdo, bg=self.COR_CARD, padx=15, pady=15)
        filtros_container.pack(fill="x", pady=(0, 15))
        tk.Label(filtros_container, text="FILTROS OPERACIONAIS", font=("Segoe UI", 10, "bold"), fg=self.COR_CYAN,
                 bg=self.COR_CARD).pack(anchor="w", pady=(0, 10))

        self.cb_periodo = ttk.Combobox(filtros_container,
                                       values=["Hoje", "Últimos 7 dias (Semanal)", "Últimos 30 dias (Mensal)",
                                               "Todo o Histórico"], font=("Segoe UI", 10), state="readonly")
        self.cb_periodo.set("Todo o Histórico")
        self.cb_periodo.pack(fill="x", pady=5)

        self.criar_botao_moderno(filtros_container, "Filtrar Dados 🔍", self.carregar_e_filtrar_dados,
                                 cor_bg="#1e293b", cor_fg="#ef4444").pack(fill="x", pady=4)
        self.criar_botao_moderno(filtros_container, "Gerar Relatório PDF 📄", self.exportar_relatorio_pdf,
                                 cor_bg="#1e293b", cor_fg="#ef4444").pack(fill="x", pady=2)
        self.criar_botao_moderno(filtros_container, "Exportar Base CSV 🔋", self.exportar_para_csv, cor_bg="#1e293b",
                                 cor_fg="#ef4444").pack(fill="x", pady=2)
        self.criar_botao_moderno(filtros_container, "Limpar Banco ⚡", self.resetar_banco_dados, cor_bg="#1e293b",
                                 cor_fg="#ef4444").pack(fill="x", pady=(8, 0))

        cards_container = tk.Frame(painel_esquerdo, bg=self.COR_CARD, padx=10, pady=10)
        cards_container.pack(fill="x", pady=(0, 10))
        tk.Label(cards_container, text="KPIs CONSOLIDADOS", font=("Segoe UI", 10, "bold"), fg=self.COR_CYAN,
                 bg=self.COR_CARD).pack(anchor="w", pady=(0, 10))

        self.lbl_votos_val = self.criar_linha_metrica(cards_container, "Volume Total de Votos:", "0", self.COR_TEXTO)
        self.lbl_media_val = self.criar_linha_metrica(cards_container, "Média Geral:", "0.0 / 5.0", self.COR_CYAN)
        self.lbl_cartas_val = self.criar_linha_metrica(cards_container, "Cartas Coletadas:", "0", "#a78bfa")

        grafico_container = tk.Frame(painel_esquerdo, bg=self.COR_CARD, padx=10, pady=10)
        grafico_container.pack(fill="both", expand=True)
        tk.Label(grafico_container, text="DISTRIBUIÇÃO VOLUMÉTRICA", font=("Segoe UI", 10, "bold"), fg=self.COR_CYAN,
                 bg=self.COR_CARD).pack(anchor="w", pady=(0, 5))

        # ADICIONADO: height=180 para forçar o layout a exibir as 5 categorias
        self.canvas_grafico = tk.Canvas(grafico_container, bg=self.COR_CARD, bd=0, highlightthickness=0, height=190)
        self.canvas_grafico.pack(fill="both", expand=True)

        # Coluna da Direita (Tabela de Registros com Busca)
        painel_direito = tk.Frame(corpo_frame, bg=self.COR_CARD, padx=10, pady=10)
        painel_direito.pack(side="right", fill="both", expand=True)

        acoes_frame = tk.Frame(painel_direito, bg=self.COR_CARD)
        acoes_frame.pack(fill="x", pady=(0, 10))

        tk.Label(acoes_frame, text="Pesquisar registro:", font=("Segoe UI", 10), fg=self.COR_MUTED,
                 bg=self.COR_CARD).pack(side="left", padx=(0, 10))
        self.ent_busca = tk.Entry(acoes_frame, font=("Segoe UI", 11), fg=self.COR_TEXTO, bg=self.COR_BG, bd=0,
                                  highlightthickness=1, highlightbackground=self.COR_BORDA, width=30)
        self.ent_busca.pack(side="left", ipady=4)
        self.ent_busca.bind("<KeyRelease>", lambda e: self.aplicar_busca_em_tempo_real())

        self.criar_botao_moderno(acoes_frame, "🗑️ Excluir Selecionado", self.deletar_registro_selecionado,
                                 cor_bg="#ef4444").pack(side="right")

        tabela_container = tk.Frame(painel_direito, bg=self.COR_CARD)
        tabela_container.pack(fill="both", expand=True)

        colunas = ("id", "data", "setor", "nota", "motivos", "carta")
        self.tabela_ouvidoria = ttk.Treeview(tabela_container, columns=colunas, show="headings", style="Treeview")

        self.tabela_ouvidoria.heading("id", text="ID")
        self.tabela_ouvidoria.heading("data", text="Data/Hora")
        self.tabela_ouvidoria.heading("setor", text="Setor")
        self.tabela_ouvidoria.heading("nota", text="Nota")
        self.tabela_ouvidoria.heading("motivos", text="Motivos/Tags")
        self.tabela_ouvidoria.heading("carta", text="Carta / Relato na Íntegra")

        self.tabela_ouvidoria.column("id", width=50, anchor="center")
        self.tabela_ouvidoria.column("data", width=140, anchor="center")
        self.tabela_ouvidoria.column("setor", width=150, anchor="w")
        self.tabela_ouvidoria.column("nota", width=110, anchor="center")
        self.tabela_ouvidoria.column("motivos", width=200, anchor="w")
        self.tabela_ouvidoria.column("carta", width=320, anchor="w")

        scroll_y = ttk.Scrollbar(tabela_container, orient="vertical", command=self.tabela_ouvidoria.yview)
        self.tabela_ouvidoria.configure(yscrollcommand=scroll_y.set)
        self.tabela_ouvidoria.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        self.carregar_e_filtrar_dados()

    def criar_linha_metrica(self, pai, rotulo, valor_ini, cor_val):
        f = tk.Frame(pai, bg=self.COR_CARD)
        f.pack(fill="x", pady=5)
        tk.Label(f, text=rotulo, font=("Segoe UI", 11), fg=self.COR_MUTED, bg=self.COR_CARD).pack(side="left")
        lbl_v = tk.Label(f, text=valor_ini, font=("Segoe UI", 12, "bold"), fg=cor_val, bg=self.COR_CARD)
        lbl_v.pack(side="right")
        return lbl_v

    def carregar_e_filtrar_dados(self):
        periodo = self.cb_periodo.get()
        data_limite = None
        agora = datetime.now()

        if periodo == "Hoje":
            data_limite = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        elif periodo == "Últimos 7 dias (Semanal)":
            data_limite = agora - timedelta(days=7)
        elif periodo == "Últimos 30 dias (Mensal)":
            data_limite = agora - timedelta(days=30)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, setor, nota, rotulo_nota, motivos, carta, timestamp FROM avaliacoes ORDER BY id DESC")
        linhas = cursor.fetchall()
        conn.close()

        self.dados_locais = []
        soma_notas = 0
        contagem_cartas = 0
        distribuicao = {"Péssimo": 0, "Ruim": 0, "Regular": 0, "Bom": 0, "Excelente": 0}

        for row in linhas:
            try:
                row_date = datetime.strptime(row[6], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

            if data_limite and row_date < data_limite: continue

            item = {"id": row[0], "setor": row[1], "nota": row[2], "rotulo_nota": row[3],
                    "motivos": row[4] if row[4] else "", "carta": row[5] if row[5] else "", "timestamp": row[6]}
            self.dados_locais.append(item)
            soma_notas += item["nota"]
            if item["carta"].strip(): contagem_cartas += 1

            r_nota = item["rotulo_nota"]
            if r_nota in distribuicao: distribuicao[r_nota] += 1

        total_votos = len(self.dados_locais)
        media_geral = round(soma_notas / total_votos, 2) if total_votos > 0 else 0.0

        self.lbl_votos_val.configure(text=str(total_votos))
        self.lbl_media_val.configure(text=f"{media_geral} / 5.0")
        self.lbl_cartas_val.configure(text=str(contagem_cartas))

        self.desenhar_grafico_distribuicao(distribuicao, total_votos)
        self.atualizar_linhas_tabela(self.dados_locais)

    def atualizar_linhas_tabela(self, lista_dados):
        for item in self.tabela_ouvidoria.get_children(): self.tabela_ouvidoria.delete(item)
        for r in lista_dados:
            self.tabela_ouvidoria.insert("", "end", values=(
            r["id"], r["timestamp"], r["setor"], f"{r['nota']} ({r['rotulo_nota']})", r["motivos"], r["carta"]))

    def aplicar_busca_em_tempo_real(self):
        termo = self.ent_busca.get().lower().strip()
        if not termo:
            self.atualizar_linhas_tabela(self.dados_locais)
            return
        filtrados = [r for r in self.dados_locais if
                     termo in r["setor"].lower() or termo in r["motivos"].lower() or termo in r[
                         "carta"].lower() or termo in str(r["id"])]
        self.atualizar_linhas_tabela(filtrados)

    def desenhar_grafico_distribuicao(self, distribuicao, total_votos):
        self.canvas_grafico.delete("all")
        largura = self.canvas_grafico.winfo_width()
        if largura <= 10: largura = 340

        # Ajustes para garantir que as 5 barras caibam perfeitamente na janela
        alt_barra = 18  # Reduzido levemente de 20 para 18
        espacamento = 8  # Reduzido levemente de 10 para 8
        y_ini = 12  # Ajustado o topo para ganhar área útil
        largura_max = max(largura - 110, 140)

        cores = {
            "Excelente": self.COR_CYAN,
            "Bom": "#10b981",
            "Regular": "#eab308",
            "Ruim": "#f97316",
            "Péssimo": "#ef4444"
        }
        ordem = ["Excelente", "Bom", "Regular", "Ruim", "Péssimo"]

        for idx, rotulo in enumerate(ordem):
            qtd = distribuicao.get(rotulo, 0)
            y1 = y_ini + idx * (alt_barra + espacamento)
            y2 = y1 + alt_barra

            pct = (qtd / total_votos) if total_votos > 0 else 0
            tam_barra = int(pct * largura_max)

            # Renderização do texto do rótulo à esquerda
            self.canvas_grafico.create_text(5, (y1 + y2) // 2, text=rotulo, fill=self.COR_MUTED,
                                            font=("Segoe UI", 9, "bold"), anchor="w")

            # Fundo escuro da barra de progresso (track)
            self.canvas_grafico.create_rectangle(75, y1, 75 + largura_max, y2, fill=self.COR_BG, outline="")

            # Barra preenchida com a cor correspondente
            if tam_barra > 0:
                self.canvas_grafico.create_rectangle(75, y1, 75 + tam_barra, y2, fill=cores[rotulo], outline="")

            # Contador numérico e porcentagem à direita
            self.canvas_grafico.create_text(80 + largura_max, (y1 + y2) // 2, text=f"{qtd} ({int(pct * 100)}%)",
                                            fill=self.COR_TEXTO, font=("Segoe UI", 9, "bold"), anchor="w")

    def deletar_registro_selecionado(self):
        sel = self.tabela_ouvidoria.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione uma linha da lista para remoção.")
            return

        valores = self.tabela_ouvidoria.item(sel, "values")
        id_reg = valores[0]

        if messagebox.askyesno("Confirmar", f"Deseja deletar permanentemente o registro ID {id_reg}?"):
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM avaliacoes WHERE id = ?", (id_reg,))
                conn.commit()
                conn.close()
                self.carregar_e_filtrar_dados()
            except Exception as e:
                messagebox.showerror("Erro", f"Falha na exclusão: {e}")

    def resetar_banco_dados(self):
        if messagebox.askyesno("⚠️ ALERTA CRÍTICO", "Deseja apagar TODOS os registros de ouvidoria definitivamente?"):
            if messagebox.askyesno("Confirmação Final", "Ação irreversível. Prosseguir?"):
                try:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DROP TABLE IF EXISTS avaliacoes")
                    conn.commit()
                    conn.close()
                    inicializar_banco()
                    self.carregar_e_filtrar_dados()
                except Exception as e:
                    messagebox.showerror("Erro", f"Falha: {e}")

    def exportar_para_csv(self):
        if not self.dados_locais:
            messagebox.showwarning("Aviso", "Sem dados para exportar.")
            return

        destino = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("Planilha CSV", "*.csv")],
                                               title="Exportar CSV")
        if not destino: return

        try:
            with open(destino, mode='w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(["ID", "Data/Hora", "Setor", "Nota", "Rótulo", "Motivos", "Carta"])
                for r in self.dados_locais:
                    w.writerow(
                        [r["id"], r["timestamp"], r["setor"], r["nota"], r["rotulo_nota"], r["motivos"], r["carta"]])
            messagebox.showinfo("Sucesso", "CSV gerado com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na exportação: {e}")

    def exportar_relatorio_pdf(self):
        if not self.dados_locais:
            messagebox.showwarning("Aviso", "Sem dados para compilação.")
            return

        destino = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("Arquivos PDF", "*.pdf")],
                                               title="Salvar Relatório PDF")
        if not destino: return

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            doc = SimpleDocTemplate(destino, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40,
                                    bottomMargin=40)
            story = []
            styles = getSampleStyleSheet()

            style_titulo = ParagraphStyle('T1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=22,
                                          textColor=colors.HexColor("#0f172a"), spaceAfter=6)
            style_sub = ParagraphStyle('S1', parent=styles['Normal'], fontName='Helvetica', fontSize=10,
                                       textColor=colors.HexColor("#475569"), spaceAfter=15)
            style_h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=14,
                                      textColor=colors.HexColor("#0284c7"), spaceBefore=12, spaceAfter=8)
            style_texto = ParagraphStyle('TX', parent=styles['Normal'], fontName='Helvetica', fontSize=10,
                                         textColor=colors.HexColor("#1e293b"), leading=14)
            style_t_cab = ParagraphStyle('TC', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10,
                                         textColor=colors.HexColor("#ffffff"))
            style_alerta = ParagraphStyle('TA', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10,
                                          textColor=colors.HexColor("#991b1b"), leading=14)

            story.append(Paragraph("RELATÓRIO DE GESTÃO - OUVIDORIA DIGITAL", style_titulo))
            story.append(Paragraph(
                f"Filtro Aplicado: {self.cb_periodo.get()} | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                style_sub))
            story.append(Spacer(1, 10))

            total_votos = len(self.dados_locais)
            soma_notas = sum(r["nota"] for r in self.dados_locais)
            media_geral = round(soma_notas / total_votos, 2) if total_votos > 0 else 0.0

            distribuicao = {"Excelente": 0, "Bom": 0, "Regular": 0, "Ruim": 0, "Péssimo": 0}
            por_setor = {}
            alertas_motivos = {}

            for r in self.dados_locais:
                rot = r["rotulo_nota"]
                if rot in distribuicao: distribuicao[rot] += 1
                s = r["setor"]
                por_setor[s] = por_setor.get(s, []) + [r["nota"]]

                if r["nota"] <= 3 and r["motivos"]:
                    for m in r["motivos"].split(", "):
                        if m: alertas_motivos[m] = alertas_motivos.get(m, 0) + 1

            story.append(Paragraph("Métricas Consolidadas", style_h2))
            dados_metrica = [
                [Paragraph("<b>Indicador</b>", style_texto), Paragraph("<b>Resultado</b>", style_texto)],
                [Paragraph("Volume Total de Avaliações", style_texto), Paragraph(str(total_votos), style_texto)],
                [Paragraph("Média de Satisfação Geral", style_texto), Paragraph(f"{media_geral} / 5.0", style_texto)],
            ]
            t_metrica = Table(dados_metrica, colWidths=[250, 250])
            t_metrica.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#f1f5f9")),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ]))
            story.append(t_metrica)
            story.append(Spacer(1, 15))

            story.append(Paragraph("Análise de Gargalos e Pontos Críticos", style_h2))
            story.append(Paragraph("Gargalos operacionais mapeados com base na apuração ativa do totem:", style_texto))
            story.append(Spacer(1, 8))

            pontos = []
            if media_geral < 3.8 and total_votos > 0:
                pontos.append(
                    "• <b>ALERTA DE DESEMPENHO:</b> Média de satisfação geral abaixo da linha aceitável (3.8).")
            for s, notas in por_setor.items():
                m_s = sum(notas) / len(notas)
                if m_s <= 3.0:
                    pontos.append(
                        f"• <b>CRÍTICO - SETOR {s.upper()}:</b> Rendimento alarmante com média {round(m_s, 2)} / 5.0.")
            reclamacoes = sorted(alertas_motivos.items(), key=lambda x: x[1], reverse=True)
            for motivo, qtd in reclamacoes[:3]:
                pontos.append(
                    f"• <b>RECORRÊNCIA:</b> A tag '<u>{motivo}</u>' foi selecionada {qtd} vezes como causa de insatisfação.")

            if not pontos: pontos.append(
                "• <b>Conformidade Operacional:</b> Nenhuma não-conformidade registrada no ciclo atual.")

            for p in pontos:
                est = style_alerta if "CRÍTICO" in p or "ALERTA" in p else style_texto
                story.append(Paragraph(p, est))
                story.append(Spacer(1, 4))

            story.append(Spacer(1, 15))
            story.append(Paragraph("Desempenho Detalhado por Setor", style_h2))
            dados_setores = [[Paragraph("<b>Setor Hospitalar</b>", style_texto), Paragraph("<b>Votos</b>", style_texto),
                              Paragraph("<b>Média</b>", style_texto)]]
            for s, nts in por_setor.items():
                dados_setores.append([Paragraph(s, style_texto), Paragraph(str(len(nts)), style_texto),
                                      Paragraph(f"{round(sum(nts) / len(nts), 2)} / 5.0", style_texto)])

            t_setores = Table(dados_setores, colWidths=[240, 130, 130])
            t_setores.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1"))
            ]))
            story.append(t_setores)

            story.append(Spacer(1, 15))
            story.append(Paragraph("Anexo: Transcrições das Cartas Coletadas", style_h2))
            dados_cartas = [[Paragraph("<b>Data</b>", style_t_cab), Paragraph("<b>Setor</b>", style_t_cab),
                             Paragraph("<b>Nota</b>", style_t_cab),
                             Paragraph("<b>Relato Técnico na Íntegra</b>", style_t_cab)]]

            tem_carta = False
            for r in self.dados_locais:
                if r["carta"].strip():
                    tem_carta = True
                    dados_cartas.append([Paragraph(r["timestamp"], style_texto), Paragraph(r["setor"], style_texto),
                                         Paragraph(f"{r['nota']}", style_texto), Paragraph(r["carta"], style_texto)])

            if tem_carta:
                t_cartas = Table(dados_cartas, colWidths=[100, 110, 50, 260])
                est_c = [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")), ('PADDING', (0, 0), (-1, -1), 6),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                         ('VALIGN', (0, 0), (-1, -1), 'TOP')]
                for i in range(1, len(dados_cartas)):
                    if i % 2 == 0: est_c.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8fafc")))
                t_cartas.setStyle(TableStyle(est_c))
                story.append(t_cartas)
            else:
                story.append(
                    Paragraph("<i>Nenhum relato descritivo registrado no intervalo selecionado.</i>", style_texto))

            doc.build(story)
            messagebox.showinfo("Sucesso", f"Relatório PDF gerado:\n{destino}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na compilação do arquivo PDF: {e}")


# --- INICIALIZAÇÃO DO PROGRAMA ---
if __name__ == "__main__":
    app = OuvidoriaTotemApp()
    app.mainloop()
