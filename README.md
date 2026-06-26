# Coastdown MDA Launcher

Launcher simples para Windows usado para abrir e atualizar as aplicacoes Streamlit do Coastdown MDA.

Este repositorio nao contem o codigo do Coastdown MDA Standard nem do Coastdown MDA Split. Esses apps continuam em repositorios separados, e o launcher apenas gerencia a execucao local usando Git, Python, ambientes virtuais e Streamlit.

## Aplicacoes gerenciadas

- Coastdown MDA Standard
- Coastdown MDA Split

## Como iniciar

Execute o arquivo:

```bat
launcher.bat
```

O arquivo abre o `launcher.py` a partir da propria pasta do projeto.

## Configuracao

O arquivo `config.example.json` serve como modelo da configuracao esperada.

Na primeira execucao, se `config.json` ainda nao existir, o launcher inicia uma configuracao guiada. O usuario pode usar a pasta recomendada `%USERPROFILE%\CoastdownMDA` ou escolher outra pasta.

Depois da escolha, o launcher cria o `config.json` local automaticamente a partir de `config.example.json`. O `config.example.json` e o modelo versionado; o `config.json` e local da maquina e nao deve ser commitado.

Os apps sao configurados em subpastas da pasta raiz escolhida:

```text
<root>\standard\cd-streamlit
<root>\split\coastdown-mda-split
```

O launcher cria as pastas intermediarias `standard` e `split`; as pastas finais dos repositorios sao criadas pelo `git clone` quando o usuario usa `Instalar/Reparar`.

Cada app pode definir sua propria porta pelo campo `port` no `config.json`. Se o campo nao existir, o launcher usa a porta padrao `8501`.

Exemplo:

```json
{
  "apps": {
    "standard": {
      "port": 8501
    },
    "split": {
      "port": 8502
    }
  }
}
```

O launcher passa a porta diretamente para o Streamlit pela linha de comando. Nao e necessario alterar `.streamlit/config.toml` nos repositorios dos apps.

## Dependencias da maquina

O launcher precisa de Git para verificar atualizacoes, atualizar e instalar apps. Se o Git nao for encontrado, o launcher pode perguntar se deve tentar instalar automaticamente usando `winget`.

Em ambientes corporativos, a instalacao via `winget` pode depender de permissoes da maquina ou apoio do TI. Depois da instalacao, talvez seja necessario fechar e abrir o launcher novamente para o PATH ser atualizado. O acesso ao GitHub e ao PyPI tambem pode depender de liberacao do TI.

## Ambientes virtuais e PowerShell

O launcher nao ativa o ambiente virtual via PowerShell. Em vez disso, executa os comandos diretamente pelo `python.exe` do ambiente virtual, por exemplo `venv\Scripts\python.exe -m pip` e `venv\Scripts\python.exe -m streamlit`.

Por isso, normalmente nao e necessario alterar a `ExecutionPolicy` do PowerShell para usar o launcher. O usuario nao precisa rodar manualmente `.\venv\Scripts\Activate.ps1`, `.\.venv\Scripts\Activate.ps1` nem `Set-ExecutionPolicy`.

Se aparecer algum erro de politica de execucao, abra o app pelo `launcher.bat` e envie o log ao responsavel tecnico.

## Atalho na Area de Trabalho

Na primeira configuracao, o launcher pode criar um atalho `Coastdown MDA Launcher.lnk` na Area de Trabalho. O atalho aponta para `launcher.bat` e usa a pasta do launcher como diretorio de trabalho.

Tambem e possivel recriar o atalho pela interface, no botao `Criar atalho na Area de Trabalho`.

Se existir o arquivo `assets/coastdown_launcher.ico`, ele sera usado como icone do atalho. Se esse arquivo nao existir, o Windows usa o icone padrao do atalho.

## Instalar/Reparar apps

Cada app possui um botao `Instalar/Reparar`.

Quando a pasta local do app nao existe, o launcher pede confirmacao e clona o repositorio configurado com Git. Depois disso, prepara o ambiente virtual e instala as dependencias do `requirements.txt`.

Quando a pasta local ja existe, o launcher verifica se ela e um repositorio Git. Por seguranca, pastas existentes que nao tenham `.git` nao sao sobrescritas automaticamente; nesses casos, revise o caminho configurado ou escolha outra pasta.

Para repositorios Git existentes, o launcher busca a branch configurada, troca para essa branch quando possivel, atualiza com `git pull --ff-only` e reinstala as dependencias.

## O que o launcher faz

- Verifica atualizacoes com Git.
- Atualiza repositorios locais com `git pull --ff-only`.
- Instala ou repara apps com `git clone`, checkout da branch configurada e `git pull --ff-only`.
- Detecta ambientes virtuais `venv` e `.venv`.
- Cria `.venv` e instala `requirements.txt` com confirmacao do usuario quando necessario.
- Valida se o Streamlit esta disponivel antes de abrir o app.
- Abre o app com `python -m streamlit run app.py --server.port <porta> --server.headless true` usando o Python do ambiente virtual do app.
- Tenta abrir Microsoft Edge ou Google Chrome em modo app, sem abas e sem barra de endereco.
- Usa o navegador padrao como fallback quando Edge/Chrome nao sao encontrados.

## Restricoes

- Nao gera executavel `.exe`.
- Nao instala bibliotecas externas para o launcher.
- Nao mistura codigo dos apps Standard e Split neste repositorio.
