# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e este projeto adere ao [Versionamento Semântico (SemVer)](https://semver.org/lang/pt-BR/).

## Esquema de versionamento

As versões seguem o padrão `MAJOR.MINOR.PATCH`:

- **MAJOR** — mudanças incompatíveis na API/comportamento ou no formato de dados.
- **MINOR** — novas funcionalidades compatíveis com versões anteriores.
- **PATCH** — correções de bugs compatíveis com versões anteriores.

A versão corrente é declarada em [`pyproject.toml`](pyproject.toml) e deve ser
incrementada conforme o esquema acima a cada novo lançamento.

## [Não lançado]

### Adicionado

### Alterado

### Corrigido

## [5.4] - 2026-07-12

Release de métricas de investigação completas (A1–A10), manifesto de custódia e
tipagem mypy sem isenções de módulos.

### Adicionado

- **Iniciadores (A3)**, **velocidade de conversa (A5)**, **rajadas (A6)** e
  **removidas por autor (A7)**.
- **Timeline de links (A8)**, **dominância em grupos (A9)** e **mídia por contato (A10)**.
- Bloco **Investigação** no topo do painel de estatísticas (A1–A10).
- Módulo `stats_investigation.py` (métricas A1–A10 extraídas de `stats.py`).
- Famílias A3/A5–A10 no schema de exportação avançada (JSON/CSV).
- **Manifesto de custódia (F4)**: JSON com SHA-256 dos HTMLs de entrada e artefatos
  exportados (GUI via `ExportService`, CLI html/json/csv); módulo `manifest.py`.
- Tokens de cor centralizados (`constants.COLOR_*`) e legenda no HTML exportado.
- Validação de pasta de áudios/cache antes de iniciar o subprocesso Whisper.
- Redação de `share_url` (IDs longos) e `subscription_users` (aliases).

### Alterado

- `inject_transcriptions` usa `escape_html` centralizado.
- GUI: removida leitura morta de `proc.stderr` (stderr mesclado em stdout).
- Balões sent/received passam a consumir tokens compartilhados (single + all).
- Tipagem mypy: removidas **todas** as isenções de módulos; guards de None e
  anotações em `app.py` / `cli.py` / `generators_all.py`.
- Documentação (README / GUIA) alinhada a A1–A10 e ao manifesto.

## [5.3] - 2026-07-12

Release de métricas de investigação iniciais e endurecimentos de exportação/segurança.

### Adicionado

- **Timeline de contatos (A1)**: primeira e última mensagem de cada contato com o alvo.
- **Atividade noturna (A2)**: mensagens entre 00h e 05h por autor (single-pass).
- **Taxa de resposta em DMs (A4)**: % de mensagens respondidas em até 24h, pulando rajadas do mesmo autor.
- Famílias A1/A2/A4 no esquema `advanced_stats_schema` (export JSON/CSV avançado).
- Allowlist de schemes de URL (`http`/`https`/`mailto`) em cards de compartilhamento.
- Cores do chat exportado: alvo em vermelho, interlocutores em azul (modos claro e escuro).

### Alterado

- Sanitização CSV estendida a estatísticas por participante e categorias genéricas.
- Documentação (README / GUIA) alinhada às métricas de investigação e às cores.

### Corrigido

- A2 deixou de revarrear todas as mensagens e passa a usar acumuladores da passagem única.

## [5.2] - 2025-01-01

Release que consolida as melhorias de análise e projeto do **Meta Chat Exporter**,
evoluindo a aplicação sem reescrevê-la.

### Adicionado

- Versionamento de esquema do cache para invalidar entradas incompatíveis entre versões.
- Motor de redação (redaction) para ocultar/anonimizar dados sensíveis na exportação.
- Estatísticas avançadas no relatório de estatísticas.
- Internacionalização (i18n): strings de interface e de estatísticas externalizadas em
  recursos, além de listas de stop words/idiomas.
- Integração contínua (CI) com matriz Windows + Linux, executando `ruff` e `mypy`.
- Empacotamento e distribuição: configuração de build do pacote e do executável da GUI.
- Este `CHANGELOG.md` e declaração da versão corrente em `pyproject.toml`.

### Alterado

- Escape de HTML centralizado para garantir saída consistente e segura entre os geradores.
- Alinhamento de `requires-python` e documentação para a versão mínima de Python suportada (3.12).

### Corrigido

- Cálculo da mediana nas estatísticas.

[Não lançado]: https://github.com/
[5.3]: https://github.com/
[5.2]: https://github.com/
