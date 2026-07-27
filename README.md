# Meta Chat Exporter v5.4

Aplicação em Python para consolidar, analisar e exportar conversas extraídas dos arquivos HTML da Meta. O projeto lê todos os `.html` de uma pasta de backup, reaproveita a pasta `linked_media/` quando disponível, mescla conversas duplicadas e gera saídas navegáveis em HTML, JSON e CSV.

A versão corrente é **5.4** (métricas de investigação A1–A10, manifesto de
custódia e tipagem mypy sem isenções de módulos).

## Aviso importante

Este projeto trabalha com conteúdo potencialmente sensível.

Os arquivos processados podem conter, por exemplo:

- nomes de usuários e identificadores internos;
- mensagens privadas;
- datas e horários de atividade;
- mídias e anexos;
- links compartilhados;
- transcrições de áudio, quando esse recurso é usado.

Se você pretende compartilhar os arquivos gerados, revise o material antes e considere usar o modo redigido (`--redact` na CLI ou a opção `🔒 Redigir` na interface gráfica).

## O que a ferramenta faz

- Processa exportações HTML da Meta de forma totalmente offline.
- Consolida múltiplos arquivos da mesma pasta em uma base única de conversas.
- Gera um HTML unificado com navegação, busca, galerias e estatísticas.
- Exporta os dados estruturados em JSON e CSV.
- Extrai mídias do perfil e anexos associados às conversas.
- Oferece transcrição local de áudios com Whisper como recurso opcional.
- Permite redigir nomes e números sensíveis para compartilhar relatórios sem expor dados pessoais.

## Execução local e ressalvas

Na prática, o projeto roda praticamente 100% local.

Durante o uso normal, o processamento das conversas, a consolidação, a geração do HTML, a exportação em JSON/CSV e a visualização do resultado são executados na máquina do usuário, sem dependência de APIs externas para analisar os dados.

Ressalvas importantes:

- a instalação de dependências com `pip` exige internet;
- a publicação do repositório no GitHub, naturalmente, exige internet;
- o recurso opcional de transcrição com Whisper também é local, mas pode exigir instalação prévia de dependências adicionais e, dependendo do ambiente, download inicial dos modelos;
- o HTML gerado é autocontido e não depende de CSS ou JavaScript externos, mas links presentes nas próprias mensagens continuam sendo links normais: se o usuário clicar neles no navegador, o acesso ao site de destino dependerá da internet.

## Recursos principais

### Processamento e consolidação

- Leitura automática de todos os arquivos `.html` da pasta selecionada.
- Mesclagem e deduplicação de threads fragmentadas em múltiplos arquivos.
- Fallback de encoding para lidar com exportações heterogêneas.
- Cache incremental por arquivo para acelerar reprocessamentos.
- Parser resiliente para mensagens, chamadas, reações, anexos e eventos de sistema.

### Visualização e exportação

- HTML unificado com sidebar, busca, filtros, galeria de mídias e painel de estatísticas.
- Exportação individual por conversa.
- Suporte a modo escuro, layout responsivo, impressão e exportação em PDF.
- Carregamento progressivo, rolagem otimizada, memória de posição, modo compacto e atalhos de teclado.
- Copiar mensagem, ir para uma data específica e miniestatísticas por conversa.

### Qualidade visual do chat exportado

- Agrupamento de mensagens consecutivas do mesmo autor.
- Destaque para mensagens editadas, mensagens com apenas emojis e links detectados automaticamente.
- Enriquecimento visual para compartilhamentos, menções em grupos e placeholders de mensagens de voz sem anexo.
- Exibição de participantes antigos em grupos como mensagens de sistema.
- Lightbox para imagens e players embutidos para vídeo e áudio.
- **Cores distintas por remetente**: mensagens do alvo (owner) em vermelho e
  mensagens dos demais participantes em azul, em ambos os modos claro e escuro,
  para facilitar a leitura e identificação rápida do remetente.

