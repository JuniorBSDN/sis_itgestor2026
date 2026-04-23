import customtkinter as ctk
from datetime import datetime


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema de Senhas")
        self.after(0, lambda: self.state('zoomed'))

        self.contadores = {"Normal": 0, "Prioridade": 0, "Preferencial": 0}
        self.descricao_servico = "Atendimento Geral"

        # Grid Principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.label_titulo = ctk.CTkLabel(self, text="TOQUE PARA RETIRAR SUA SENHA",
                                         font=ctk.CTkFont(size=32, weight="bold"))
        self.label_titulo.grid(row=0, column=0, padx=20, pady=(60, 20))  # pady maior no topo

        # Frame Centralizador
        self.frame_container = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_container.grid(row=1, column=0, sticky="n")  # "n" alinha o grupo ao topo do espaço central

        self.frame_container.grid_columnconfigure(0, weight=1)
        # Removido o rowconfigure(weight=1) para os botões não se espalharem

        # Configurações dos botões
        largura_fixa = 400
        altura_fixa = 100
        fonte_botao = ctk.CTkFont(size=20, weight="bold")
        espacamento_vertical = 10  # Altere este valor para aproximar mais ou menos

        self.btn_normal = ctk.CTkButton(self.frame_container, text="ATENDIMENTO NORMAL",
                                        width=largura_fixa, height=altura_fixa, font=fonte_botao,
                                        command=lambda: self.gerar_senha("Normal"))
        self.btn_normal.grid(row=0, column=0, pady=espacamento_vertical)

        self.btn_prioridade = ctk.CTkButton(self.frame_container, text="PRIORIDADE",
                                            fg_color="#e67e22", hover_color="#d35400",
                                            width=largura_fixa, height=altura_fixa, font=fonte_botao,
                                            command=lambda: self.gerar_senha("Prioridade"))
        self.btn_prioridade.grid(row=1, column=0, pady=espacamento_vertical)

        self.btn_preferencial = ctk.CTkButton(self.frame_container, text="PREFERENCIAL",
                                              fg_color="#2ecc71", hover_color="#27ae60",
                                              width=largura_fixa, height=altura_fixa, font=fonte_botao,
                                              command=lambda: self.gerar_senha("Preferencial"))
        self.btn_preferencial.grid(row=2, column=0, pady=espacamento_vertical)

        # Botão de Configuração
        self.btn_config = ctk.CTkButton(self, text="⚙", width=50,
                                        command=self.abrir_modal_config)
        self.btn_config.grid(row=2, column=0, padx=20, pady=20, sticky="se")

    def abrir_modal_config(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Configuração")
        modal.geometry("400x200")
        modal.attributes("-topmost", True)

        ctk.CTkLabel(modal, text="Descrição do Serviço:").pack(pady=10)
        entry = ctk.CTkEntry(modal, width=250)
        entry.insert(0, self.descricao_servico)
        entry.pack(pady=10)

        def salvar():
            self.descricao_servico = entry.get()
            modal.destroy()

        ctk.CTkButton(modal, text="Confirmar", command=salvar).pack(pady=10)

    def gerar_senha(self, tipo):
        self.contadores[tipo] += 1
        senha = f"{tipo[0].upper()}-{self.contadores[tipo]:03d}"
        print(f"Imprimindo: {senha} | {self.descricao_servico}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
