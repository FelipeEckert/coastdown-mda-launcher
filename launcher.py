# -*- coding: utf-8 -*-

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
CONFIG_EXAMPLE_FILE = BASE_DIR / "config.example.json"


class CoastdownLauncher(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Coastdown MDA Launcher")
        self.geometry("1000x720")
        self.minsize(900, 650)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        icon_path = BASE_DIR / "assets" / "coastdown_launcher.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass

        self.log_queue = queue.Queue()
        self.log_history = []
        self.buttons = []
        self.app_status_vars = {}
        self.update_status = {}
        self.git_executable = None
        self.startup_cancelled = False

        self.config_data, _ = self.load_config()
        if self.startup_cancelled:
            self.destroy()
            return

        self.configure_styles()
        self.configure_ui()
        self.after(100, self.flush_log_queue)

    def load_config(self):
        if CONFIG_FILE.exists():
            config_data = self.read_config_file(CONFIG_FILE)
            return config_data, False

        if not CONFIG_EXAMPLE_FILE.exists():
            messagebox.showerror(
                "Configuração não encontrada",
                "Nenhum arquivo config.json ou config.example.json foi encontrado.",
            )
            return {"apps": {}}, False

        self.enqueue_log("Configuração inicial necessária.")
        example_config = self.read_config_file(CONFIG_EXAMPLE_FILE)
        config_data = self.create_initial_config(example_config)
        if config_data is None:
            self.startup_cancelled = True
            return {"apps": {}}, False

        return config_data, False

    def read_config_file(self, config_path):
        try:
            with config_path.open("r", encoding="utf-8") as config_file:
                return json.load(config_file)
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showerror(
                "Erro ao ler configuração",
                f"Não foi possível ler {config_path.name}:\n{error}",
            )
            return {"apps": {}}

    def create_initial_config(self, example_config):
        recommended_root = Path.home() / "CoastdownMDA"
        answer = messagebox.askyesnocancel(
            "Configuração inicial",
            "O Coastdown MDA Launcher ainda não foi configurado nesta máquina.\n\n"
            "Escolha onde os aplicativos Coastdown serão instalados.\n"
            f"Local recomendado:\n{recommended_root}\n\n"
            "Deseja usar o local recomendado?",
            parent=self,
        )

        if answer is None:
            messagebox.showinfo(
                "Configuração cancelada",
                "Configuração inicial cancelada. O launcher será encerrado.",
                parent=self,
            )
            return None

        if answer:
            root_path = recommended_root
        else:
            selected_path = filedialog.askdirectory(
                title="Escolha onde instalar os aplicativos Coastdown",
                initialdir=str(Path.home()),
                parent=self,
            )
            if not selected_path:
                messagebox.showinfo(
                    "Configuração cancelada",
                    "Nenhuma pasta foi escolhida. O launcher será encerrado.",
                    parent=self,
                )
                return None
            root_path = Path(selected_path)

        try:
            root_path.mkdir(parents=True, exist_ok=True)
            (root_path / "standard").mkdir(parents=True, exist_ok=True)
            (root_path / "split").mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Erro ao criar pastas",
                f"Não foi possível criar as pastas iniciais:\n{error}",
                parent=self,
            )
            return None

        config_data = json.loads(json.dumps(example_config))
        apps = config_data.get("apps", {})
        if "standard" in apps:
            apps["standard"]["local_path"] = str(root_path / "standard" / "cd-streamlit")
        if "split" in apps:
            apps["split"]["local_path"] = str(root_path / "split" / "coastdown-mda-split")

        try:
            with CONFIG_FILE.open("x", encoding="utf-8") as config_file:
                json.dump(config_data, config_file, indent=2, ensure_ascii=False)
                config_file.write("\n")
        except FileExistsError:
            return self.read_config_file(CONFIG_FILE)
        except OSError as error:
            messagebox.showerror(
                "Erro ao criar configuração",
                f"Não foi possível criar config.json:\n{error}",
                parent=self,
            )
            return None

        self.enqueue_log(f"Pasta raiz escolhida: {root_path}")
        self.enqueue_log("config.json criado com sucesso.")
        should_create_shortcut = messagebox.askyesno(
            "Criar atalho",
            "Deseja criar um atalho do Coastdown MDA Launcher na Área de Trabalho?",
            parent=self,
        )
        if should_create_shortcut:
            self.create_desktop_shortcut()

        return config_data

    def get_desktop_path(self) -> Path:
        user_profile = Path(os.path.expandvars("%USERPROFILE%"))
        candidates = [
            user_profile / "Desktop",
            user_profile / "Área de Trabalho",
            user_profile / "Area de Trabalho",
            Path.home() / "Desktop",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return Path.home() / "Desktop"

    def create_desktop_shortcut(self) -> bool:
        desktop_path = self.get_desktop_path()
        shortcut_path = desktop_path / "Coastdown MDA Launcher.lnk"
        launcher_path = BASE_DIR / "launcher.bat"
        icon_path = BASE_DIR / "assets" / "coastdown_launcher.ico"

        self.enqueue_log("Criando atalho na Área de Trabalho...")
        self.enqueue_log(f"Área de Trabalho usada: {desktop_path}")

        if not launcher_path.exists():
            self.enqueue_log(f"launcher.bat não encontrado: {launcher_path}")
            return False

        if shortcut_path.exists():
            should_recreate = self.ask_yes_no(
                "Atalho existente",
                "O atalho já existe. Deseja recriá-lo?",
            )
            if not should_recreate:
                self.enqueue_log("Criação de atalho cancelada pelo usuário.")
                return False

        def powershell_quote(value):
            return "'" + str(value).replace("'", "''") + "'"

        powershell_script = (
            "$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut({powershell_quote(shortcut_path)}); "
            f"$Shortcut.TargetPath = {powershell_quote(launcher_path)}; "
            f"$Shortcut.WorkingDirectory = {powershell_quote(BASE_DIR)}; "
        )
        if icon_path.exists():
            powershell_script += f"$Shortcut.IconLocation = {powershell_quote(icon_path)}; "
        powershell_script += "$Shortcut.Save()"

        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", powershell_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
        except OSError as error:
            self.enqueue_log(f"Não foi possível criar o atalho: {error}")
            self.show_warning(
                "Atalho não criado",
                "Não foi possível criar o atalho. Verifique as permissões da Área de Trabalho.",
            )
            return False

        if result.returncode != 0:
            if result.stdout:
                self.enqueue_log(result.stdout.strip())
            if result.stderr:
                self.enqueue_log(result.stderr.strip())
            self.enqueue_log(
                "Não foi possível criar o atalho. Verifique as permissões da Área de Trabalho."
            )
            self.show_warning(
                "Atalho não criado",
                "Não foi possível criar o atalho. Verifique as permissões da Área de Trabalho.",
            )
            return False

        self.enqueue_log(f"Atalho criado: {shortcut_path}")
        return True

    def configure_styles(self):
        self.colors = {
            "background": "#F4F6F8",
            "card": "#FFFFFF",
            "text": "#1F2933",
            "secondary": "#52616B",
            "blue": "#0F4C81",
            "green": "#2E7D32",
            "warning": "#B7791F",
            "border": "#D9E2EC",
        }
        self.configure(bg=self.colors["background"])

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10))
        style.configure("App.TFrame", background=self.colors["background"])
        style.configure("Header.TFrame", background=self.colors["background"])
        style.configure(
            "Card.TFrame",
            background=self.colors["card"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Title.TLabel",
            background=self.colors["background"],
            foreground=self.colors["text"],
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.colors["background"],
            foreground=self.colors["secondary"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "CardTitle.TLabel",
            background=self.colors["card"],
            foreground=self.colors["text"],
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "Meta.TLabel",
            background=self.colors["card"],
            foreground=self.colors["secondary"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Status.TLabel",
            background=self.colors["card"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Path.TLabel",
            background=self.colors["card"],
            foreground=self.colors["secondary"],
            font=("Segoe UI", 8),
        )
        style.configure("TButton", padding=(10, 6), font=("Segoe UI", 9))
        style.configure(
            "Primary.TButton",
            background=self.colors["blue"],
            foreground="#FFFFFF",
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#0B3D66"), ("disabled", "#A7BBCD")],
            foreground=[("disabled", "#EFF4F8")],
        )
        style.configure(
            "Shortcut.TButton",
            background="#E7EEF5",
            foreground=self.colors["blue"],
            borderwidth=0,
        )
        style.map("Shortcut.TButton", background=[("active", "#D7E4EF")])
    def configure_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(24, 20, 24, 14), style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(
            header,
            text="Coastdown MDA Launcher",
            style="Title.TLabel",
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew")

        subtitle = ttk.Label(
            header,
            text="Gerenciador de instalação, atualização e abertura dos apps Coastdown MDA",
            style="Subtitle.TLabel",
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        apps_frame = ttk.Frame(self, padding=(24, 0, 24, 0), style="App.TFrame")
        apps_frame.grid(row=1, column=0, sticky="nsew")
        apps_frame.columnconfigure(0, weight=1)

        apps = self.config_data.get("apps", {})
        if not apps:
            self.log("Nenhuma aplicação encontrada na configuração.")

        for row_index, app_key in enumerate(("standard", "split")):
            app_config = apps.get(app_key)
            if app_config:
                self.create_app_block(apps_frame, row_index, app_key, app_config)

        actions_frame = ttk.Frame(self, padding=(24, 0, 24, 10), style="App.TFrame")
        actions_frame.grid(row=2, column=0, sticky="ew")
        shortcut_button = ttk.Button(
            actions_frame,
            text="Criar atalho na Área de Trabalho",
            command=lambda: self.run_in_background(
                "Criar atalho na Área de Trabalho",
                self.create_desktop_shortcut,
            ),
            style="Shortcut.TButton",
        )
        shortcut_button.grid(row=0, column=0, sticky="w")
        self.buttons.append(shortcut_button)

    def create_app_block(self, parent, row_index, app_key, app_config):
        block = ttk.Frame(parent, padding=(16, 14, 16, 14), style="Card.TFrame")
        block.grid(row=row_index, column=0, sticky="ew", pady=(0, 14))
        block.columnconfigure(0, weight=1)

        name_label = ttk.Label(
            block,
            text=app_config.get("name", app_key),
            style="CardTitle.TLabel",
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="ew")

        status_var = tk.StringVar()
        meta_var = tk.StringVar()
        update_var = tk.StringVar()
        action_var = tk.StringVar()
        path_var = tk.StringVar()
        self.app_status_vars[app_key] = {
            "status": status_var,
            "meta": meta_var,
            "update": update_var,
            "action": action_var,
            "path": path_var,
        }

        status_label = ttk.Label(
            block,
            textvariable=status_var,
            style="Status.TLabel",
            anchor="w",
        )
        status_label.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        meta_label = ttk.Label(
            block,
            textvariable=meta_var,
            style="Meta.TLabel",
            anchor="w",
        )
        meta_label.grid(row=2, column=0, sticky="ew", pady=(3, 0))

        update_label = tk.Label(
            block,
            textvariable=update_var,
            bg=self.colors["card"],
            fg=self.colors["secondary"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        update_label.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.app_status_vars[app_key]["update_widget"] = update_label

        action_label = ttk.Label(
            block,
            textvariable=action_var,
            style="Meta.TLabel",
            anchor="w",
        )
        action_label.grid(row=4, column=0, sticky="ew", pady=(3, 0))

        path_label = ttk.Label(
            block,
            textvariable=path_var,
            style="Path.TLabel",
            anchor="w",
            justify="left",
        )
        path_label.grid(row=5, column=0, sticky="ew", pady=(6, 10))

        buttons_frame = ttk.Frame(block, style="Card.TFrame")
        buttons_frame.grid(row=6, column=0, sticky="w")

        check_button = ttk.Button(
            buttons_frame,
            text="Verificar atualização",
            command=lambda: self.run_in_background(
                f"Verificar atualização - {app_config.get('name', app_key)}",
                self.check_update,
                app_config,
            ),
        )
        check_button.grid(row=0, column=0, sticky="w", padx=(0, 8))

        update_button = ttk.Button(
            buttons_frame,
            text="Atualizar",
            command=lambda: self.run_in_background(
                f"Atualizar - {app_config.get('name', app_key)}",
                self.update_app,
                app_config,
            ),
        )
        update_button.grid(row=0, column=1, sticky="w", padx=(0, 8))

        install_button = ttk.Button(
            buttons_frame,
            text="Instalar/Reparar",
            command=lambda: self.run_in_background(
                f"Instalar/Reparar - {app_config.get('name', app_key)}",
                self.install_or_repair_app,
                app_config,
            ),
            style="Primary.TButton",
        )
        install_button.grid(row=0, column=2, sticky="w", padx=(0, 8))

        open_button = ttk.Button(
            buttons_frame,
            text="Abrir",
            command=lambda: self.run_in_background(
                f"Abrir - {app_config.get('name', app_key)}",
                self.open_app,
                app_config,
            ),
            style="Primary.TButton",
        )
        open_button.grid(row=0, column=3, sticky="w")

        self.buttons.extend([check_button, update_button, install_button, open_button])
        self.refresh_app_status(app_key)
        self.initialize_app_update_status(app_key)

    def run_in_background(self, title, target, app_config=None):
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
            if app_config is None:
                target()
            else:
                target(app_config)
        except Exception as error:
            self.enqueue_log(f"Erro inesperado: {error}")
        finally:
            self.refresh_status_cards()
            self.set_buttons_state("normal")

    def set_buttons_state(self, state):
        self.log_queue.put(("buttons", state))

    def refresh_status_cards(self):
        self.log_queue.put(("refresh_status", None))

    def set_app_update_status(self, app_key: str, state: str, message: str) -> None:
        self.log_queue.put(("update_status", app_key, state, message))

    def flush_log_queue(self):
        while True:
            try:
                item = self.log_queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(item, tuple) and item[0] == "buttons":
                for button in self.buttons:
                    button.configure(state=item[1])
            elif isinstance(item, tuple) and item[0] == "refresh_status":
                self.refresh_all_app_statuses()
            elif isinstance(item, tuple) and item[0] == "update_status":
                _, app_key, state, message = item
                self.apply_app_update_status(app_key, state, message)
            else:
                self.write_log(str(item))

        self.after(100, self.flush_log_queue)

    def log(self, message):
        self.enqueue_log(message)

    def enqueue_log(self, message):
        self.log_queue.put(message)

    def write_log(self, message):
        self.log_history.append(message)
        print(message)

    def get_venv_status(self, app_path: Path, app_config: dict) -> tuple[Path | None, str | None]:
        venv_names = app_config.get("venv_names")
        if not venv_names:
            venv_names = [".venv", "venv"]

        for venv_name in venv_names:
            venv_python = app_path / venv_name / "Scripts" / "python.exe"
            if venv_python.exists():
                return venv_python, venv_name

        return None, None

    def get_app_status(self, app_key: str) -> dict:
        app_config = self.config_data.get("apps", {}).get(app_key, {})
        app_path = self.get_app_path(app_config)
        installed = app_path.exists()
        git_repo = (app_path / ".git").exists()
        _, venv_name = self.get_venv_status(app_path, app_config)

        if installed and git_repo:
            status = "instalado"
        elif installed:
            status = "pasta sem Git"
        else:
            status = "não instalado"

        return {
            "name": app_config.get("name", app_key),
            "status": status,
            "environment": venv_name or "pendente",
            "branch": app_config.get("branch", "release"),
            "port": self.get_app_port(app_config),
            "path": app_path,
        }

    def refresh_app_status(self, app_key):
        status_vars = self.app_status_vars.get(app_key)
        if not status_vars:
            return

        status = self.get_app_status(app_key)
        status_vars["status"].set(
            f"Status: {status['status']} | Ambiente: {status['environment']}"
        )
        status_vars["meta"].set(
            f"Branch: {status['branch']} | Porta: {status['port']}"
        )
        status_vars["path"].set(f"Caminho: {status['path']}")

    def refresh_all_app_statuses(self):
        for app_key in self.app_status_vars:
            self.refresh_app_status(app_key)

    def get_update_status_display(self, state: str) -> tuple[str, str]:
        status_map = {
            "not_checked": ("Não verificado", self.colors["secondary"]),
            "up_to_date": ("Atualizado", self.colors["green"]),
            "update_available": ("Atualização disponível", self.colors["warning"]),
            "updated_success": ("Atualizado com sucesso", self.colors["green"]),
            "install_success": ("Instalação concluída", self.colors["green"]),
            "repair_success": ("Reparo concluído", self.colors["green"]),
            "not_installed": ("Não instalado", self.colors["secondary"]),
            "check_error": ("Erro ao verificar", "#C62828"),
            "update_error": ("Erro ao atualizar", "#C62828"),
            "install_repair_error": ("Erro ao instalar/reparar", "#C62828"),
        }
        return status_map.get(state, ("Não verificado", self.colors["secondary"]))

    def apply_app_update_status(self, app_key: str, state: str, message: str):
        self.update_status[app_key] = {
            "state": state,
            "message": message,
        }
        status_vars = self.app_status_vars.get(app_key)
        if not status_vars:
            return

        label, color = self.get_update_status_display(state)
        update_widget = status_vars.get("update_widget")
        if update_widget is not None:
            update_widget.configure(fg=color)
        status_vars["update"].set(f"Atualização: {label}")
        status_vars["action"].set(f"Última ação: {message}")

    def initialize_app_update_status(self, app_key: str):
        status = self.get_app_status(app_key)
        if status["status"] == "não instalado":
            self.apply_app_update_status(
                app_key,
                "not_installed",
                "Aplicação ainda não instalada nesta máquina.",
            )
            return

        self.apply_app_update_status(
            app_key,
            "not_checked",
            "Atualização ainda não verificada.",
        )

    def get_app_path(self, app_config):
        return Path(os.path.expandvars(app_config.get("local_path", "")))

    def get_app_key(self, app_config):
        apps = self.config_data.get("apps", {})
        for app_key, configured_app in apps.items():
            if configured_app is app_config:
                return app_key

        app_name = app_config.get("name")
        for app_key, configured_app in apps.items():
            if configured_app.get("name") == app_name:
                return app_key

        return None

    def get_app_port(self, app_config):
        try:
            return int(app_config.get("port", 8501))
        except (TypeError, ValueError):
            self.enqueue_log("Porta inválida na configuração. Usando porta padrão 8501.")
            return 8501

    def find_git_executable(self) -> str | None:
        git_path = shutil.which("git")
        if git_path:
            return git_path

        common_paths = [
            r"%ProgramFiles%\Git\cmd\git.exe",
            r"%ProgramFiles%\Git\bin\git.exe",
            r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe",
        ]
        for candidate in common_paths:
            expanded_path = Path(os.path.expandvars(candidate))
            if expanded_path.exists():
                return str(expanded_path)

        return None

    def ensure_git_available(self) -> bool:
        self.enqueue_log("Verificando Git...")

        git_path = self.find_git_executable()
        if git_path:
            self.git_executable = git_path
            self.enqueue_log(f"Git encontrado: {git_path}")
            return True

        self.enqueue_log("Git não encontrado.")
        should_install = self.ask_yes_no(
            "Git não encontrado",
            "Git não foi encontrado nesta máquina.\n\n"
            "O launcher precisa do Git para verificar atualizações, atualizar "
            "e instalar os apps.\n\n"
            "Deseja tentar instalar o Git automaticamente usando winget?",
        )
        if not should_install:
            self.enqueue_log("Instalação do Git cancelada pelo usuário.")
            return False

        winget_path = shutil.which("winget")
        if not winget_path:
            self.enqueue_log(
                "Instalação automática do Git não foi possível. Solicite apoio ao TI."
            )
            return False

        self.enqueue_log("Tentando instalar Git via winget...")
        install_code, _ = self.run_command(
            [winget_path, "install", "-e", "--id", "Git.Git"],
            BASE_DIR,
        )
        self.enqueue_log(
            "Talvez seja necessário fechar e abrir novamente o launcher para o PATH ser atualizado."
        )

        if install_code != 0:
            self.enqueue_log(
                "Instalação automática do Git não foi possível. Solicite apoio ao TI."
            )
            return False

        git_path = self.find_git_executable()
        if git_path:
            self.git_executable = git_path
            self.enqueue_log(f"Git encontrado: {git_path}")
            return True

        self.enqueue_log(
            "Git instalado, mas ainda não foi possível confirmar o comando nesta sessão."
        )
        return False

    def ask_yes_no(self, title, message):
        if threading.current_thread() is threading.main_thread():
            return messagebox.askyesno(title, message, parent=self)

        result = {"answer": False}
        done = threading.Event()

        def show_messagebox():
            try:
                result["answer"] = messagebox.askyesno(title, message, parent=self)
            finally:
                done.set()

        self.after(0, show_messagebox)
        done.wait()
        return result["answer"]

    def show_warning(self, title, message):
        if threading.current_thread() is threading.main_thread():
            messagebox.showwarning(title, message, parent=self)
            return

        done = threading.Event()

        def show_messagebox():
            try:
                messagebox.showwarning(title, message, parent=self)
            finally:
                done.set()

        self.after(0, show_messagebox)
        done.wait()

    def find_venv_python(self, app_path: Path, app_config: dict) -> Path | None:
        venv_python, venv_name = self.get_venv_status(app_path, app_config)
        if venv_python is not None:
            self.enqueue_log(f"Ambiente virtual encontrado: {venv_name}")
            return venv_python

        self.enqueue_log("Ambiente virtual não encontrado.")
        return None

    def create_venv(self, app_path: Path) -> Path | None:
        venv_path = app_path / ".venv"
        venv_python = venv_path / "Scripts" / "python.exe"

        self.enqueue_log(f"Criando ambiente virtual em: {venv_path}")
        return_code, _ = self.run_command(
            [sys.executable, "-m", "venv", ".venv"],
            app_path,
        )
        if return_code != 0:
            self.enqueue_log("Erro ao criar ambiente virtual.")
            return None

        if not venv_python.exists():
            self.enqueue_log(f"Erro: Python do ambiente virtual não encontrado: {venv_python}")
            return None

        self.enqueue_log("Ambiente virtual criado: .venv")
        return venv_python

    def upgrade_pip(self, app_path: Path, venv_python: Path) -> bool:
        self.enqueue_log("Atualizando pip no ambiente virtual...")
        return_code, _ = self.run_command(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
            app_path,
        )
        if return_code != 0:
            self.enqueue_log("Falha ao atualizar pip.")
            return False

        return True

    def install_requirements(self, app_path: Path, venv_python: Path) -> bool:
        requirements = app_path / "requirements.txt"

        if not requirements.exists():
            self.enqueue_log(
                "requirements.txt não encontrado. Pulando instalação de dependências."
            )
            return True

        self.enqueue_log("Instalando dependências do requirements.txt...")
        return_code, _ = self.run_command(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            app_path,
        )
        if return_code != 0:
            self.enqueue_log("Falha ao instalar dependências.")
            return False

        self.enqueue_log("Dependências instaladas com sucesso.")
        return True

    def has_streamlit(self, venv_python: Path) -> bool:
        app_path = venv_python.parents[2]
        return_code, _ = self.run_command(
            [str(venv_python), "-m", "streamlit", "--version"],
            app_path,
        )
        return return_code == 0

    def wait_for_localhost(self, url: str, timeout_seconds: int = 15) -> bool:
        self.enqueue_log(f"Aguardando {url}...")
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1):
                    return True
            except urllib.error.HTTPError:
                return True
            except (OSError, urllib.error.URLError, TimeoutError):
                time.sleep(0.5)

        self.enqueue_log(
            f"Aviso: {url} não respondeu em {timeout_seconds} segundos. Abrindo mesmo assim."
        )
        return False

    def find_browser_executable(self, paths):
        for browser_path in paths:
            expanded_path = Path(os.path.expandvars(browser_path))
            if expanded_path.exists():
                return expanded_path

        return None

    def open_browser_app_window(self, url: str) -> None:
        edge_paths = [
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
            r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe",
        ]
        chrome_paths = [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ]

        edge_path = self.find_browser_executable(edge_paths)
        if edge_path is not None:
            self.enqueue_log("Abrindo em modo app: Microsoft Edge")
            try:
                subprocess.Popen([str(edge_path), f"--app={url}", "--start-maximized"])
                return
            except OSError as error:
                self.enqueue_log(f"Falha ao abrir Microsoft Edge: {error}")

        chrome_path = self.find_browser_executable(chrome_paths)
        if chrome_path is not None:
            self.enqueue_log("Abrindo em modo app: Google Chrome")
            try:
                subprocess.Popen([str(chrome_path), f"--app={url}", "--start-maximized"])
                return
            except OSError as error:
                self.enqueue_log(f"Falha ao abrir Google Chrome: {error}")

        self.enqueue_log("Edge/Chrome não encontrado. Abrindo no navegador padrão.")
        webbrowser.open(url)

    def prepare_app_environment(
        self,
        app_path: Path,
        app_config: dict,
        ask_confirmation: bool = True,
    ) -> Path | None:
        app_name = app_config.get("name", "sem nome")
        if ask_confirmation:
            should_prepare = self.ask_yes_no(
                "Ambiente virtual não encontrado",
                f"Ambiente virtual não encontrado para {app_name}.\n\n"
                "Deseja preparar esta aplicação agora?",
            )
            if not should_prepare:
                self.enqueue_log("Preparo do ambiente virtual cancelado pelo usuário.")
                return None

        venv_python = self.create_venv(app_path)
        if venv_python is None:
            return None

        requirements = app_path / "requirements.txt"
        if requirements.exists() and not self.upgrade_pip(app_path, venv_python):
            return None

        if not self.install_requirements(app_path, venv_python):
            return None

        return venv_python

    def prepare_existing_environment(self, app_path: Path, app_config: dict) -> bool:
        venv_python = self.find_venv_python(app_path, app_config)
        if venv_python is None:
            venv_python = self.prepare_app_environment(
                app_path,
                app_config,
                ask_confirmation=False,
            )
            if venv_python is None:
                return False
            return True

        return self.install_requirements(app_path, venv_python)

    def checkout_configured_branch(self, app_path: Path, branch: str) -> bool:
        git_command = self.git_executable or "git"

        self.enqueue_log(f"Trocando para branch {branch}...")
        checkout_code, _ = self.run_command([git_command, "checkout", branch], app_path)
        if checkout_code == 0:
            return True

        self.enqueue_log(f"Branch local {branch} não encontrada. Criando a partir da remota.")
        checkout_new_code, _ = self.run_command(
            [git_command, "checkout", "-b", branch, f"origin/{branch}"],
            app_path,
        )
        return checkout_new_code == 0

    def install_or_repair_app(self, app_config) -> bool:
        app_path = self.get_app_path(app_config)
        app_name = app_config.get("name", "sem nome")
        repo_url = app_config.get("repo_url", "")
        branch = app_config.get("branch", "release")
        app_key = self.get_app_key(app_config)
        was_installed = app_path.exists()

        self.enqueue_log(f"Aplicação: {app_name}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not repo_url:
            self.enqueue_log("URL do repositório não configurada.")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "install_repair_error",
                    "Não foi possível preparar a aplicação.",
                )
            return False

        if not self.ensure_git_available():
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "install_repair_error",
                    "Não foi possível preparar a aplicação.",
                )
            return False

        git_command = self.git_executable or "git"

        if not app_path.exists():
            self.enqueue_log("Aplicação não encontrada localmente.")
            should_install = self.ask_yes_no(
                "Aplicação não instalada",
                f"A aplicação {app_name} ainda não está instalada nesta máquina.\n\n"
                "Deseja instalar agora?",
            )
            if not should_install:
                self.enqueue_log("Instalação cancelada pelo usuário.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "not_installed",
                        "Aplicação ainda não instalada nesta máquina.",
                    )
                return False

            try:
                app_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                self.enqueue_log(f"Não foi possível criar a pasta pai: {error}")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return False

            self.enqueue_log(f"Clonando {repo_url}...")
            clone_code, _ = self.run_command(
                [git_command, "clone", "--branch", branch, repo_url, str(app_path)],
                app_path.parent,
            )
            if clone_code != 0:
                self.enqueue_log("Clone falhou.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return False

            self.enqueue_log("Clone concluído.")
        else:
            self.enqueue_log("Pasta local encontrada.")
            if not (app_path / ".git").exists():
                message = (
                    "A pasta da aplicação já existe, mas não parece ser um repositório Git.\n\n"
                    "Por segurança, o launcher não irá sobrescrever esta pasta.\n"
                    "Verifique o caminho configurado ou escolha outra pasta."
                )
                self.enqueue_log(message)
                self.show_warning("Pasta existente sem Git", message)
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return False

            self.enqueue_log("Repositório Git detectado.")
            self.enqueue_log(f"Buscando branch remota {branch}...")
            fetch_code, _ = self.run_command([git_command, "fetch", "origin", branch], app_path)
            if fetch_code != 0:
                self.enqueue_log("Não foi possível buscar a branch remota.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return False

            if not self.checkout_configured_branch(app_path, branch):
                self.enqueue_log("Não foi possível trocar para a branch configurada.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return False

            self.enqueue_log("Atualizando código...")
            pull_code, _ = self.run_command(
                [git_command, "pull", "--ff-only", "origin", branch],
                app_path,
            )
            if pull_code != 0:
                self.enqueue_log("Atualização via Git falhou.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return False

        if not self.prepare_existing_environment(app_path, app_config):
            self.enqueue_log("Não foi possível preparar a aplicação.")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "install_repair_error",
                    "Não foi possível preparar a aplicação.",
                )
            return False

        self.enqueue_log("Aplicação preparada com sucesso.")
        if app_key:
            if was_installed:
                self.set_app_update_status(
                    app_key,
                    "repair_success",
                    "Aplicação verificada e preparada com sucesso.",
                )
            else:
                self.set_app_update_status(
                    app_key,
                    "install_success",
                    "Aplicação instalada e preparada com sucesso.",
                )
        return True

    def check_update(self, app_config):
        app_path = self.get_app_path(app_config)
        branch = app_config.get("branch", "release")
        app_key = self.get_app_key(app_config)

        self.enqueue_log(f"Aplicação: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            self.enqueue_log("Repositório ainda não existe nesta máquina.")
            self.enqueue_log("Clone automático será implementado em etapa futura.")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "not_installed",
                    "Aplicação ainda não instalada nesta máquina.",
                )
            return

        if not self.ensure_git_available():
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "check_error",
                    "Não foi possível verificar atualizações.",
                )
            return

        git_command = self.git_executable or "git"

        fetch_code, _ = self.run_command([git_command, "fetch", "origin", branch], app_path)
        if fetch_code != 0:
            self.enqueue_log("Não foi possível verificar atualização.")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "check_error",
                    "Não foi possível verificar atualizações.",
                )
            return

        local_code, local_commit = self.run_command([git_command, "rev-parse", "HEAD"], app_path)
        remote_code, remote_commit = self.run_command(
            [git_command, "rev-parse", f"origin/{branch}"],
            app_path,
        )

        if local_code != 0 or remote_code != 0:
            self.enqueue_log("Não foi possível comparar os commits.")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "check_error",
                    "Não foi possível verificar atualizações.",
                )
            return

        local_short = local_commit.strip()[:8]
        remote_short = remote_commit.strip()[:8]
        self.enqueue_log(f"Commit local:  {local_short}")
        self.enqueue_log(f"Commit remoto: {remote_short}")

        if local_short == remote_short:
            self.enqueue_log("Status: aplicação atualizada")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "up_to_date",
                    "Software já está na versão mais recente.",
                )
        else:
            self.enqueue_log("Status: atualização disponível")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "update_available",
                    "Nova versão disponível para instalação.",
                )

    def update_app(self, app_config):
        app_path = self.get_app_path(app_config)
        branch = app_config.get("branch", "release")
        app_key = self.get_app_key(app_config)

        self.enqueue_log(f"Aplicação: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            should_install = self.ask_yes_no(
                "Aplicação não instalada",
                "Aplicação não instalada.\n\nDeseja instalar agora?",
            )
            if not should_install:
                self.enqueue_log("Aplicação não instalada. Use Instalar/Reparar.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "not_installed",
                        "Aplicação ainda não instalada nesta máquina.",
                    )
                return

            if not self.install_or_repair_app(app_config):
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "update_error",
                        "Não foi possível concluir a atualização.",
                    )
                return
            return

        if not self.ensure_git_available():
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "update_error",
                    "Não foi possível concluir a atualização.",
                )
            return

        git_command = self.git_executable or "git"

        pull_code, pull_output = self.run_command(
            [git_command, "pull", "--ff-only", "origin", branch],
            app_path,
        )
        if pull_code != 0:
            self.enqueue_log("Atualização via Git falhou.")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "update_error",
                    "Não foi possível concluir a atualização.",
                )
            return

        venv_python = self.find_venv_python(app_path, app_config)
        if venv_python is None:
            venv_python = self.prepare_app_environment(app_path, app_config)
            if venv_python is None:
                self.enqueue_log("Código atualizado, mas ambiente virtual não preparado.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "update_error",
                        "Não foi possível concluir a atualização.",
                    )
                return
            if app_key:
                if "Already up to date." in pull_output:
                    self.set_app_update_status(
                        app_key,
                        "up_to_date",
                        "Software já estava atualizado.",
                    )
                else:
                    self.set_app_update_status(
                        app_key,
                        "updated_success",
                        "Atualização instalada com sucesso.",
                    )
            return

        if not self.install_requirements(app_path, venv_python):
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "update_error",
                    "Não foi possível concluir a atualização.",
                )
            return

        if app_key:
            if "Already up to date." in pull_output:
                self.set_app_update_status(
                    app_key,
                    "up_to_date",
                    "Software já estava atualizado.",
                )
            else:
                self.set_app_update_status(
                    app_key,
                    "updated_success",
                    "Atualização instalada com sucesso.",
                )

    def open_app(self, app_config):
        app_path = self.get_app_path(app_config)
        entrypoint = app_config.get("entrypoint", "app.py")
        app_key = self.get_app_key(app_config)

        self.enqueue_log(f"Aplicação: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            should_install = self.ask_yes_no(
                "Aplicação não instalada",
                "Aplicação não instalada.\n\nDeseja instalar agora?",
            )
            if not should_install:
                self.enqueue_log("Abertura cancelada porque a aplicação não está instalada.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "not_installed",
                        "Aplicação ainda não instalada nesta máquina.",
                    )
                return

            if not self.install_or_repair_app(app_config):
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return

        venv_python = self.find_venv_python(app_path, app_config)
        if venv_python is None:
            venv_python = self.prepare_app_environment(app_path, app_config)
            if venv_python is None:
                self.enqueue_log("Abertura cancelada porque o ambiente não foi preparado.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return

        entrypoint_path = app_path / entrypoint
        if not entrypoint_path.exists():
            self.enqueue_log(f"Arquivo de entrada não encontrado: {entrypoint_path}")
            if app_key:
                self.set_app_update_status(
                    app_key,
                    "install_repair_error",
                    "Não foi possível preparar a aplicação.",
                )
            return

        if not self.has_streamlit(venv_python):
            should_install = self.ask_yes_no(
                "Dependências não encontradas",
                "O Streamlit ou alguma dependência necessária não foi encontrada.\n\n"
                "Deseja instalar as dependências agora?",
            )
            if not should_install:
                self.enqueue_log("Abertura cancelada porque as dependências não foram instaladas.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return

            if not self.install_requirements(app_path, venv_python):
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return

            if not self.has_streamlit(venv_python):
                self.enqueue_log("Streamlit ainda não foi encontrado após instalar dependências.")
                if app_key:
                    self.set_app_update_status(
                        app_key,
                        "install_repair_error",
                        "Não foi possível preparar a aplicação.",
                    )
                return

        port = self.get_app_port(app_config)
        url = f"http://localhost:{port}"
        command = [
            str(venv_python),
            "-m",
            "streamlit",
            "run",
            entrypoint,
            "--server.port",
            str(port),
            "--server.headless",
            "true",
        ]
        self.enqueue_log(f"Iniciando Streamlit na porta {port}...")
        self.enqueue_log(f"$ {subprocess.list2cmdline(command)}")

        try:
            process = subprocess.Popen(
                command,
                cwd=str(app_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            self.enqueue_log(f"Erro ao abrir aplicação: {error}")
            return

        self.enqueue_log("Aplicação iniciada em segundo plano.")
        output_thread = threading.Thread(
            target=self.read_process_output,
            args=(process,),
            daemon=True,
        )
        output_thread.start()
        self.wait_for_localhost(url)
        self.open_browser_app_window(url)

    def is_execution_policy_error(self, text: str) -> bool:
        lower_text = text.lower()
        indicators = [
            "executionpolicy",
            "running scripts is disabled",
            "activate.ps1",
            "não pode ser carregado",
            "não pode ser carregado",
            "execução de scripts foi desabilitada",
            "execução de scripts foi desabilitada",
        ]
        return any(indicator in lower_text for indicator in indicators)

    def log_execution_policy_help(self):
        self.enqueue_log(
            "Foi detectado um erro relacionado à política de execução do PowerShell."
        )
        self.enqueue_log(
            "O launcher não precisa ativar o ambiente virtual manualmente."
        )
        self.enqueue_log("Tente abrir o app novamente pelo botão Abrir.")
        self.enqueue_log(
            "Se o problema persistir, envie este log ao suporte técnico."
        )

    def read_process_output(self, process):
        if process.stdout is None:
            return

        execution_policy_detected = False
        for line in process.stdout:
            clean_line = line.rstrip()
            self.enqueue_log(clean_line)
            if self.is_execution_policy_error(clean_line):
                execution_policy_detected = True

        return_code = process.wait()
        self.enqueue_log(f"Processo encerrado com código {return_code}.")
        if return_code != 0 and execution_policy_detected:
            self.log_execution_policy_help()

    def run_command(self, command, cwd):
        self.enqueue_log(f"{cwd}> {subprocess.list2cmdline(command)}")
        output_lines = []

        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
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
            self.enqueue_log(f"Comando terminou com código {return_code}.")
            if self.is_execution_policy_error("\n".join(output_lines)):
                self.log_execution_policy_help()

        return return_code, "\n".join(output_lines)


if __name__ == "__main__":
    launcher = CoastdownLauncher()
    if not getattr(launcher, "startup_cancelled", False):
        launcher.mainloop()
