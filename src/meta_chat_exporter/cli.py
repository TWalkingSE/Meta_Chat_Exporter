"""
Meta Platforms Chat Exporter - Interface de Linha de Comando (CLI)
Alternativa ao GUI para automação e uso em scripts
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from meta_chat_exporter.consolidation import consolidate_threads
from meta_chat_exporter.exporters import CSVExporter, JSONExporter
from meta_chat_exporter.generators_all import AllChatsHTMLGenerator
from meta_chat_exporter.generators_single import ChatHTMLGenerator
from meta_chat_exporter.manifest import discover_source_htmls
from meta_chat_exporter.parser import MetaRecordsParser
from meta_chat_exporter.redaction import RedactionEngine
from meta_chat_exporter.stats import ChatStatistics

logger = logging.getLogger(__name__)


def process_folder(folder: Path, log_callback=None) -> tuple:
    """Processa todos os HTMLs de uma pasta e retorna (threads, owner_username, owner_id)"""
    html_files = discover_source_htmls(folder)

    if not html_files:
        print(f"❌ Nenhum arquivo HTML encontrado em: {folder}")
        return [], "", ""

    print(f"📂 Encontrados {len(html_files)} arquivo(s) HTML")

    all_threads = []
    owner_username = ""
    owner_id = ""

    for i, html_file in enumerate(html_files):
        print(f"  📖 [{i+1}/{len(html_files)}] Processando: {html_file.name}")

        try:
            parser = MetaRecordsParser(str(html_file), log_callback)
            threads = parser.parse()
            all_threads.extend(threads)

            if parser.owner_username:
                owner_username = parser.owner_username
            if parser.owner_id:
                owner_id = parser.owner_id

            print(f"     ✅ {len(threads)} conversas encontradas")
        except Exception as e:
            print(f"     ❌ Erro: {e}")

    print(f"\n🔄 Consolidando {len(all_threads)} threads...")
    threads = consolidate_threads(all_threads)
    threads.sort(
        key=lambda t: (t.messages[-1].sent or datetime.min) if t.messages else datetime.min,
        reverse=True,
    )

    total_msgs = sum(len(t.messages) for t in threads)
    print(f"✅ {len(threads)} conversas únicas, {total_msgs:,} mensagens total")

    return threads, owner_username, owner_id


def cmd_export_html(args) -> int:
    """Exporta conversas para HTML"""
    folder = Path(args.pasta)
    if not folder.exists():
        print(f"❌ Pasta não encontrada: {folder}")
        return 1

    threads, owner, owner_id = process_folder(folder)
    if not threads:
        return 1

    # Carregar transcrições se fornecido
    transcriptions = {}
    if args.transcricoes:
        transcriptions = _load_transcriptions(args.transcricoes)

    # R4.1 — redação aplicada uma única vez na Data_Layer, antes de qualquer
    # gerador (individual ou unificado), garantindo consistência entre formatos.
    redact = getattr(args, "redact", False)
    if redact:
        print("\n🔒 Modo REDIGIDO ativo — nomes e números serão ocultados.")
        RedactionEngine(owner).redact(threads)

    start = time.time()
    from meta_chat_exporter.manifest import write_manifest_for_export

    source_files = discover_source_htmls(folder)
    output_files: list[Path] = []

    if args.individual:
        print("\n📤 Exportando conversas individuais...")
        for i, thread in enumerate(threads):
            gen = ChatHTMLGenerator(thread, owner, owner_id, transcriptions)

            participants = [p[0] for p in thread.participants if p[0] != owner]
            safe_name = "_".join(participants[:3]) if participants else thread.thread_id
            import re

            safe_name = re.sub(r'[<>:"/\\|?*]', "_", safe_name)
            suffix = "_redigido" if redact else ""
            filename = f"chat{suffix}_{safe_name}_{thread.thread_id[-8:]}.html"
            output_path = folder / filename

            gen.write_to_file(output_path)
            output_files.append(output_path)
            print(f"  ✅ [{i+1}/{len(threads)}] {filename}")
    else:
        print("\n📦 Gerando HTML unificado...")
        # Os threads já foram redigidos acima (quando aplicável); informamos ao
        # gerador via `already_redacted` para preservar o selo sem reaplicar.
        gen = AllChatsHTMLGenerator(
            threads,
            owner,
            owner_id,
            transcriptions,
            redact=redact,
            already_redacted=redact,
        )

        suffix = "_redigido" if redact else ""
        filename = f"todas_conversas{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = folder / filename

        gen.write_to_file(output_path)
        output_files.append(output_path)
        print(f"✅ Exportado: {output_path}")

    manifest_path = write_manifest_for_export(
        folder,
        source_files,
        output_files=output_files,
        stem="manifesto_html_redigido" if redact else "manifesto_html",
    )
    if manifest_path:
        print(f"🔏 Manifesto de custódia: {manifest_path.name}")

    elapsed = time.time() - start
    print(f"⏱️ Tempo: {elapsed:.2f}s")
    return 0


def cmd_export_json(args):
    """Exporta conversas para JSON"""
    folder = Path(args.pasta)
    if not folder.exists():
        print(f"❌ Pasta não encontrada: {folder}")
        return 1

    threads, owner, owner_id = process_folder(folder)
    if not threads:
        return 1

    # R4.1 — redação aplicada uma única vez na Data_Layer antes do exportador.
    redact = getattr(args, "redact", False)
    if redact:
        print("🔒 Modo REDIGIDO ativo — nomes e números serão ocultados.")
        RedactionEngine(owner).redact(threads)

    suffix = "_redigido" if redact else ""
    filename = args.output or f"conversas{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = folder / filename

    exporter = JSONExporter(threads, owner, owner_id)
    exporter.export(output_path, include_stats=args.estatisticas)

    from meta_chat_exporter.manifest import write_manifest_for_export

    mpath = write_manifest_for_export(
        folder,
        discover_source_htmls(folder),
        output_files=[output_path],
        stem="manifesto_json_redigido" if redact else "manifesto_json",
    )
    if mpath:
        print(f"🔏 Manifesto de custódia: {mpath.name}")

    print(f"✅ JSON exportado: {output_path}")
    return 0


def cmd_export_csv(args):
    """Exporta conversas para CSV"""
    folder = Path(args.pasta)
    if not folder.exists():
        print(f"❌ Pasta não encontrada: {folder}")
        return 1

    threads, owner, owner_id = process_folder(folder)
    if not threads:
        return 1

    # R4.1 — redação aplicada uma única vez na Data_Layer antes do exportador.
    redact = getattr(args, "redact", False)
    if redact:
        print("🔒 Modo REDIGIDO ativo — nomes e números serão ocultados.")
        RedactionEngine(owner).redact(threads)

    suffix = "_redigido" if redact else ""
    filename = args.output or f"conversas{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = folder / filename

    exporter = CSVExporter(threads, owner, owner_id)
    exporter.export(output_path)

    outputs = [output_path]
    if args.estatisticas:
        stats_path = output_path.with_name(output_path.stem + "_stats.csv")
        exporter.export_stats(stats_path)
        outputs.append(stats_path)
        print(f"✅ Estatísticas CSV: {stats_path}")

    from meta_chat_exporter.manifest import write_manifest_for_export

    mpath = write_manifest_for_export(
        folder,
        discover_source_htmls(folder),
        output_files=outputs,
        stem="manifesto_csv_redigido" if redact else "manifesto_csv",
    )
    if mpath:
        print(f"🔏 Manifesto de custódia: {mpath.name}")

    print(f"✅ CSV exportado: {output_path}")
    return 0


def cmd_stats(args):
    """Mostra estatísticas das conversas"""
    folder = Path(args.pasta)
    if not folder.exists():
        print(f"❌ Pasta não encontrada: {folder}")
        return 1

    threads, owner, owner_id = process_folder(folder)
    if not threads:
        return 1

    # R4.1/R4.5 — quando redigido, a Data_Layer é redigida uma única vez antes
    # de calcular as estatísticas, de modo que o relatório não exponha nomes
    # de usuários nem números longos originais.
    redact = getattr(args, "redact", False)
    if redact:
        print("🔒 Modo REDIGIDO ativo — nomes e números serão ocultados.")
        RedactionEngine(owner).redact(threads)

    stats = ChatStatistics(threads, owner, owner_id, base_dir=folder)
    all_stats = stats.generate_all()

    resumo = all_stats["resumo"]
    print("\n" + "=" * 60)
    print("📊 ESTATÍSTICAS DAS CONVERSAS")
    print("=" * 60)

    print("\n📋 Resumo Geral:")
    print(f"   Total de mensagens:   {resumo['total_mensagens']:,}")
    print(f"   Total de conversas:   {resumo['total_conversas']}")
    print(f"     ├─ DMs:             {resumo['total_dms']} ({resumo['msgs_dms']:,} msgs)")
    print(f"     └─ Grupos:          {resumo['total_grupos']} ({resumo['msgs_grupos']:,} msgs)")
    print(f"   Total participantes:  {resumo['total_participantes']}")
    print(f"   Total de anexos:      {resumo['total_anexos']}")
    print(f"   Chamadas:             {resumo['total_chamadas']}")
    print(f"   Msgs temporárias:     {resumo['total_temporarias']}")
    print(f"   Msgs removidas:       {resumo['total_removidas']}")
    print(f"   Período:              {resumo['primeira_mensagem']} → {resumo['ultima_mensagem']}")
    print(f"   Duração:              {resumo['periodo_dias']} dias")
    print(f"   Média msgs/dia:       {resumo['media_mensagens_dia']}")

    print("\n👥 Top Participantes:")
    for p in all_stats["por_participante"][:10]:
        bar_len = int((p["mensagens"] / all_stats["por_participante"][0]["mensagens"]) * 30)
        bar = "█" * bar_len
        print(f"   {p['nome'][:20]:<20} {bar} {p['mensagens']:,}")

    print("\n📷 Mídias:")
    midias = all_stats["midias"]
    print(
        f"   Fotos: {midias['fotos']}  |  Vídeos: {midias['videos']}  |  Áudios: {midias['audios']}  |  Outros: {midias['outros']}"
    )

    print("\n📞 Chamadas:")
    chamadas = all_stats["chamadas"]
    print(
        f"   Total: {chamadas['total']}  |  Atendidas: {chamadas['atendidas']}  |  Perdidas: {chamadas['perdidas']}"
    )
    print(f"   Duração total: {chamadas['duracao_total_formatada']}")

    horarios = all_stats["horarios"]
    print("\n⏰ Horários:")
    print(f"   Hora mais ativa: {horarios['hora_mais_ativa']}")
    periodos = horarios["periodos"]
    print(
        f"   Madrugada: {periodos['madrugada']}  |  Manhã: {periodos['manha']}  |  Tarde: {periodos['tarde']}  |  Noite: {periodos['noite']}"
    )

    temporal = all_stats["temporal"]
    print(f"   Dia mais ativo: {temporal['dia_mais_ativo']}")

    print("\n💬 Top 10 Palavras:")
    for w in all_stats["palavras"]["top_50"][:10]:
        print(f"   {w['palavra']:<15} {w['contagem']:,}x")

    print("\n🏆 Top Conversas:")
    for i, c in enumerate(all_stats["top_conversas"]):
        print(f"   #{i+1} {c['nome'][:30]:<30} {c['mensagens']:,} msgs")

    # Famílias adicionais para paridade com o relatório completo (R23)
    _print_heatmap(all_stats.get("heatmap"))
    _print_emojis(all_stats.get("emojis"))
    _print_tempo_resposta(all_stats.get("tempo_resposta"))
    _print_gaps(all_stats.get("gaps"))
    _print_idiomas(all_stats.get("idiomas"))
    _print_comparacao_periodos(all_stats.get("comparacao_periodos"))

    print("\n" + "=" * 60)
    return 0


# Nomes dos dias da semana (weekday(): 0 = segunda-feira)
_DIAS_SEMANA = (
    "Segunda",
    "Terça",
    "Quarta",
    "Quinta",
    "Sexta",
    "Sábado",
    "Domingo",
)


def _print_heatmap(heatmap) -> None:
    """Imprime um resumo textual do heatmap dia×hora de atividade."""
    print("\n🗓️ Heatmap de Atividade:")
    # heatmap é uma matriz 7×24 (dia da semana × hora)
    total = sum(sum(linha) for linha in heatmap) if heatmap else 0
    if not heatmap or total == 0:
        print("   sem dados")
        return

    # Dia e hora mais ativos
    por_dia = [sum(linha) for linha in heatmap]
    por_hora = [sum(heatmap[d][h] for d in range(len(heatmap))) for h in range(24)]
    dia_idx = max(range(len(por_dia)), key=lambda i: por_dia[i])
    hora_idx = max(range(24), key=lambda h: por_hora[h])

    print(f"   Dia mais ativo:  {_DIAS_SEMANA[dia_idx]} ({por_dia[dia_idx]:,} msgs)")
    print(f"   Hora mais ativa: {hora_idx:02d}:00 ({por_hora[hora_idx]:,} msgs)")

    # Grade textual compacta: uma linha por dia com barra proporcional
    maximo = max(por_dia)
    print("   Distribuição por dia:")
    for d, nome in enumerate(_DIAS_SEMANA):
        bar_len = int((por_dia[d] / maximo) * 20) if maximo else 0
        bar = "█" * bar_len
        print(f"     {nome:<8} {bar} {por_dia[d]:,}")


def _print_emojis(emojis) -> None:
    """Imprime os emojis mais usados."""
    print("\n😀 Emojis:")
    top = emojis.get("top_30") if emojis else None
    if not top:
        print("   sem dados")
        return

    print(
        f"   Total: {emojis['total_emojis']:,}  |  Únicos: {emojis['emojis_unicos']}"
        f"  |  Msgs com emoji: {emojis['msgs_com_emoji']:,}"
    )
    linha = "  ".join(f"{item['emoji']} {item['contagem']:,}" for item in top[:10])
    print(f"   Top 10: {linha}")


def _print_tempo_resposta(tempo_resposta) -> None:
    """Imprime o tempo de resposta por participante."""
    print("\n⏱️ Tempo de Resposta:")
    if not tempo_resposta:
        print("   sem dados")
        return

    for t in tempo_resposta[:10]:
        print(
            f"   {t['nome'][:20]:<20} média {t['media_formatada']}"
            f"  |  mediana {t['mediana_formatada']}"
            f"  |  {t['total_respostas']:,} respostas"
        )


def _print_gaps(gaps) -> None:
    """Imprime os períodos de inatividade (gaps) detectados."""
    print("\n🕳️ Gaps de Inatividade:")
    lista = gaps.get("gaps") if gaps else None
    if not lista:
        print("   sem dados")
        return

    print(
        f"   Total de gaps: {gaps['total_gaps']}"
        f"  |  Conversas afetadas: {gaps['conversas_com_gaps']}"
        f"  (limiar: {gaps['min_dias']} dias)"
    )
    maior = gaps.get("maior_gap")
    if maior:
        print(f"   Maior gap: {maior['dias']} dias em '{maior['conversa'][:30]}'")
    for g in lista[:10]:
        print(f"     {g['conversa'][:30]:<30} {g['dias']} dias")


def _print_idiomas(idiomas) -> None:
    """Imprime os idiomas detectados."""
    print("\n🌐 Idiomas:")
    percentuais = idiomas.get("percentuais") if idiomas else None
    if not idiomas or not percentuais:
        print("   sem dados")
        return

    print(
        f"   Principal: {idiomas.get('principal', 'Indeterminado')} (método: {idiomas['metodo']})"
    )
    for lang, pct in list(percentuais.items())[:10]:
        print(f"     {str(lang)[:20]:<20} {pct}%")


def _print_comparacao_periodos(comparacao) -> None:
    """Imprime a comparação entre a primeira e a segunda metade do período."""
    print("\n📈 Comparação de Períodos:")
    if not comparacao or not comparacao.get("ativo"):
        print("   sem dados")
        return

    p1, p2 = comparacao["p1"], comparacao["p2"]
    var = comparacao["variacoes"]
    print(f"   Período 1: {comparacao['p1_de']} → {comparacao['p1_ate']}")
    print(f"   Período 2: {comparacao['p2_de']} → {comparacao['p2_ate']}")
    print(f"   {'Métrica':<12} {'Período 1':>12} {'Período 2':>12} {'Variação':>10}")
    print(f"   {'Mensagens':<12} {p1['msgs']:>12,} {p2['msgs']:>12,} {var['msgs']:>10}")
    print(f"   {'Anexos':<12} {p1['anexos']:>12,} {p2['anexos']:>12,} {var['anexos']:>10}")
    print(f"   {'Chamadas':<12} {p1['chamadas']:>12,} {p2['chamadas']:>12,} {var['chamadas']:>10}")
    print(f"   {'Autores':<12} {p1['autores']:>12,} {p2['autores']:>12,} {var['autores']:>10}")
    print(
        f"   {'Tam. médio':<12} {p1['media_len']:>12} {p2['media_len']:>12} {var['media_len']:>10}"
    )


def _load_transcriptions(file_path: str) -> dict:
    """Carrega arquivo de transcrições"""
    transcriptions = {}
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    content = None
    for enc in encodings:
        try:
            with open(file_path, encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
        except OSError as e:
            print(f"⚠️ Não foi possível abrir o arquivo de transcrições: {e}")
            return {}

    if content is None:
        print(f"⚠️ Não foi possível ler o arquivo de transcrições: {file_path}")
        return {}

    blocks = content.split("Nome:")
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        if not lines:
            continue

        filename = lines[0].strip()
        transcription = ""
        for i, line in enumerate(lines):
            if line.startswith("HASH:"):
                hash_line = line.replace("HASH:", "").strip()
                if len(hash_line) > 33:
                    text_part = hash_line[32:].strip()
                    if text_part:
                        transcription = text_part
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith(("Nome:", "Caminho:", "HASH:")):
                        transcription = (transcription + " " + next_line).strip()
                break

        if filename and transcription:
            transcriptions[filename.lower()] = transcription.strip()
            name_no_ext = filename.rsplit(".", 1)[0].lower()
            transcriptions[name_no_ext] = transcription.strip()

    print(f"📝 {len(transcriptions) // 2} transcrições carregadas")
    return transcriptions


def main():
    """Ponto de entrada da CLI"""
    parser = argparse.ArgumentParser(
        prog="chat_exporter",
        description="Meta Platforms Chat Exporter - Exporta conversas da Meta para formatos visualizáveis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  chat-exporter html ./minha_pasta                    # Exporta HTML unificado
  chat-exporter html ./minha_pasta --individual       # Exporta HTMLs individuais
  chat-exporter json ./minha_pasta                    # Exporta para JSON
  chat-exporter csv ./minha_pasta --estatisticas      # Exporta CSV + estatísticas
  chat-exporter stats ./minha_pasta                   # Mostra estatísticas no terminal
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verboso (DEBUG logging)")

    subparsers = parser.add_subparsers(dest="comando", help="Comando a executar")

    # HTML
    html_parser = subparsers.add_parser("html", help="Exportar para HTML")
    html_parser.add_argument("pasta", help="Pasta com arquivos HTML da Meta")
    html_parser.add_argument(
        "--individual",
        action="store_true",
        help="Exportar conversas individuais em vez de unificado",
    )
    html_parser.add_argument("--transcricoes", "-t", help="Arquivo de transcrições (opcional)")
    html_parser.add_argument(
        "--redact",
        "-r",
        action="store_true",
        help="Redação: ocultar nomes e números sensíveis no HTML",
    )
    html_parser.set_defaults(func=cmd_export_html)

    # JSON
    json_parser = subparsers.add_parser("json", help="Exportar para JSON")
    json_parser.add_argument("pasta", help="Pasta com arquivos HTML da Meta")
    json_parser.add_argument("--output", "-o", help="Nome do arquivo de saída")
    json_parser.add_argument(
        "--estatisticas", "-e", action="store_true", help="Incluir estatísticas no JSON"
    )
    json_parser.add_argument(
        "--redact",
        "-r",
        action="store_true",
        help="Redação: ocultar nomes e números sensíveis na exportação",
    )
    json_parser.set_defaults(func=cmd_export_json)

    # CSV
    csv_parser = subparsers.add_parser("csv", help="Exportar para CSV")
    csv_parser.add_argument("pasta", help="Pasta com arquivos HTML da Meta")
    csv_parser.add_argument("--output", "-o", help="Nome do arquivo de saída")
    csv_parser.add_argument(
        "--estatisticas",
        "-e",
        action="store_true",
        help="Exportar arquivo de estatísticas separado",
    )
    csv_parser.add_argument(
        "--redact",
        "-r",
        action="store_true",
        help="Redação: ocultar nomes e números sensíveis na exportação",
    )
    csv_parser.set_defaults(func=cmd_export_csv)

    # Stats
    stats_parser = subparsers.add_parser("stats", help="Mostrar estatísticas")
    stats_parser.add_argument("pasta", help="Pasta com arquivos HTML da Meta")
    stats_parser.add_argument(
        "--redact",
        "-r",
        action="store_true",
        help="Redação: ocultar nomes e números sensíveis nas estatísticas",
    )
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()

    # Configurar logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="[%(name)s] %(levelname)s: %(message)s")

    if not args.comando:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