### Estatísticas e privacidade

- Resumo geral da base, ranking de participantes e top conversas.
- Heatmap de atividade, timeline temporal e nuvem de palavras.
- Cálculo de métricas por conversa e indicadores de atividade por horário.
- Detecção de idioma com `langdetect` opcional e fallback por palavras-chave;
  idiomas fora do mapa de exibição são reportados pelo código, e a detecção de
  emojis usa a biblioteca `emoji` quando disponível, com fallback por regex.
- Modo redigido na GUI e na CLI com `--redact`, agora centralizado em um único
  motor de redação (`RedactionEngine`).

### Análises avançadas (v5.2)

Novas famílias de métricas, expostas no painel HTML e nas exportações JSON/CSV
com nomes de campos consistentes entre os formatos:

- Mensagens editadas por participante.
- Agregações temporais de pagamentos, eventos de grupo, mensagens removidas e
  temporárias.
- Domínios de links compartilhados.
- Indicador de iniciativa (quem inicia e encerra conversas) e índice de
  reciprocidade por DM.
- Sessões de conversa, evolução/esfriamento do contato e streaks de dias
  consecutivos.
- Bigramas e trigramas, métricas linguísticas por participante (razão
  pergunta/afirmação, riqueza de vocabulário, perfil horário).
- Análise de sentimento offline opcional (léxico local, ativável na configuração).
- Sumário automático de insights (picos de atividade, contato mais ativo,
  resposta mais rápida) e filtros do painel por conversa e intervalo de datas.
- Relatório aprofundado por conversa e gráficos com acessibilidade (rótulos ARIA
  e contraste adequado). Os dados do grafo de relacionamentos são estruturais
  (`nodes`/`edges`), com o SVG gerado separadamente.

### Métricas de investigação (v5.3 / v5.4)

Métricas adicionais voltadas para análise investigativa, expostas no painel
HTML (bloco **Investigação**) e nas exportações JSON/CSV. Implementadas em
`stats_investigation.py` e consumidas por `stats.py`:

- **Timeline de contatos (A1)**: primeira e última mensagem de cada contato com
  o alvo, ordenadas por volume — permite mapear quando cada contato iniciou ou
  encerrou comunicação.
- **Atividade noturna (A2)**: contagem de mensagens enviadas entre 00h e 05h por
  autor — identifica comunicação em horários atípicos.
- **Iniciadores de conversa (A3)**: autor da primeira mensagem datada de cada
  conversa.
- **Taxa de resposta em DMs (A4)**: para cada conversa direta, calcula a
  porcentagem de mensagens do contato que o alvo respondeu e vice-versa, com
  janela de 24h — identifica conversas unidirecionais ou ignoradas.
- **Velocidade de conversa (A5)**: msgs/hora em sessões ativas (gap &lt; 30 min)
  por conversa — pico e média de ritmo.
- **Rajadas (A6)**: sequências consecutivas do mesmo autor (mín. 3 mensagens).
- **Removidas por autor (A7)**: mensagens apagadas pelo remetente, por autor.
- **Timeline de links (A8)**: links compartilhados com autor, data e domínio.
- **Dominância em grupos (A9)**: percentual de mensagens por participante em
  conversas com mais de 2 pessoas.
- **Mídia por contato (A10)**: fotos, áudios, vídeos e links por autor, com
  tipo predominante.

### Manifesto de custódia (F4)

Após exportações HTML/JSON/CSV (GUI e CLI), é gerado um JSON de custódia com
SHA-256 dos HTMLs de entrada e dos artefatos de saída (`manifest.py`).

### Transcrição de áudios com Whisper

- Transcrição local de mensagens de voz com CPU ou GPU.
- Cache de transcrições para evitar retrabalho.
- Escolha de modelo e idioma na interface gráfica.
- Injeção posterior de transcrições em HTMLs já gerados.

## Entradas e saídas

