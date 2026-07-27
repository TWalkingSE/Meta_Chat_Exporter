# Guia do Usuário — Meta Chat Exporter v5.4

Este guia é prático e orientado a tarefas. Ele mostra, passo a passo, como sair
de uma pasta de backup da Meta e chegar a relatórios navegáveis em HTML, JSON e
CSV. Para a visão de referência completa (lista de recursos, dependências e
detalhes técnicos), consulte o [README.md](README.md).

> Aviso: as exportações da Meta contêm dados pessoais (mensagens, nomes, números,
> mídias). Antes de compartilhar qualquer arquivo gerado, revise o conteúdo e
> considere o modo redigido (descrito na seção "Compartilhar com segurança").

---

## 1. Antes de começar

### 1.1 O que você precisa

- Python 3.12 ou superior com `pip`.
- A pasta de backup da Meta contendo os arquivos `.html`.
- Opcionalmente, a pasta `linked_media/` (anexos e mídias) dentro do backup.

### 1.2 Como deve ser a pasta de entrada

Aponte sempre a ferramenta para a **pasta**, não para um arquivo isolado. Uma
estrutura típica:

```text
backup_meta/
├── messages_1.html
├── messages_2.html
├── linked_media/
│   ├── foto_001.jpg
│   └── audio_001.mp4
└── ...
```

A ferramenta lê todos os `.html` da pasta, mescla conversas fragmentadas em
vários arquivos e reaproveita a `linked_media/` quando ela existe.

### 1.3 Instalação

A partir da v5.2 o código vive no pacote `meta_chat_exporter` (layout `src/`). A
forma recomendada é instalar em **modo editável**, que cria os comandos
`chat-exporter` (CLI) e `chat-exporter-gui` (GUI) no `venv`:

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install --upgrade pip
pip install -e .
```

> Se você apagar/recriar o `venv`, basta repetir `pip install -e .` na raiz do
> projeto para reinstalar tudo e regenerar os comandos.

Alternativa sem instalar o pacote (instala só as dependências; nesse caso use os
comandos `python -m ...` mostrados adiante):

```bash
pip install -r requirements.txt
```

---

## 2. Caminho rápido (interface gráfica)

Para a maioria dos usuários, a GUI é o caminho mais simples. Após instalar em
modo editável (`pip install -e .`), abra a interface com o comando gerado no
`venv`:

```bash
# Windows
venv\Scripts\chat-exporter-gui.exe

# Linux/macOS
venv/bin/chat-exporter-gui
```

Ou execute como módulo Python (funciona mesmo sem instalar o pacote, desde que as
dependências estejam instaladas):

```bash
python -m meta_chat_exporter.app
```

Ou use o atalho na raiz do projeto (detecta o `venv` automaticamente):

```bash
python run_gui.py
```

> Atenção: o antigo `python app.py` **não funciona mais**. Com o layout `src/`, a
> GUI é aberta pelo script `chat-exporter-gui`, por `python -m meta_chat_exporter.app`
> ou pelo atalho `python run_gui.py`.

1. Clique para **selecionar a pasta** com os arquivos HTML.
2. Aguarde a **consolidação** das conversas e a indexação das mídias.
3. **Revise, filtre e pesquise** as conversas na interface.
4. **Exporte** no formato desejado (HTML, JSON ou CSV).
5. Se for compartilhar, ative a **redação** (botão `🔒 Redigir`).

A primeira execução de uma pasta grande é a mais lenta; execuções seguintes
aproveitam o cache incremental e ficam mais rápidas.

---

## 3. Caminho rápido (linha de comando)

A CLI é ideal para automação e processamento em lote. Com o pacote instalado, o
comando base é `chat-exporter`; sem instalar o pacote, use
`python -m meta_chat_exporter.cli` (as opções são idênticas):

```bash
chat-exporter <comando> <pasta> [opções]
# equivalente sem instalar o pacote:
python -m meta_chat_exporter.cli <comando> <pasta> [opções]
```

Comandos disponíveis: `html`, `json`, `csv`, `stats`.

```bash
# HTML unificado (todas as conversas em um arquivo)
chat-exporter html ./backup_meta

# Um HTML por conversa
chat-exporter html ./backup_meta --individual

# HTML redigido (para compartilhar)
chat-exporter html ./backup_meta --redact

# HTML com transcrições já prontas
chat-exporter html ./backup_meta --transcricoes ./transcricoes.txt

# JSON estruturado, incluindo estatísticas
chat-exporter json ./backup_meta --estatisticas

# CSV tabular + CSV de estatísticas separado
chat-exporter csv ./backup_meta --estatisticas

