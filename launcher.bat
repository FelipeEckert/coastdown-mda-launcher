@echo off
cd /d "%~dp0"

set "PYTHON_CMD="

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto run_launcher
)

python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto run_launcher
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    goto run_launcher
)

echo Python nao foi encontrado nesta maquina.
echo O Coastdown MDA Launcher precisa do Python para funcionar.
echo.
set /p INSTALL_PYTHON=Deseja tentar instalar o Python automaticamente usando winget? [S/N] 

if /I not "%INSTALL_PYTHON%"=="S" goto install_manual

winget --version >nul 2>&1
if errorlevel 1 goto install_failed

winget install -e --id Python.Python.3.12
if errorlevel 1 goto install_failed

echo.
echo Instalacao concluida. Talvez seja necessario fechar e abrir novamente o launcher para o PATH ser atualizado.
goto end

:install_failed
echo.
echo A instalacao automatica nao foi possivel.
echo Instale o Python manualmente ou peca apoio ao TI.
goto end

:install_manual
echo.
echo Instale o Python manualmente ou peca apoio ao TI.
goto end

:run_launcher
%PYTHON_CMD% launcher.py

:end
pause