### Entrada

- Arquivos HTML da exportação da Meta.
- Pasta `linked_media/` com anexos e mídias, quando presente.
- Arquivo de transcrições opcional para uso via CLI.

### Saída

- HTML unificado com todas as conversas.
- HTML individual por conversa.
- JSON estruturado, com estatísticas opcionais.
- CSV tabular e CSV separado de estatísticas.
- Relatório de estatísticas no terminal via CLI.

## Instalação

### Requisitos

- Python 3.12 ou superior.
- `pip` disponível no ambiente.

> A partir da versão 5.2 o projeto adota o layout de pacote `src/`: todo o código
> vive em `src/meta_chat_exporter/` e é distribuído como o pacote
> `meta_chat_exporter`. Por isso, a forma recomendada de instalar é em **modo
> editável** (`pip install -e .`), que descobre os módulos automaticamente e gera
> os comandos `chat-exporter` (CLI) e `chat-exporter-gui` (GUI).

### Instalação recomendada (modo editável)

```bash
git clone https://github.com/<seu-usuario>/<seu-repositorio>.git
cd Meta_Chat_Exporter

python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install --upgrade pip
pip install -e .
```

Isso instala as dependências da aplicação (PyQt6 e BeautifulSoup) e cria os
scripts de entrada no `venv` (`venv\Scripts\chat-exporter-gui.exe` /
`venv/bin/chat-exporter-gui` e equivalentes para a CLI).

### Instalação alternativa (somente dependências)

Se preferir não instalar o pacote, instale apenas as dependências. Nesse caso os
comandos `chat-exporter`/`chat-exporter-gui` não são criados e você executa a
aplicação como módulo (ver "Como usar").

```bash
pip install -r requirements.txt
```

### Reprodutibilidade de versões

Para reproduzir exatamente o mesmo conjunto de versões usado no desenvolvimento,
use os arquivos de lock:

```bash
pip install -r requirements.lock        # dependências de runtime fixadas
pip install -r requirements-dev.lock    # inclui ferramentas de desenvolvimento
```

## Dependências opcionais

As dependências opcionais estão organizadas como *extras* do pacote.

### Detecção de idioma mais precisa

```bash
pip install -e ".[langdetect]"
# ou, sem instalar o pacote:
pip install langdetect
```

Sem essa dependência, o projeto continua funcional com fallback por palavras-chave.

### Transcrição de áudios com Whisper

```bash
pip install -e ".[transcription]"
# ou, sem instalar o pacote:
pip install openai-whisper
```

Para transcrição, também é necessário:

- instalar o PyTorch compatível com a sua CPU ou GPU;
- ter o FFmpeg disponível no sistema.

Para builds com CUDA, use as instruções oficiais do PyTorch: https://pytorch.org/get-started/locally/

## Como usar

### Interface gráfica

Após instalar em modo editável (`pip install -e .`), abra a GUI com o comando
gerado no `venv`:

```bash
# Windows
venv\Scripts\chat-exporter-gui.exe

# Linux/macOS
venv/bin/chat-exporter-gui
```

Alternativamente, execute como módulo Python (funciona mesmo sem instalar o
pacote, desde que as dependências estejam instaladas):

```bash
python -m meta_chat_exporter.app
```

Ou use o atalho na raiz do projeto (detecta o `venv` automaticamente):

```bash
python run_gui.py
```

> O antigo `python app.py` não funciona mais: com o layout `src/`, os módulos são
> acessados pelo nome do pacote (`meta_chat_exporter.app`), pelo script
> `chat-exporter-gui` ou pelo atalho `python run_gui.py`.

Fluxo recomendado:

1. Selecione a pasta com os arquivos HTML da Meta.
2. Aguarde a consolidação das conversas e a indexação das mídias.
3. Revise, filtre e pesquise as conversas na interface.
4. Exporte em HTML, JSON ou CSV.
5. Se necessário, ative a redação de dados ou a transcrição de áudios.

