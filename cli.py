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
from typing import List

from constants import TIMEZONE_OFFSET
from models import Thread
from parser import MetaRecordsParser
from consolidation import consolidate_threads, get_message_signature
from generators_single import ChatHTMLGenerator
from generators_all import AllChatsHTMLGenerator
from stats import ChatStatistics
from exporters import JSONExporter, CSVExporter

logger = logging.getLogger(__name__)


def process_folder(folder: Path, log_callback=None) -> tuple:
    """Processa todos os HTMLs de uma pasta e retorna (threads, owner_username, owner_id)"""
    html_files = list(folder.glob("*.html"))
    html_files = [f for f in html_files if not f.name.startswith("chat_")
                  and not f.name.startswith("todas_conversas_")]

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
        reverse=True
    )

    total_msgs = sum(len(t.messages) for t in threads)
    print(f"✅ {len(threads)} conversas únicas, {total_msgs:,} mensagens total")

    return threads, owner_username, owner_id


def cmd_export_html(args):
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

    start = time.time()

    if args.individual:
        print("\n📤 Exportando conversas individuais...")
        for i, thread in enumerate(threads):
            gen = ChatHTMLGenerator(thread, owner, owner_id, transcriptions)

            participants = [p[0] for p in thread.participants if p[0] != owner]
            safe_name = "_".join(participants[:3]) if participants else thread.thread_id
            import re
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
            filename = f"chat_{safe_name}_{thread.thread_id[-8:]}.html"
            output_path = folder / filename

            gen.write_to_file(output_path)
            print(f"  ✅ [{i+1}/{len(threads)}] {filename}")
    else:
        redact = getattr(args, 'redact', False)
        if redact:
            print("\n� Modo REDIGIDO ativo — nomes e números serão ocultados.")
        print("\n�📦 Gerando HTML unificado...")
        gen = AllChatsHTMLGenerator(threads, owner, owner_id, transcriptions, redact=redact)

        suffix = "_redigido" if redact else ""
        filename = f"todas_conversas{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = folder / filename

        gen.write_to_file(output_path)
        print(f"✅ Exportado: {output_path}")

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

    filename = args.output or f"conversas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = folder / filename

    exporter = JSONExporter(threads, owner, owner_id)
    exporter.export(output_path, include_stats=args.estatisticas)

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

    filename = args.output or f"conversas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = folder / filename

    exporter = CSVExporter(threads, owner, owner_id)
    exporter.export(output_path)

    if args.estatisticas:
        stats_path = output_path.with_name(output_path.stem + "_stats.csv")
        exporter.export_stats(stats_path)
        print(f"✅ Estatísticas CSV: {stats_path}")

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

    stats = ChatStatistics(threads, owner, owner_id, base_dir=folder)
    all_stats = stats.generate_all()

    resumo = all_stats["resumo"]
    print("\n" + "=" * 60)
    print("📊 ESTATÍSTICAS DAS CONVERSAS")
    print("=" * 60)

    print(f"\n📋 Resumo Geral:")
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

    print(f"\n👥 Top Participantes:")
    for p in all_stats["por_participante"][:10]:
        bar_len = int((p["mensagens"] / all_stats["por_participante"][0]["mensagens"]) * 30)
        bar = "█" * bar_len
        print(f"   {p['nome'][:20]:<20} {bar} {p['mensagens']:,}")

    print(f"\n📷 Mídias:")
    midias = all_stats["midias"]
    print(f"   Fotos: {midias['fotos']}  |  Vídeos: {midias['videos']}  |  Áudios: {midias['audios']}  |  Outros: {midias['outros']}")

    print(f"\n📞 Chamadas:")
    chamadas = all_stats["chamadas"]
    print(f"   Total: {chamadas['total']}  |  Atendidas: {chamadas['atendidas']}  |  Perdidas: {chamadas['perdidas']}")
    print(f"   Duração total: {chamadas['duracao_total_formatada']}")

    horarios = all_stats["horarios"]
    print(f"\n⏰ Horários:")
    print(f"   Hora mais ativa: {horarios['hora_mais_ativa']}")
    periodos = horarios["periodos"]
    print(f"   Madrugada: {periodos['madrugada']}  |  Manhã: {periodos['manha']}  |  Tarde: {periodos['tarde']}  |  Noite: {periodos['noite']}")

    temporal = all_stats["temporal"]
    print(f"   Dia mais ativo: {temporal['dia_mais_ativo']}")

    print(f"\n💬 Top 10 Palavras:")
    for w in all_stats["palavras"]["top_50"][:10]:
        print(f"   {w['palavra']:<15} {w['contagem']:,}x")

    print(f"\n🏆 Top Conversas:")
    for i, c in enumerate(all_stats["top_conversas"]):
        print(f"   #{i+1} {c['nome'][:30]:<30} {c['mensagens']:,} msgs")

    print("\n" + "=" * 60)
    return 0


def _load_transcriptions(file_path: str) -> dict:
    """Carrega arquivo de transcrições"""
    transcriptions = {}
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

    content = None
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        print(f"⚠️ Não foi possível ler o arquivo de transcrições: {file_path}")
        return {}

    blocks = content.split("Nome:")
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split('\n')
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
            name_no_ext = filename.rsplit('.', 1)[0].lower()
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
  python cli.py html ./minha_pasta                    # Exporta HTML unificado
  python cli.py html ./minha_pasta --individual       # Exporta HTMLs individuais
  python cli.py json ./minha_pasta                    # Exporta para JSON
  python cli.py csv ./minha_pasta --estatisticas      # Exporta CSV + estatísticas
  python cli.py stats ./minha_pasta                   # Mostra estatísticas no terminal
        """
    )

    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Modo verboso (DEBUG logging)'
    )

    subparsers = parser.add_subparsers(dest='comando', help='Comando a executar')

    # HTML
    html_parser = subparsers.add_parser('html', help='Exportar para HTML')
    html_parser.add_argument('pasta', help='Pasta com arquivos HTML da Meta')
    html_parser.add_argument('--individual', action='store_true',
                             help='Exportar conversas individuais em vez de unificado')
    html_parser.add_argument('--transcricoes', '-t', help='Arquivo de transcrições (opcional)')
    html_parser.add_argument('--redact', '-r', action='store_true',
                             help='Redação: ocultar nomes e números sensíveis no HTML')
    html_parser.set_defaults(func=cmd_export_html)

    # JSON
    json_parser = subparsers.add_parser('json', help='Exportar para JSON')
    json_parser.add_argument('pasta', help='Pasta com arquivos HTML da Meta')
    json_parser.add_argument('--output', '-o', help='Nome do arquivo de saída')
    json_parser.add_argument('--estatisticas', '-e', action='store_true',
                             help='Incluir estatísticas no JSON')
    json_parser.set_defaults(func=cmd_export_json)

    # CSV
    csv_parser = subparsers.add_parser('csv', help='Exportar para CSV')
    csv_parser.add_argument('pasta', help='Pasta com arquivos HTML da Meta')
    csv_parser.add_argument('--output', '-o', help='Nome do arquivo de saída')
    csv_parser.add_argument('--estatisticas', '-e', action='store_true',
                             help='Exportar arquivo de estatísticas separado')
    csv_parser.set_defaults(func=cmd_export_csv)

    # Stats
    stats_parser = subparsers.add_parser('stats', help='Mostrar estatísticas')
    stats_parser.add_argument('pasta', help='Pasta com arquivos HTML da Meta')
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()

    # Configurar logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='[%(name)s] %(levelname)s: %(message)s'
    )

    if not args.comando:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
