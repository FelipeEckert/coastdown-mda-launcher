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
        self.git_executable = None
        self.startup_cancelled = False

        self.config_data, _ = self.load_config()
        if self.startup_cancelled:
            self.destroy()
            return

        self.configure_ui()
        self.after(100, self.flush_log_queue)

    def load_config(self):
        if CONFIG_FILE.exists():
            config_data = self.read_config_file(CONFIG_FILE)
            return config_data, False

        if not CONFIG_EXAMPLE_FILE.exists():
            messagebox.showerror(
                "Configuracao nao encontrada",
                "Nenhum arquivo config.json ou config.example.json foi encontrado.",
            )
            return {"apps": {}}, False

        self.enqueue_log("Configuracao inicial necessaria.")
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
                "Erro ao ler configuracao",
                f"Nao foi possivel ler {config_path.name}:\n{error}",
            )
            return {"apps": {}}

    def create_initial_config(self, example_config):
        recommended_root = Path.home() / "CoastdownMDA"
        answer = messagebox.askyesnocancel(
            "Configuracao inicial",
            "O Coastdown MDA Launcher ainda nao foi configurado nesta maquina.\n\n"
            "Escolha onde os aplicativos Coastdown serao instalados.\n"
            f"Local recomendado:\n{recommended_root}\n\n"
            "Deseja usar o local recomendado?",
            parent=self,
        )

        if answer is None:
            messagebox.showinfo(
                "Configuracao cancelada",
                "Configuracao inicial cancelada. O launcher sera encerrado.",
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
                    "Configuracao cancelada",
                    "Nenhuma pasta foi escolhida. O launcher sera encerrado.",
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
                f"Nao foi possivel criar as pastas iniciais:\n{error}",
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
                "Erro ao criar configuracao",
                f"Nao foi possivel criar config.json:\n{error}",
                parent=self,
            )
            return None

        self.enqueue_log(f"Pasta raiz escolhida: {root_path}")
        self.enqueue_log("config.json criado com sucesso.")
        return config_data

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

        install_button = tk.Button(
            block,
            text="Instalar/Reparar",
            command=lambda: self.run_in_background(
                f"Instalar/Reparar - {app_config.get('name', app_key)}",
                self.install_or_repair_app,
                app_config,
            ),
            width=18,
        )
        install_button.grid(row=2, column=2, sticky="w", padx=(0, 8))

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
        open_button.grid(row=2, column=3, sticky="w")

        self.buttons.extend([check_button, update_button, install_button, open_button])

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

    def get_app_port(self, app_config):
        try:
            return int(app_config.get("port", 8501))
        except (TypeError, ValueError):
            self.enqueue_log("Porta invalida na configuracao. Usando porta padrao 8501.")
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

        self.enqueue_log("Git nao encontrado.")
        should_install = self.ask_yes_no(
            "Git nao encontrado",
            "Git nao foi encontrado nesta maquina.\n\n"
            "O launcher precisa do Git para verificar atualizacoes, atualizar "
            "e instalar os apps.\n\n"
            "Deseja tentar instalar o Git automaticamente usando winget?",
        )
        if not should_install:
            self.enqueue_log("Instalacao do Git cancelada pelo usuario.")
            return False

        winget_path = shutil.which("winget")
        if not winget_path:
            self.enqueue_log(
                "Instalacao automatica do Git nao foi possivel. Solicite apoio ao TI."
            )
            return False

        self.enqueue_log("Tentando instalar Git via winget...")
        install_code, _ = self.run_command(
            [winget_path, "install", "-e", "--id", "Git.Git"],
            BASE_DIR,
        )
        self.enqueue_log(
            "Talvez seja necessario fechar e abrir novamente o launcher para o PATH ser atualizado."
        )

        if install_code != 0:
            self.enqueue_log(
                "Instalacao automatica do Git nao foi possivel. Solicite apoio ao TI."
            )
            return False

        git_path = self.find_git_executable()
        if git_path:
            self.git_executable = git_path
            self.enqueue_log(f"Git encontrado: {git_path}")
            return True

        self.enqueue_log(
            "Git instalado, mas ainda nao foi possivel confirmar o comando nesta sessao."
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
        venv_names = app_config.get("venv_names")
        if not venv_names:
            venv_names = [".venv", "venv"]

        for venv_name in venv_names:
            venv_python = app_path / venv_name / "Scripts" / "python.exe"
            if venv_python.exists():
                self.enqueue_log(f"Ambiente virtual encontrado: {venv_name}")
                return venv_python

        self.enqueue_log("Ambiente virtual nao encontrado.")
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
            self.enqueue_log(f"Erro: Python do ambiente virtual nao encontrado: {venv_python}")
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
                "requirements.txt nao encontrado. Pulando instalacao de dependencias."
            )
            return True

        self.enqueue_log("Instalando dependencias do requirements.txt...")
        return_code, _ = self.run_command(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            app_path,
        )
        if return_code != 0:
            self.enqueue_log("Falha ao instalar dependencias.")
            return False

        self.enqueue_log("Dependencias instaladas com sucesso.")
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
            f"Aviso: {url} nao respondeu em {timeout_seconds} segundos. Abrindo mesmo assim."
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
                subprocess.Popen([str(edge_path), f"--app={url}"])
                return
            except OSError as error:
                self.enqueue_log(f"Falha ao abrir Microsoft Edge: {error}")

        chrome_path = self.find_browser_executable(chrome_paths)
        if chrome_path is not None:
            self.enqueue_log("Abrindo em modo app: Google Chrome")
            try:
                subprocess.Popen([str(chrome_path), f"--app={url}"])
                return
            except OSError as error:
                self.enqueue_log(f"Falha ao abrir Google Chrome: {error}")

        self.enqueue_log("Edge/Chrome nao encontrado. Abrindo no navegador padrao.")
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
                "Ambiente virtual nao encontrado",
                f"Ambiente virtual nao encontrado para {app_name}.\n\n"
                "Deseja preparar esta aplicacao agora?",
            )
            if not should_prepare:
                self.enqueue_log("Preparo do ambiente virtual cancelado pelo usuario.")
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

        self.enqueue_log(f"Branch local {branch} nao encontrada. Criando a partir da remota.")
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

        self.enqueue_log(f"Aplicacao: {app_name}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not repo_url:
            self.enqueue_log("URL do repositorio nao configurada.")
            return False

        if not self.ensure_git_available():
            return False

        git_command = self.git_executable or "git"

        if not app_path.exists():
            self.enqueue_log("Aplicacao nao encontrada localmente.")
            should_install = self.ask_yes_no(
                "Aplicacao nao instalada",
                f"A aplicacao {app_name} ainda nao esta instalada nesta maquina.\n\n"
                "Deseja instalar agora?",
            )
            if not should_install:
                self.enqueue_log("Instalacao cancelada pelo usuario.")
                return False

            try:
                app_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                self.enqueue_log(f"Nao foi possivel criar a pasta pai: {error}")
                return False

            self.enqueue_log(f"Clonando {repo_url}...")
            clone_code, _ = self.run_command(
                [git_command, "clone", "--branch", branch, repo_url, str(app_path)],
                app_path.parent,
            )
            if clone_code != 0:
                self.enqueue_log("Clone falhou.")
                return False

            self.enqueue_log("Clone concluido.")
        else:
            self.enqueue_log("Pasta local encontrada.")
            if not (app_path / ".git").exists():
                message = (
                    "A pasta da aplicacao ja existe, mas nao parece ser um repositorio Git.\n\n"
                    "Por seguranca, o launcher nao ira sobrescrever esta pasta.\n"
                    "Verifique o caminho configurado ou escolha outra pasta."
                )
                self.enqueue_log(message)
                self.show_warning("Pasta existente sem Git", message)
                return False

            self.enqueue_log("Repositorio Git detectado.")
            self.enqueue_log(f"Buscando branch remota {branch}...")
            fetch_code, _ = self.run_command([git_command, "fetch", "origin", branch], app_path)
            if fetch_code != 0:
                self.enqueue_log("Nao foi possivel buscar a branch remota.")
                return False

            if not self.checkout_configured_branch(app_path, branch):
                self.enqueue_log("Nao foi possivel trocar para a branch configurada.")
                return False

            self.enqueue_log("Atualizando codigo...")
            pull_code, _ = self.run_command(
                [git_command, "pull", "--ff-only", "origin", branch],
                app_path,
            )
            if pull_code != 0:
                self.enqueue_log("Atualizacao via Git falhou.")
                return False

        if not self.prepare_existing_environment(app_path, app_config):
            self.enqueue_log("Nao foi possivel preparar a aplicacao.")
            return False

        self.enqueue_log("Aplicacao preparada com sucesso.")
        return True

    def check_update(self, app_config):
        app_path = self.get_app_path(app_config)
        branch = app_config.get("branch", "release")

        self.enqueue_log(f"Aplicacao: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            self.enqueue_log("Repositorio ainda nao existe nesta maquina.")
            self.enqueue_log("Clone automatico sera implementado em etapa futura.")
            return

        if not self.ensure_git_available():
            return

        git_command = self.git_executable or "git"

        fetch_code, _ = self.run_command([git_command, "fetch", "origin", branch], app_path)
        if fetch_code != 0:
            self.enqueue_log("Nao foi possivel verificar atualizacao.")
            return

        local_code, local_commit = self.run_command([git_command, "rev-parse", "HEAD"], app_path)
        remote_code, remote_commit = self.run_command(
            [git_command, "rev-parse", f"origin/{branch}"],
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
            should_install = self.ask_yes_no(
                "Aplicacao nao instalada",
                "Aplicacao nao instalada.\n\nDeseja instalar agora?",
            )
            if not should_install:
                self.enqueue_log("Aplicacao nao instalada. Use Instalar/Reparar.")
                return

            if not self.install_or_repair_app(app_config):
                return
            return

        if not self.ensure_git_available():
            return

        git_command = self.git_executable or "git"

        pull_code, _ = self.run_command(
            [git_command, "pull", "--ff-only", "origin", branch],
            app_path,
        )
        if pull_code != 0:
            self.enqueue_log("Atualizacao via Git falhou.")
            return

        venv_python = self.find_venv_python(app_path, app_config)
        if venv_python is None:
            venv_python = self.prepare_app_environment(app_path, app_config)
            if venv_python is None:
                self.enqueue_log("Codigo atualizado, mas ambiente virtual nao preparado.")
                return
            return

        self.install_requirements(app_path, venv_python)

    def open_app(self, app_config):
        app_path = self.get_app_path(app_config)
        entrypoint = app_config.get("entrypoint", "app.py")

        self.enqueue_log(f"Aplicacao: {app_config.get('name', 'sem nome')}")
        self.enqueue_log(f"Caminho local: {app_path}")

        if not app_path.exists():
            should_install = self.ask_yes_no(
                "Aplicacao nao instalada",
                "Aplicacao nao instalada.\n\nDeseja instalar agora?",
            )
            if not should_install:
                self.enqueue_log("Abertura cancelada porque a aplicacao nao esta instalada.")
                return

            if not self.install_or_repair_app(app_config):
                return

        venv_python = self.find_venv_python(app_path, app_config)
        if venv_python is None:
            venv_python = self.prepare_app_environment(app_path, app_config)
            if venv_python is None:
                self.enqueue_log("Abertura cancelada porque o ambiente nao foi preparado.")
                return

        entrypoint_path = app_path / entrypoint
        if not entrypoint_path.exists():
            self.enqueue_log(f"Arquivo de entrada nao encontrado: {entrypoint_path}")
            return

        if not self.has_streamlit(venv_python):
            should_install = self.ask_yes_no(
                "Dependencias nao encontradas",
                "O Streamlit ou alguma dependencia necessaria nao foi encontrada.\n\n"
                "Deseja instalar as dependencias agora?",
            )
            if not should_install:
                self.enqueue_log("Abertura cancelada porque as dependencias nao foram instaladas.")
                return

            if not self.install_requirements(app_path, venv_python):
                return

            if not self.has_streamlit(venv_python):
                self.enqueue_log("Streamlit ainda nao foi encontrado apos instalar dependencias.")
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
        self.wait_for_localhost(url)
        self.open_browser_app_window(url)

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
    if not getattr(launcher, "startup_cancelled", False):
        launcher.mainloop()
