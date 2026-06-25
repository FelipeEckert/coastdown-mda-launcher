import json
import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from tkinter import scrolledtext


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
CONFIG_EXAMPLE_FILE = BASE_DIR / "config.example.json"


class CoastdownLauncher(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Coastdown MDA Launcher")
        self.geometry("860x620")
        self.minsize(760, 520)

        self.log_queue = queue.Queue()
        self.buttons = []

        self.config_data, used_example = self.load_config()
        self.configure_ui()
        self.after(100, self.flush_log_queue)

        if used_example:
            self.log(
                "Aviso: config.json nao foi encontrado. "
                "Usando config.example.json temporariamente."
            )
            messagebox.showwarning(
                "Configuracao local nao encontrada",
                "config.json nao foi encontrado.\n\n"
                "O arquivo config.example.json esta sendo usado temporariamente. "
                "Crie um config.json local quando precisar personalizar os caminhos.",
            )

    def load_config(self):
        config_path = CONFIG_FILE
        used_example = False

        if not config_path.exists():
            config_path = CONFIG_EXAMPLE_FILE
            used_example = True

        if not config_path.exists():
            messagebox.showerror(
                "Configuracao nao encontrada",
                "Nenhum arquivo config.json ou config.example.json foi encontrado.",
            )
            return {"apps": {}}, used_example

        try:
            with config_path.open("r", encoding="utf-8") as config_file:
                return json.load(config_file), used_example
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showerror(
                "Erro ao ler configuracao",
                f"Nao foi possivel ler {config_path.name}:\n{error}",
            )
            return {"apps": {}}, used_example

    def configure_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = tk.Frame(self, padx=18, pady=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = tk.Label(
            header,
            text="Coastdown MDA Launcher",
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew")

        subtitle = tk.Label(
            header,
            text="Atualize e abra os apps Streamlit Standard e Split.",
            font=("Segoe UI", 10),
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        apps_frame = tk.Frame(self, padx=18)
        apps_frame.grid(row=1, column=0, sticky="ew")
        apps_frame.columnconfigure(0, weight=1)

        apps = self.config_data.get("apps", {})
        if not apps:
            self.log("Nenhuma aplicacao encontrada na configuracao.")

        for row_index, app_key in enumerate(("standard", "split")):
            app_config = apps.get(app_key)
            if app_config:
                self.create_app_block(apps_frame, row_index, app_key, app_config)

        log_frame = tk.LabelFrame(self, text="Log", padx=10, pady=10)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=18)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            wrap=tk.WORD,
            state="disabled",
            font=("Consolas", 9),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def create_app_block(self, parent, row_index, app_key, app_config):
        block = tk.LabelFrame(parent, text=app_config.get("name", app_key), padx=12, pady=10)
        block.grid(row=row_index, column=0, sticky="ew", pady=(0, 12))
        block.columnconfigure(1, weight=1)

        name_label = tk.Label(
            block,
            text=app_config.get("name", app_key),
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, columnspan=4, sticky="ew")

        configured_path = app_config.get("local_path", "")
        expanded_path = os.path.expandvars(configured_path)
        path_label = tk.Label(
            block,
            text=f"Caminho: {expanded_path}",
            anchor="w",
            justify="left",
        )
        path_label.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 10))

        check_button = tk.Button(
            block,
            text="Verificar atualizacao",
            command=lambda: self.run_in_background(
                f"Verificar atualizacao - {app_config.get('name', app_key)}",
                self.check_update,
                app_config,
            ),
            width=22,
        )
        check_button.grid(row=2, column=0, sticky="w", padx=(0, 8))

        update_button = tk.Button(
            block,
            text="Atualizar",
            command=lambda: self.run_in_background(
                f"Atualizar - {app_config.get('name', app_key)}",
                self.update_app,
                app_config,
            ),
            width=18,
        )
        update_button.grid(row=2, column=1, sticky="w", padx=(0, 8))

        open_button = tk.Button(
            block,
            text="Abrir",
            command=lambda: self.run_in_background(
                f"Abrir - {app_config.get('name', app_key)}",
                self.open_app,
                app_config,
            ),
            width=18,
        )
        open_button.grid(row=2, column=2, sticky="w")

        self.buttons.extend([check_button, update_button, open_button])

    def run_in_background(self, title, target, app_config):
        thread = threading.Thread(
            target=self.background_wrapper,
            args=(title, target, app_config),
            daemon=True,
        )
        thread.start()

    def background_wrapper(self, title, target, app_config):
        self.set_buttons_state("disabled")
        self.enqueue_log("")
        self.enqueue_log(f"== {title} ==")

        try:
            target(app_config)
        except Exception as error:
            self.enqueue_log(f"Erro inesperado: {error}")
        finally:
            self.set_buttons_state("normal")

    def set_buttons_state(self, state):
        self.log_queue.put(("buttons", state))

    def flush_log_queue(self):
        while True:
            try:
                item = self.log_queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(item, tuple) and item[0] == "buttons":
                for button in self.buttons:
                    button.configure(state=item[1])
            else:
                self.write_log(str(item))

        self.after(100, self.flush_log_queue)

    def log(self, message):
        if hasattr(self, "log_text"):
            self.write_log(message)
        else:
            self.enqueue_log(message)

    def enqueue_log(self, message):
        self.log_queue.put(message)

    def write_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def get_app_path(self, app_config):
        return Path(os.path.expandvars(app_config.get("local_path", "")))

    def check_update(self, app_config):
        app_path = self.get_app_path(app_config)
        branch = app_config.get("branch", "release")

        self.enqueue_log(f"Aplicacao: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            self.enqueue_log("Repositorio ainda nao existe nesta maquina.")
            self.enqueue_log("Clone automatico sera implementado em etapa futura.")
            return

        fetch_code, _ = self.run_command(["git", "fetch", "origin", branch], app_path)
        if fetch_code != 0:
            self.enqueue_log("Nao foi possivel verificar atualizacao.")
            return

        local_code, local_commit = self.run_command(["git", "rev-parse", "HEAD"], app_path)
        remote_code, remote_commit = self.run_command(
            ["git", "rev-parse", f"origin/{branch}"],
            app_path,
        )

        if local_code != 0 or remote_code != 0:
            self.enqueue_log("Nao foi possivel comparar os commits.")
            return

        local_short = local_commit.strip()[:8]
        remote_short = remote_commit.strip()[:8]
        self.enqueue_log(f"Commit local:  {local_short}")
        self.enqueue_log(f"Commit remoto: {remote_short}")

        if local_short == remote_short:
            self.enqueue_log("Status: aplicacao atualizada")
        else:
            self.enqueue_log("Status: atualizacao disponivel")

    def update_app(self, app_config):
        app_path = self.get_app_path(app_config)
        branch = app_config.get("branch", "release")

        self.enqueue_log(f"Aplicacao: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            self.enqueue_log("Repositorio ainda nao existe nesta maquina.")
            return

        pull_code, _ = self.run_command(
            ["git", "pull", "--ff-only", "origin", branch],
            app_path,
        )
        if pull_code != 0:
            self.enqueue_log("Atualizacao via Git falhou.")
            return

        venv_python = app_path / ".venv" / "Scripts" / "python.exe"
        requirements = app_path / "requirements.txt"

        if not venv_python.exists():
            self.enqueue_log("Aviso: .venv nao encontrado. Instalacao de dependencias ignorada.")
            return

        if not requirements.exists():
            self.enqueue_log(
                "Aviso: requirements.txt nao encontrado. Instalacao de dependencias ignorada."
            )
            return

        self.run_command(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            app_path,
        )

    def open_app(self, app_config):
        app_path = self.get_app_path(app_config)
        entrypoint = app_config.get("entrypoint", "app.py")

        self.enqueue_log(f"Aplicacao: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            self.enqueue_log("Repositorio ainda nao existe nesta maquina.")
            return

        venv_python = app_path / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            self.enqueue_log(
                ".venv nao encontrado. Crie o ambiente virtual dentro do app antes de abrir pelo launcher."
            )
            return

        entrypoint_path = app_path / entrypoint
        if not entrypoint_path.exists():
            self.enqueue_log(f"Arquivo de entrada nao encontrado: {entrypoint_path}")
            return

        command = [str(venv_python), "-m", "streamlit", "run", entrypoint]
        self.enqueue_log(f"$ {subprocess.list2cmdline(command)}")

        try:
            process = subprocess.Popen(
                command,
                cwd=str(app_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            self.enqueue_log(f"Erro ao abrir aplicacao: {error}")
            return

        self.enqueue_log("Aplicacao iniciada em segundo plano.")
        output_thread = threading.Thread(
            target=self.read_process_output,
            args=(process,),
            daemon=True,
        )
        output_thread.start()

    def read_process_output(self, process):
        if process.stdout is None:
            return

        for line in process.stdout:
            self.enqueue_log(line.rstrip())

        return_code = process.wait()
        self.enqueue_log(f"Processo encerrado com codigo {return_code}.")

    def run_command(self, command, cwd):
        self.enqueue_log(f"{cwd}> {subprocess.list2cmdline(command)}")
        output_lines = []

        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            self.enqueue_log(f"Erro ao executar comando: {error}")
            return 1, ""

        if process.stdout is not None:
            for line in process.stdout:
                clean_line = line.rstrip()
                output_lines.append(clean_line)
                self.enqueue_log(clean_line)

        return_code = process.wait()
        if return_code != 0:
            self.enqueue_log(f"Comando terminou com codigo {return_code}.")

        return return_code, "\n".join(output_lines)


if __name__ == "__main__":
    launcher = CoastdownLauncher()
    launcher.mainloop()
