# Meta Chat Exporter v5.2

Aplicação em Python para consolidar, analisar e exportar conversas extraídas dos arquivos HTML da Meta. O projeto lê todos os `.html` de uma pasta de backup, reaproveita a pasta `linked_media/` quando disponível, mescla conversas duplicadas e gera saídas navegáveis em HTML, JSON e CSV.

Esta publicação inicial no GitHub representa o conjunto consolidado de recursos da versão 5.2.

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

### Estatísticas e privacidade

- Resumo geral da base, ranking de participantes e top conversas.
- Heatmap de atividade, timeline temporal e nuvem de palavras.
- Cálculo de métricas por conversa e indicadores de atividade por horário.
- Detecção de idioma com `langdetect` opcional e fallback por palavras-chave.
- Modo redigido na GUI e na CLI com `--redact`.

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

- Python 3.9 ou superior.
- `pip` disponível no ambiente.

### Instalação básica

```bash
git clone https://github.com/<seu-usuario>/<seu-repositorio>.git
cd Meta_Chat_Exporter

python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

## Dependências opcionais

### Detecção de idioma mais precisa

```bash
pip install langdetect
```

Sem essa dependência, o projeto continua funcional com fallback por palavras-chave.

### Transcrição de áudios com Whisper

```bash
pip install openai-whisper
```

Para transcrição, também é necessário:

- instalar o PyTorch compatível com a sua CPU ou GPU;
- ter o FFmpeg disponível no sistema.

Para builds com CUDA, use as instruções oficiais do PyTorch: https://pytorch.org/get-started/locally/

## Como usar

### Interface gráfica

```bash
python app.py
```

Fluxo recomendado:

1. Selecione a pasta com os arquivos HTML da Meta.
2. Aguarde a consolidação das conversas e a indexação das mídias.
3. Revise, filtre e pesquise as conversas na interface.
4. Exporte em HTML, JSON ou CSV.
5. Se necessário, ative a redação de dados ou a transcrição de áudios.

### Linha de comando

```bash
python cli.py html ./backup_meta
python cli.py html ./backup_meta --individual
python cli.py html ./backup_meta --redact
python cli.py html ./backup_meta --transcricoes ./transcricoes.txt
python cli.py json ./backup_meta --estatisticas
python cli.py csv ./backup_meta --estatisticas
python cli.py stats ./backup_meta
```

## Estrutura resumida do projeto

```text
app.py                     GUI em PyQt6
cli.py                     Interface de linha de comando
parser.py                  Parser principal das conversas
consolidation.py           Mesclagem e deduplicação de threads
generators_all.py          HTML unificado
generators_single.py       HTML individual por conversa
exporters.py               Exportadores JSON e CSV
stats.py                   Estatísticas e análises
transcriber.py             Transcrição local com Whisper
inject_transcriptions.py   Injeção de transcrições em HTML existente
tests/                     Suíte de testes
```

## Arquivos gerados durante o uso

Em tempo de execução, o projeto pode gerar arquivos locais como:

- `config.json`
- `.chat_export_cache/`
- `chat_exporter_YYYYMMDD.log`

Esses artefatos não fazem parte do código-fonte e não precisam ser versionados.

## Testes

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Contribuição

Contribuições via issues e pull requests são bem-vindas. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para preparar o ambiente local, seguir o fluxo de colaboração e revisar o checklist de envio.

O repositório inclui automação básica no GitHub Actions para executar a suíte de testes em pushes e pull requests.

## Privacidade

Todo o processamento ocorre localmente. O projeto não depende de serviços externos para analisar os arquivos exportados e o recurso de transcrição, quando habilitado, também é executado localmente.

## Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo `LICENSE` para os termos completos.