# Apenas imprimir estatísticas no terminal
chat-exporter stats ./backup_meta
```

Use `-v`/`--verbose` em qualquer comando para logs detalhados (nível DEBUG):

```bash
chat-exporter html ./backup_meta -v
```

---

## 4. Escolhendo o formato de saída

| Quero... | Use |
| --- | --- |
| Ler/navegar as conversas como um chat | `html` (unificado) |
| Arquivar uma conversa específica isolada | `html --individual` |
| Reprocessar os dados em outra ferramenta | `json` |
| Abrir em planilha (Excel, LibreOffice) | `csv` |
| Só ver um resumo numérico rápido | `stats` |

Resumo prático de cada saída:

- **HTML unificado** — sidebar, busca, filtros, galeria de mídias e painel de
  estatísticas, tudo em um arquivo autocontido.
- **HTML individual** — um arquivo por conversa, útil para arquivamento pontual.
- **JSON** — dados estruturados; com `--estatisticas`, inclui o bloco de métricas.
- **CSV** — uma linha por mensagem; com `--estatisticas`, gera um CSV adicional
  só com os números agregados.

> Desde a v5.2, o painel de estatísticas (HTML) e as exportações com
> `--estatisticas` trazem análises avançadas: mensagens editadas, agregações de
> pagamentos/eventos/removidas/temporárias, domínios de links, iniciativa,
> reciprocidade por DM, sessões, esfriamento do contato, streaks, bigramas/
> trigramas, métricas linguísticas, sentimento offline (opcional), além de
> insights automáticos e filtros do painel por conversa e intervalo de datas.
> JSON e CSV usam os mesmos nomes de campos para cada métrica.
>
> Desde a v5.3/v5.4, o painel traz o bloco **Investigação** com:
> - **A1 Timeline de contatos** — primeira e última mensagem de cada contato.
> - **A2 Atividade noturna** — mensagens entre 00h e 05h por autor.
> - **A3 Iniciadores** — quem enviou a primeira mensagem de cada conversa.
> - **A4 Taxa de resposta em DMs** — % respondidas em até 24h (alvo ↔ contato).
> - **A5 Velocidade de conversa** — msgs/hora em sessões ativas (gap &lt; 30 min).
> - **A6 Rajadas** — sequências consecutivas do mesmo autor (mín. 3 msgs).
> - **A7 Removidas por autor** — mensagens apagadas pelo remetente.
> - **A8 Timeline de links** — links com autor, data e domínio.
> - **A9 Dominância em grupos** — % de mensagens por participante.
> - **A10 Mídia por contato** — fotos/áudios/vídeos/links e tipo predominante.
>
> As cores do chat exportado usam tokens compartilhados e legenda: mensagens do
> alvo (owner) em **vermelho** e dos demais em **azul** (claro e escuro).
>
> Após exportar HTML/JSON/CSV, a ferramenta grava um **manifesto de custódia**
> (`manifesto_custodia_*.json`) com SHA-256 dos HTMLs de entrada e dos arquivos
> gerados — útil para cadeia de custódia e verificação de integridade.

---

## 5. Compartilhar com segurança (modo redigido)

Se você vai enviar o resultado para outra pessoa, oculte nomes e números
sensíveis:

- **GUI:** ative a opção `🔒 Redigir` antes de exportar.
- **CLI:** adicione `--redact` (ou `-r`) ao comando `html`.

```bash
chat-exporter html ./backup_meta --redact
```

Mesmo com a redação ativa, **revise o material gerado** antes de compartilhar.
Lembre-se ainda de que links presentes nas próprias mensagens continuam sendo
links normais: clicá-los abre o site de destino no navegador.

---

## 6. Transcrição de áudios (opcional)

A transcrição de mensagens de voz é local (Whisper) e opcional.

1. Instale as dependências de transcrição: `pip install -e ".[transcription]"`
   (consulte o README — exige também PyTorch e FFmpeg).
2. Na **GUI**, escolha o modelo e o idioma e inicie a transcrição; o resultado é
   armazenado em cache para evitar retrabalho. A própria GUI injeta as
   transcrições no HTML gerado.
3. Na **CLI**, passe um arquivo de transcrições pronto ao gerar o HTML:

```bash
chat-exporter html ./backup_meta --transcricoes ./transcricoes.txt
```

---

## 7. Arquivos criados durante o uso

Ao processar uma pasta, a ferramenta pode criar artefatos locais:

- `config.json` — preferências da aplicação.
- `.chat_export_cache/` — cache incremental por arquivo (acelera reprocessos).
- `chat_exporter_YYYYMMDD.log` — log de execução.

Esses arquivos não fazem parte do código-fonte e não precisam ser versionados.
Apagar o cache apenas força um reprocessamento completo na próxima execução.

---

## 8. Solução de problemas

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| `chat-exporter`/`chat-exporter-gui` não encontrado | Pacote não instalado, ou `venv` recriado/apagado | Ative o `venv` e rode `pip install -e .` na raiz; ou use `python -m meta_chat_exporter.app` / `python -m meta_chat_exporter.cli` |
| `python app.py` não funciona | Layout `src/`: o arquivo não fica mais na raiz | Use `chat-exporter-gui` ou `python -m meta_chat_exporter.app` |
| `ModuleNotFoundError: meta_chat_exporter` | Dependências/pacote não instalados no ambiente ativo | Ative o `venv` e rode `pip install -e .` (ou `pip install -r requirements.txt`) |
| "Nenhuma conversa encontrada" | A pasta não contém `.html` da Meta, ou foi apontado um arquivo em vez da pasta | Aponte para a **pasta** que contém os arquivos `.html` |
| Mídias/áudios não aparecem | A pasta `linked_media/` não está junto dos HTMLs | Coloque `linked_media/` dentro da mesma pasta de entrada |
| Anexo ignorado nos logs | Caminho inseguro no HTML (traversal `../` ou caminho absoluto) | Comportamento esperado: a ferramenta rejeita esses caminhos por segurança |
| Caracteres estranhos no texto | Encoding heterogêneo na exportação | O parser tenta vários encodings automaticamente; se persistir, rode com `-v` e verifique o log |
| Processamento muito lento na 1ª vez | Pasta grande sem cache | Normal; execuções seguintes usam o cache e são mais rápidas |
| Transcrição não funciona | Dependências de Whisper/PyTorch/FFmpeg ausentes | Instale conforme a seção de transcrição do README |
| Detecção de idioma imprecisa | `langdetect` não instalado | Instale `langdetect` para precisão; sem ele há fallback por palavras-chave |

Para diagnosticar qualquer comando, execute-o com `-v` e consulte o arquivo de
log gerado na pasta.

---

## 9. Próximos passos

- Referência completa de recursos e dependências: [README.md](README.md).
- Como contribuir e preparar o ambiente de desenvolvimento:
  [CONTRIBUTING.md](CONTRIBUTING.md).
