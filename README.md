# Coastdown MDA Launcher

Launcher simples para Windows usado para abrir e atualizar as aplicações Streamlit do Coastdown MDA.

Este repositório não contém o código do Coastdown MDA Standard nem do Coastdown MDA Split. Esses apps continuam em repositórios separados, e o launcher apenas gerencia a execução local usando Git, Python, ambientes virtuais e Streamlit.

## Aplicações Gerenciadas

- Coastdown MDA Standard
- Coastdown MDA Split

## Como Iniciar

Execute o arquivo:

```bat
launcher.bat
```

O arquivo abre o `launcher.py` a partir da própria pasta do projeto.

O launcher abre em janela maximizada para facilitar o uso em telas corporativas.

## Configuração

O arquivo `config.example.json` serve como modelo da configuração esperada.

Na primeira execução, se `config.json` ainda não existir, o launcher inicia uma configuração guiada. O usuário pode usar a pasta recomendada `%USERPROFILE%\CoastdownMDA` ou escolher outra pasta.

Depois da escolha, o launcher cria o `config.json` local automaticamente a partir de `config.example.json`. O `config.example.json` é o modelo versionado; o `config.json` é local da máquina e não deve ser commitado.

Os apps são configurados em subpastas da pasta raiz escolhida:

```text
<root>\standard\cd-streamlit
<root>\split\coastdown-mda-split
```

O launcher cria as pastas intermediárias `standard` e `split`; as pastas finais dos repositórios são criadas pelo `git clone` quando o usuário usa `Instalar/Reparar`.

Cada app pode definir sua própria porta pelo campo `port` no `config.json`. Se o campo não existir, o launcher usa a porta padrão `8501`.

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

O launcher passa a porta diretamente para o Streamlit pela linha de comando. Não é necessário alterar `.streamlit/config.toml` nos repositórios dos apps.

Os apps são abertos em modo app do Microsoft Edge ou Google Chrome e o launcher tenta iniciar essas janelas maximizadas.

## Dependências Da Máquina

O launcher precisa de Git para verificar atualizações, atualizar e instalar apps. Se o Git não for encontrado, o launcher pode perguntar se deve tentar instalar automaticamente usando `winget`.

Em ambientes corporativos, a instalação via `winget` pode depender de permissões da máquina ou apoio do TI. Depois da instalação, talvez seja necessário fechar e abrir o launcher novamente para o PATH ser atualizado. O acesso ao GitHub e ao PyPI também pode depender de liberação do TI.

## Ambientes Virtuais E PowerShell

O launcher não ativa o ambiente virtual via PowerShell. Em vez disso, executa os comandos diretamente pelo `python.exe` do ambiente virtual, por exemplo `venv\Scripts\python.exe -m pip` e `venv\Scripts\python.exe -m streamlit`.

Por isso, normalmente não é necessário alterar a `ExecutionPolicy` do PowerShell para usar o launcher. O usuário não precisa rodar manualmente `.\venv\Scripts\Activate.ps1`, `.\.venv\Scripts\Activate.ps1` nem `Set-ExecutionPolicy`.

Se aparecer algum erro de política de execução, abra o app pelo `launcher.bat` e envie o log ao responsável técnico.

## Atalho Na Área De Trabalho

Na primeira configuração, o launcher pode criar um atalho `Coastdown MDA Launcher.lnk` na Área de Trabalho. O atalho aponta para `launcher.bat` e usa a pasta do launcher como diretório de trabalho.

Também é possível recriar o atalho pela interface, no botão `Criar atalho na Área de Trabalho`.

Se existir o arquivo `assets/coastdown_launcher.ico`, ele será usado como ícone do atalho. Se esse arquivo não existir, o Windows usa o ícone padrão do atalho.

## Instalar/Reparar Apps

Cada app possui um botão `Instalar/Reparar`.

Quando a pasta local do app não existe, o launcher pede confirmação e clona o repositório configurado com Git. Depois disso, prepara o ambiente virtual e instala as dependências do `requirements.txt`.

Quando a pasta local já existe, o launcher verifica se ela é um repositório Git. Por segurança, pastas existentes que não tenham `.git` não são sobrescritas automaticamente; nesses casos, revise o caminho configurado ou escolha outra pasta.

Para repositórios Git existentes, o launcher busca a branch configurada, troca para essa branch quando possível, atualiza com `git pull --ff-only` e reinstala as dependências.

## Status Nos Cards

Cada card mostra o estado de instalação, ambiente virtual detectado, branch, porta, estado de atualização e resultado da última operação relevante.

Os logs técnicos não ocupam mais a tela principal. O usuário deve acompanhar o resumo diretamente nos cards, por exemplo:

```text
Atualização: Atualizado
Última ação: Software já está na versão mais recente.
```

ou:

```text
Atualização: Atualização disponível
Última ação: Nova versão disponível para instalação.
```

Use os botões dos cards para verificar atualização, atualizar, instalar/reparar e abrir cada app.

## O Que O Launcher Faz

- Verifica atualizações com Git pelo botão `Verificar atualização`, comparando commits da branch configurada.
- Atualiza repositórios locais com `git pull --ff-only`.
- Instala ou repara apps com `git clone`, checkout da branch configurada e `git pull --ff-only`.
- Detecta ambientes virtuais `venv` e `.venv`.
- Cria `.venv` e instala `requirements.txt` com confirmação do usuário quando necessário.
- Valida se o Streamlit está disponível antes de abrir o app.
- Abre o app com `python -m streamlit run app.py --server.port <porta> --server.headless true` usando o Python do ambiente virtual do app.
- Tenta abrir Microsoft Edge ou Google Chrome em modo app maximizado, sem abas e sem barra de endereço.
- Usa o navegador padrão como fallback quando Edge/Chrome não são encontrados.

## Restrições

- Não gera executável `.exe`.
- Não instala bibliotecas externas para o launcher.
- Não mistura código dos apps Standard e Split neste repositório.
