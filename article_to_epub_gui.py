"""
article_to_epub_gui.py
----------------------
Interface gráfica para article_to_epub.py.
Coloque este arquivo na mesma pasta que article_to_epub.py e execute:
    python article_to_epub_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
from pathlib import Path

try:
    from article_to_epub import (
        fetch_url, fetch_pdf, load_local_html,
        extract_content, clean_html_for_epub,
        build_epub, check_dependencies,
    )
except ImportError:
    import sys
    print("Erro: article_to_epub.py não encontrado na mesma pasta.")
    sys.exit(1)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Article → EPUB")
        self.minsize(580, 520)
        self._build()

    # ── Construção da UI ─────────────────────────────────────────────────────

    def _build(self):
        P = dict(padx=12, pady=5)

        # — Tipo de origem —
        tipo_frame = ttk.LabelFrame(self, text="Origem")
        tipo_frame.pack(fill="x", **P)

        self.tipo = tk.StringVar(value="url")
        ttk.Radiobutton(tipo_frame, text="URL",
                        variable=self.tipo, value="url",
                        command=self._atualiza_origem
                        ).pack(side="left", padx=10, pady=4)
        ttk.Radiobutton(tipo_frame, text="Arquivo (HTML ou PDF)",
                        variable=self.tipo, value="file",
                        command=self._atualiza_origem
                        ).pack(side="left", padx=10, pady=4)

        # — Container da origem (troca entre URL e arquivo) —
        self.origem_container = ttk.Frame(self)
        self.origem_container.pack(fill="x", **P)

        # Linha URL (visível por padrão)
        self.url_row = ttk.Frame(self.origem_container)
        ttk.Label(self.url_row, text="URL:", width=10).pack(side="left")
        self.url_var = tk.StringVar()
        ttk.Entry(self.url_row, textvariable=self.url_var).pack(
            side="left", fill="x", expand=True, padx=4)
        self.url_row.pack(fill="x")

        # Linha arquivo (escondida por padrão)
        self.file_row = ttk.Frame(self.origem_container)
        ttk.Label(self.file_row, text="Arquivo:", width=10).pack(side="left")
        self.file_var = tk.StringVar()
        ttk.Entry(self.file_row, textvariable=self.file_var).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(self.file_row, text="Procurar…",
                   command=self._browse_input).pack(side="left")

        # — Saída —
        out_row = ttk.Frame(self)
        out_row.pack(fill="x", **P)
        ttk.Label(out_row, text="Salvar como:", width=12).pack(side="left")
        self.out_var = tk.StringVar(value="output.epub")
        ttk.Entry(out_row, textvariable=self.out_var).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(out_row, text="Escolher…",
                   command=self._browse_output).pack(side="left")

        # — Opcionais —
        opt = ttk.LabelFrame(
            self, text="Opcionais  (deixe em branco para detecção automática)")
        opt.pack(fill="x", **P)

        for label, attr in [("Título:", "title_var"), ("Autor:", "author_var")]:
            row = ttk.Frame(opt)
            row.pack(fill="x", padx=8, pady=3)
            ttk.Label(row, text=label, width=8).pack(side="left")
            var = tk.StringVar()
            setattr(self, attr, var)
            ttk.Entry(row, textvariable=var).pack(
                side="left", fill="x", expand=True)

        lang_row = ttk.Frame(opt)
        lang_row.pack(fill="x", padx=8, pady=3)
        ttk.Label(lang_row, text="Idioma:", width=8).pack(side="left")
        self.lang_var = tk.StringVar(value="en")
        ttk.Combobox(lang_row, textvariable=self.lang_var, width=6,
                     values=["en", "pt", "es", "de", "fr"],
                     state="readonly").pack(side="left")

        # — Botão converter —
        self.btn = ttk.Button(self, text="Converter  →  EPUB",
                              command=self._iniciar)
        self.btn.pack(pady=10)

        # — Área de log —
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **P)
        self.log = scrolledtext.ScrolledText(
            log_frame, height=7, state="disabled",
            font=("Consolas", 9),
            background="#1e1e1e", foreground="#d4d4d4",
            insertbackground="white")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Helpers de UI ────────────────────────────────────────────────────────

    def _atualiza_origem(self):
        """Alterna entre o campo URL e o seletor de arquivo."""
        if self.tipo.get() == "url":
            self.file_row.pack_forget()
            self.url_row.pack(fill="x")
        else:
            self.url_row.pack_forget()
            self.file_row.pack(fill="x")

    def _browse_input(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar arquivo",
            filetypes=[("HTML", "*.html *.htm"),
                       ("PDF",  "*.pdf"),
                       ("Todos", "*.*")])
        if caminho:
            self.file_var.set(caminho)
            # Sugere nome de saída baseado no arquivo de entrada
            if self.out_var.get() in ("", "output.epub"):
                self.out_var.set(f"{Path(caminho).stem}.epub")

    def _browse_output(self):
        caminho = filedialog.asksaveasfilename(
            defaultextension=".epub",
            filetypes=[("EPUB", "*.epub")])
        if caminho:
            self.out_var.set(caminho)

    def _log(self, msg: str):
        """Adiciona uma linha ao log. Seguro para chamar de outra thread."""
        def _append():
            self.log.configure(state="normal")
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.configure(state="disabled")
        self.after(0, _append)   # agenda execução na thread principal

    # ── Conversão ────────────────────────────────────────────────────────────

    def _iniciar(self):
        """Dispara a conversão em uma thread separada."""
        self.btn.configure(state="disabled")
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")
        threading.Thread(target=self._converter, daemon=True).start()

    def _converter(self):
        """Lógica de conversão — roda em thread secundária."""
        try:
            tipo  = self.tipo.get()
            saida = self.out_var.get().strip() or "output.epub"

            # — Carrega a origem —
            if tipo == "url":
                origem = self.url_var.get().strip()
                if not origem:
                    self.after(0, lambda: messagebox.showerror(
                        "Erro", "Informe uma URL."))
                    return
                self._log(f"Buscando URL…\n  {origem}")
                html, _ = fetch_url(origem)
            else:
                origem = self.file_var.get().strip()
                if not origem:
                    self.after(0, lambda: messagebox.showerror(
                        "Erro", "Selecione um arquivo."))
                    return
                self._log(f"Carregando arquivo…\n  {origem}")
                if origem.lower().endswith(".pdf"):
                    html = fetch_pdf(origem)
                else:
                    html = load_local_html(origem)

            # — Extrai e limpa o conteúdo —
            self._log("Extraindo conteúdo…")
            titulo, autor_detectado, conteudo = extract_content(html, origem)
            conteudo = clean_html_for_epub(conteudo)

            # Aplica sobrescritas do usuário, se fornecidas
            titulo_final = self.title_var.get().strip() or titulo
            autor_final  = self.author_var.get().strip() or autor_detectado
            lang         = self.lang_var.get()

            self._log(f"Título : {titulo_final}")
            self._log(f"Autor  : {autor_final or '(não detectado)'}")
            self._log("Gerando EPUB…")

            build_epub(titulo_final, autor_final, conteudo, saida, lang)

            self._log(f"\n✓ Concluído  →  {saida}")
            self.after(0, lambda: messagebox.showinfo(
                "Concluído", f"EPUB gerado:\n\n{saida}"))

        except Exception as e:
            self._log(f"\n✗ Erro: {e}")
            self.after(0, lambda: messagebox.showerror("Erro", str(e)))
        finally:
            # Reativa o botão independentemente do resultado
            self.after(0, lambda: self.btn.configure(state="normal"))


if __name__ == "__main__":
    check_dependencies()
    app = App()
    app.mainloop()