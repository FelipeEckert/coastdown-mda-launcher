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

Para personalizar caminhos locais, crie um arquivo `config.json` na raiz do projeto com a mesma estrutura do exemplo. O `config.json` e local da maquina e nao deve ser versionado.

Se `config.json` nao existir, o launcher usa `config.example.json` temporariamente e mostra um aviso.

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

## O que o launcher faz

- Verifica atualizacoes com Git.
- Atualiza repositorios locais com `git pull --ff-only`.
- Detecta ambientes virtuais `venv` e `.venv`.
- Cria `.venv` e instala `requirements.txt` com confirmacao do usuario quando necessario.
- Valida se o Streamlit esta disponivel antes de abrir o app.
- Abre o app com `python -m streamlit run app.py --server.port <porta> --server.headless true` usando o Python do ambiente virtual do app.
- Tenta abrir Microsoft Edge ou Google Chrome em modo app, sem abas e sem barra de endereco.
- Usa o navegador padrao como fallback quando Edge/Chrome nao sao encontrados.

## Restricoes

- Nao gera executavel `.exe`.
- Nao clona repositorios automaticamente nesta primeira versao.
- Nao instala bibliotecas externas para o launcher.
- Nao mistura codigo dos apps Standard e Split neste repositorio.