### Linha de comando

Com o pacote instalado, use o comando `chat-exporter`; sem instalação, use
`python -m meta_chat_exporter.cli`. As opções são idênticas:

```bash
chat-exporter html ./backup_meta
chat-exporter html ./backup_meta --individual
chat-exporter html ./backup_meta --redact
chat-exporter html ./backup_meta --transcricoes ./transcricoes.txt
chat-exporter json ./backup_meta --estatisticas
chat-exporter csv ./backup_meta --estatisticas
chat-exporter stats ./backup_meta

# Equivalente sem instalar o pacote:
python -m meta_chat_exporter.cli html ./backup_meta
```

### Build empacotado da GUI para Windows

É possível gerar um executável autocontido da interface gráfica para Windows usando
PyInstaller, permitindo executar o aplicativo sem instalar Python separadamente.

```bash
pip install -e ".[dev]"
pyinstaller meta-chat-exporter-gui.spec
```

O executável final é gerado em `dist/MetaChatExporter.exe`. A configuração de empacotamento
fica em `meta-chat-exporter-gui.spec` (app "windowed", sem janela de console).

## Estrutura resumida do projeto

O código segue o layout de pacote `src/`:

```text
pyproject.toml                      Metadados, dependências e entry points
src/meta_chat_exporter/
├── __init__.py                     Versão do pacote
├── app.py                          GUI em PyQt6 (entry point chat-exporter-gui)
├── cli.py                          CLI (entry point chat-exporter)
├── parser.py                       Parser principal das conversas
├── consolidation.py                Mesclagem e deduplicação de threads
├── generators_all.py               HTML unificado
├── generators_single.py            HTML individual por conversa
├── generators_base.py              Base compartilhada dos geradores
├── exporters.py                    Exportadores JSON e CSV
├── advanced_stats_schema.py        Esquema compartilhado das métricas avançadas (JSON/CSV)
├── stats.py                        Estatísticas e análises
├── stats_investigation.py          Métricas de investigação (A1–A10)
├── stats_report.py                 Renderização do painel/relatório de estatísticas
├── manifest.py                     Manifesto de custódia (SHA-256 entrada/saída)
├── redaction.py                    Motor centralizado de redação (RedactionEngine)
├── services.py                     Serviços de cache/exportação usados pela GUI
├── transcriber.py                  Transcrição local com Whisper
├── inject_transcriptions.py        Injeção de transcrições em HTML existente
├── i18n/                           Recursos de idioma (strings, stop words, idiomas)
└── ...                             Demais módulos de apoio (models, utils, widgets, etc.)
tests/                              Suíte de testes (unitários + propriedade)
```

## Arquivos gerados durante o uso

Em tempo de execução, o projeto pode gerar arquivos locais como:

- `config.json`
- `.chat_export_cache/`
- `chat_exporter_YYYYMMDD.log`

Esses artefatos não fazem parte do código-fonte e não precisam ser versionados.

## Testes

Instale as ferramentas de desenvolvimento (extra `dev`) e rode a suíte:

```bash
pip install -e ".[dev]"
pytest -q
```

O projeto usa `ruff` (lint + formatação), `mypy` (tipos, gradual) e `pytest` com
testes de propriedade (Hypothesis). Para reproduzir os checks de CI localmente:

```bash
ruff check .
ruff format --check .
pytest -q
```

## Contribuição

Contribuições via issues e pull requests são bem-vindas. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para preparar o ambiente local, seguir o fluxo de colaboração e revisar o checklist de envio.

O repositório inclui automação básica no GitHub Actions para executar a suíte de testes em pushes e pull requests.

## Privacidade

Todo o processamento ocorre localmente. O projeto não depende de serviços externos para analisar os arquivos exportados e o recurso de transcrição, quando habilitado, também é executado localmente.

## Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo `LICENSE` para os termos completos.
