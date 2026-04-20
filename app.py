"""
Meta Platforms Chat Exporter - Aplicação GUI
Interface moderna com PyQt6 para exportação de conversas
"""

import re
import logging
import traceback
import time
import threading
import webbrowser
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QScrollArea, QProgressBar,
    QGridLayout, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox,
    QDialog, QSizePolicy, QSpacerItem,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

import constants
from models import Attachment, Message, Thread, ProfileMedia
from parser import MetaRecordsParser
from consolidation import consolidate_threads, get_message_signature
from safe_cache import save_cache, load_cache
from config import config
from generators_single import ChatHTMLGenerator
from generators_all import AllChatsHTMLGenerator
from widgets import GradientProgressBar
from exporters import JSONExporter, CSVExporter
from stats import ChatStatistics
from media_parser import MediaParser
from generic_parser import GenericCategoryParser
from transcriber import (
    check_whisper_available, detect_gpu, scan_audio_files,
    AudioTranscriber, WHISPER_MODELS, format_gpu_info,
    AUDIO_EXTENSIONS,
)

logger = logging.getLogger(__name__)


# ============================================================
# Helper: thread-safe bridge para atualizar UI de qualquer thread
# ============================================================
class _SignalBridge(QObject):
    _sig = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._sig.connect(self._run)

    def _run(self, fn):
        fn()

    def invoke(self, fn):
        """Agenda *fn* para rodar na thread principal (thread-safe)."""
        self._sig.emit(fn)


# ============================================================
# QSS (stylesheet) global para tema escuro
# ============================================================
DARK_STYLE = """
QMainWindow, QWidget#central {
    background-color: #0a0a0a;
}
QWidget#central QLabel,
QFrame#header QLabel,
QFrame#footer QLabel,
QFrame#logFrame QLabel,
QFrame#logInner QLabel,
QFrame#searchFrame QLabel,
QFrame#threadCard QLabel {
    color: #ffffff;
}
QMessageBox QLabel {
    color: #000000;
}
QMessageBox QPushButton {
    color: #000000;
    background-color: #f0f0f0;
    border: 1px solid #aaaaaa;
    border-radius: 4px;
    padding: 5px 16px;
    font-weight: normal;
    min-width: 70px;
}
QMessageBox QPushButton:hover {
    background-color: #e0e0e0;
}
QMessageBox QPushButton:pressed {
    background-color: #d0d0d0;
}
QFrame#header {
    background-color: #1a1a1a;
}
QFrame#footer {
    background-color: #1a1a1a;
}
QFrame#logFrame {
    background-color: #1a1a1a;
    border-radius: 15px;
}
QFrame#logInner {
    background-color: #0a0a0a;
    border-radius: 10px;
}
QFrame#threadCard {
    background-color: #1a1a1a;
    border-radius: 12px;
}
QFrame#searchFrame {
    background-color: #1a1a1a;
    border-radius: 10px;
}
QPushButton {
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 10px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #4a4a4a;
}
QPushButton:disabled {
    color: #777777;
    background-color: #2a2a2a;
    border-color: #3a3a3a;
}
QPushButton#btnSelect {
    background-color: #555555;
    border-color: #888888;
}
QPushButton#btnSelect:hover {
    background-color: #666666;
}
QPushButton#btnExportAll {
    background-color: #4a4a4a;
    border-color: #707070;
}
QPushButton#btnExportAll:hover {
    background-color: #5a5a5a;
}
QPushButton#btnJson {
    background-color: #3a5a3a;
    border-color: #5a8a5a;
}
QPushButton#btnJson:hover {
    background-color: #4a6a4a;
}
QPushButton#btnCsv {
    background-color: #3a3a5a;
    border-color: #5a5a8a;
}
QPushButton#btnCsv:hover {
    background-color: #4a4a6a;
}
QPushButton#btnSmall {
    background-color: #3a3a3a;
    border-color: #555555;
    border-radius: 8px;
    font-weight: normal;
    padding: 4px 10px;
}
QPushButton#btnSmall:hover {
    background-color: #4a4a4a;
}
QPushButton#btnClearLog {
    background-color: #0a0a0a;
    border-color: #1a7a7a;
    border-radius: 8px;
    font-weight: normal;
}
QPushButton#btnClearLog:hover {
    background-color: #252525;
}
QPushButton#btnSearch {
    background-color: #505050;
    border-color: #686868;
    border-radius: 8px;
}
QPushButton#btnSearch:hover {
    background-color: #686868;
}
QPushButton#btnClearSearch {
    background-color: #5a3a3a;
    border-radius: 8px;
}
QPushButton#btnClearSearch:hover {
    background-color: #6a4a4a;
}
QPushButton#btnExport {
    background-color: #505050;
    border-color: #686868;
    border-radius: 8px;
}
QPushButton#btnExport:hover {
    background-color: #686868;
}
QPushButton#btnAccent {
    background-color: #505050;
    border-color: #686868;
    border-radius: 10px;
}
QPushButton#btnAccent:hover {
    background-color: #686868;
}
QPushButton#btnCancel {
    background-color: #555555;
    border-radius: 10px;
}
QPushButton#btnCancel:hover {
    background-color: #666666;
}
QPushButton#btnLoadMore {
    background-color: #505050;
    border-color: #686868;
    border-radius: 10px;
}
QPushButton#btnLoadMore:hover {
    background-color: #686868;
}
QLineEdit {
    background-color: #0a0a0a;
    color: #ffffff;
    border: 1px solid #505050;
    border-radius: 8px;
    padding: 6px 10px;
}
QLineEdit:focus {
    border-color: #686868;
}
QComboBox {
    background-color: #2a2a2a;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 8px;
    padding: 4px 8px;
}
QComboBox::drop-down {
    background-color: #444444;
    border-radius: 4px;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #2a2a2a;
    color: #ffffff;
    selection-background-color: #505050;
    border: 1px solid #555555;
}
QScrollArea {
    border: none;
    background-color: #252525;
    border-radius: 15px;
}
QScrollBar:vertical {
    background: #1a1a1a;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #505050;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #686868;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QCheckBox {
    color: #c0c0c0;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #505050;
    border-radius: 5px;
    background: #1a1a1a;
}
QCheckBox::indicator:checked {
    background: #505050;
}
QProgressBar {
    background-color: #1a1a1a;
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #505050;
    border-radius: 6px;
}
"""


class ChatExporterApp(QMainWindow):
    """Aplicação principal com interface moderna"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Meta Chat Exporter")
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)

        # Centralizar janela
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - 1100) // 2 + geo.x()
            y = (geo.height() - 700) // 2 + geo.y()
            self.move(x, y)

        self.threads: List[Thread] = []
        self.profile_media = ProfileMedia()
        self.owner_username = ""
        self.owner_id = ""
        self.base_dir = None
        self.log_row = 0
        self.filtered_threads = None

        # Aplicar configuração persistente
        constants.set_timezone_offset(timedelta(hours=config.timezone_offset_hours))

        # Bridge para atualizações thread-safe
        self._bridge = _SignalBridge()

        # Variável para armazenar transcrições (populada pelo Whisper)
        self.transcriptions = {}
        self._transcriber: AudioTranscriber | None = None

        self._setup_ui()

        # Mostrar mensagem inicial
        QTimer.singleShot(100, self._show_startup_message)

    # ------------------------------------------------------------------
    # Cores
    # ------------------------------------------------------------------
    colors = {
        "bg_dark": "#0a0a0a",
        "bg_medium": "#1a1a1a",
        "bg_light": "#252525",
        "accent": "#505050",
        "accent2": "#686868",
        "btn_primary": "#3a3a3a",
        "btn_secondary": "#4a4a4a",
        "text": "#ffffff",
        "text_dim": "#c0c0c0",
        "success": "#00d26a",
        "warning": "#ffc107",
    }

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        """Configura interface"""
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        main_grid = QGridLayout(central)
        main_grid.setContentsMargins(0, 0, 0, 0)
        main_grid.setSpacing(0)
        main_grid.setColumnStretch(0, 3)
        main_grid.setColumnMinimumWidth(1, 380)
        main_grid.setColumnStretch(1, 1)
        main_grid.setRowStretch(1, 1)

        # ===== HEADER =====
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(70)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(25, 10, 25, 10)

        # Logo
        title = QLabel("📂 Meta Chat Exporter")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.colors['accent']};")
        header_layout.addWidget(title)

        subtitle = QLabel("  v5.2")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet(f"color: {self.colors['text_dim']};")
        header_layout.addWidget(subtitle)

        header_layout.addStretch()

        # Seletor de fuso horário
        tz_label = QLabel("🌐")
        tz_label.setFont(QFont("Segoe UI", 12))
        tz_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        header_layout.addWidget(tz_label)

        self.tz_combo = QComboBox()
        self.tz_combo.addItems([f"UTC{h:+d}" for h in range(-12, 13)])
        self.tz_combo.setCurrentText("UTC-3")
        self.tz_combo.setFixedSize(85, 28)
        self.tz_combo.setFont(QFont("Segoe UI", 9))
        self.tz_combo.currentTextChanged.connect(self._on_timezone_change)
        header_layout.addWidget(tz_label)
        header_layout.addWidget(self.tz_combo)

        header_layout.addSpacing(8)

        # Botões do header (ordem inversa para alinhar à direita)
        self.btn_inject = QPushButton("📝 Injetar Transcrições")
        self.btn_inject.setObjectName("btnSmall")
        self.btn_inject.setFont(QFont("Segoe UI", 9))
        self.btn_inject.setFixedSize(165, 30)
        self.btn_inject.clicked.connect(self._inject_transcriptions_dialog)
        header_layout.addWidget(self.btn_inject)

        self.btn_whisper = QPushButton("🎙️ Transcrever Áudios")
        self.btn_whisper.setObjectName("btnSmall")
        self.btn_whisper.setFont(QFont("Segoe UI", 9))
        self.btn_whisper.setFixedSize(155, 30)
        self.btn_whisper.clicked.connect(self._open_transcription_dialog)
        header_layout.addWidget(self.btn_whisper)

        header_layout.addSpacing(5)

        self.btn_select = QPushButton("📂 Selecionar Pasta")
        self.btn_select.setObjectName("btnSelect")
        self.btn_select.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_select.setFixedSize(185, 40)
        self.btn_select.clicked.connect(self._select_folder)
        header_layout.addWidget(self.btn_select)

        self.btn_clear = QPushButton("🗑️ Limpar")
        self.btn_clear.setObjectName("btnSmall")
        self.btn_clear.setFont(QFont("Segoe UI", 9))
        self.btn_clear.setFixedSize(90, 30)
        self.btn_clear.setEnabled(False)
        self.btn_clear.clicked.connect(self._clear_conversations)
        header_layout.addWidget(self.btn_clear)

        self.btn_export_csv = QPushButton("📊 CSV")
        self.btn_export_csv.setObjectName("btnCsv")
        self.btn_export_csv.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_export_csv.setFixedSize(80, 40)
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self._export_csv)
        header_layout.addWidget(self.btn_export_csv)

        self.btn_export_json = QPushButton("📄 JSON")
        self.btn_export_json.setObjectName("btnJson")
        self.btn_export_json.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_export_json.setFixedSize(80, 40)
        self.btn_export_json.setEnabled(False)
        self.btn_export_json.clicked.connect(self._export_json)
        header_layout.addWidget(self.btn_export_json)

        self.btn_export_all = QPushButton("📦 Exportar HTML")
        self.btn_export_all.setObjectName("btnExportAll")
        self.btn_export_all.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_export_all.setFixedSize(175, 40)
        self.btn_export_all.setEnabled(False)
        self.btn_export_all.clicked.connect(self._export_all)
        header_layout.addWidget(self.btn_export_all)

        # Phase 8.3: Checkbox de redação
        self.redact_mode = False
        self.chk_redact = QCheckBox("🔒 Redigir")
        self.chk_redact.setToolTip(
            "Ocultar nomes de usuários e números longos (IDs/telefones) no HTML exportado.\n"
            "Útil ao compartilhar relatórios preservando privacidade."
        )
        self.chk_redact.setStyleSheet("color: #ddd; font-size: 11px;")
        self.chk_redact.toggled.connect(lambda v: setattr(self, 'redact_mode', v))
        header_layout.addWidget(self.chk_redact)

        main_grid.addWidget(header, 0, 0, 1, 2)

        # ===== ÁREA PRINCIPAL (THREADS) =====
        main_frame = QWidget()
        main_frame.setStyleSheet("background-color: transparent;")
        main_frame_layout = QVBoxLayout(main_frame)
        main_frame_layout.setContentsMargins(20, 15, 10, 15)

        section_title = QLabel("💬 Conversas")
        section_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        main_frame_layout.addWidget(section_title)

        # ===== BARRA DE PESQUISA =====
        search_frame = QFrame()
        search_frame.setObjectName("searchFrame")
        search_layout = QGridLayout(search_frame)
        search_layout.setContentsMargins(10, 8, 10, 8)
        search_layout.setColumnStretch(1, 1)

        search_icon = QLabel("🔍")
        search_icon.setFont(QFont("Segoe UI", 14))
        search_layout.addWidget(search_icon, 0, 0)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Pesquisar (nome, participante, mensagem)...")
        self.search_entry.setFont(QFont("Segoe UI", 11))
        self.search_entry.setFixedHeight(35)
        self.search_entry.returnPressed.connect(self._filter_threads)
        search_layout.addWidget(self.search_entry, 0, 1)

        self.search_type = QComboBox()
        self.search_type.addItems(["Tudo", "Participante", "Mensagens", "Chamadas", "Links", "Mídias"])
        self.search_type.setFont(QFont("Segoe UI", 9))
        self.search_type.setFixedSize(120, 35)
        search_layout.addWidget(self.search_type, 0, 2)

        btn_search = QPushButton("Buscar")
        btn_search.setObjectName("btnSearch")
        btn_search.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_search.setFixedSize(80, 35)
        btn_search.clicked.connect(self._filter_threads)
        search_layout.addWidget(btn_search, 0, 3)

        btn_clear_search = QPushButton("✕")
        btn_clear_search.setObjectName("btnClearSearch")
        btn_clear_search.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        btn_clear_search.setFixedSize(40, 35)
        btn_clear_search.clicked.connect(self._clear_search)
        search_layout.addWidget(btn_clear_search, 0, 4)

        # Filtros de data
        date_filter = QWidget()
        date_layout = QHBoxLayout(date_filter)
        date_layout.setContentsMargins(0, 0, 0, 0)

        lbl_de = QLabel("📅 De:")
        lbl_de.setFont(QFont("Segoe UI", 9))
        lbl_de.setStyleSheet(f"color: {self.colors['text_dim']};")
        date_layout.addWidget(lbl_de)

        self.date_from_entry = QLineEdit()
        self.date_from_entry.setPlaceholderText("dd/mm/aaaa")
        self.date_from_entry.setFont(QFont("Segoe UI", 9))
        self.date_from_entry.setFixedSize(100, 28)
        date_layout.addWidget(self.date_from_entry)

        lbl_ate = QLabel("  Até:")
        lbl_ate.setFont(QFont("Segoe UI", 9))
        lbl_ate.setStyleSheet(f"color: {self.colors['text_dim']};")
        date_layout.addWidget(lbl_ate)

        self.date_to_entry = QLineEdit()
        self.date_to_entry.setPlaceholderText("dd/mm/aaaa")
        self.date_to_entry.setFont(QFont("Segoe UI", 9))
        self.date_to_entry.setFixedSize(100, 28)
        date_layout.addWidget(self.date_to_entry)

        date_layout.addStretch()

        self.search_results_label = QLabel("")
        self.search_results_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.search_results_label.setStyleSheet(f"color: {self.colors['success']};")
        date_layout.addWidget(self.search_results_label)

        search_layout.addWidget(date_filter, 1, 0, 1, 5)
        main_frame_layout.addWidget(search_frame)

        # ===== LISTA DE THREADS (scrollable) =====
        self.threads_scroll = QScrollArea()
        self.threads_scroll.setWidgetResizable(True)
        self.threads_scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {self.colors['bg_light']}; border-radius: 15px; }}"
        )
        self._threads_container = QWidget()
        self._threads_layout = QVBoxLayout(self._threads_container)
        self._threads_layout.setContentsMargins(5, 5, 5, 5)
        self._threads_layout.setSpacing(4)
        self._threads_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.threads_scroll.setWidget(self._threads_container)

        self.placeholder = QLabel(
            "📂 Nenhuma conversa carregada\n\n"
            "Clique em 'Selecionar Pasta' para carregar conversas\n"
            "de TODOS os arquivos HTML na pasta\n\n"
            "🔗 Threads de diferentes arquivos serão mesclados!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔒 SEGURANÇA DO HTML GERADO:\n\n"
            "✅ 100% Offline - funciona sem internet\n"
            "✅ CSS e JavaScript embutidos no arquivo\n"
            "✅ Não faz requisições externas\n"
            "✅ Pode ser aberto localmente no navegador"
        )
        self.placeholder.setFont(QFont("Segoe UI", 12))
        self.placeholder.setStyleSheet(f"color: {self.colors['text_dim']};")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._threads_layout.addWidget(self.placeholder)

        main_frame_layout.addWidget(self.threads_scroll, stretch=1)
        main_grid.addWidget(main_frame, 1, 0)

        # ===== PAINEL DE LOG LATERAL =====
        log_frame = QFrame()
        log_frame.setObjectName("logFrame")
        log_frame_layout = QVBoxLayout(log_frame)
        log_frame_layout.setContentsMargins(15, 15, 15, 10)

        log_title = QLabel("📋 Log de Progresso")
        log_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        log_title.setStyleSheet(f"color: {self.colors['accent']};")
        log_frame_layout.addWidget(log_title)

        self.offline_status_label = QLabel("🔒 HTML 100% Offline")
        self.offline_status_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.offline_status_label.setStyleSheet(f"color: {self.colors['success']};")
        log_frame_layout.addWidget(self.offline_status_label)

        # Log scroll
        self.log_scroll = QScrollArea()
        self.log_scroll.setWidgetResizable(True)
        log_inner = QFrame()
        log_inner.setObjectName("logInner")
        self._log_layout = QVBoxLayout(log_inner)
        self._log_layout.setContentsMargins(8, 8, 8, 8)
        self._log_layout.setSpacing(3)
        self._log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.log_scroll.setWidget(log_inner)
        log_frame_layout.addWidget(self.log_scroll, stretch=1)

        btn_clear_log = QPushButton("🗑️ Limpar Log")
        btn_clear_log.setObjectName("btnClearLog")
        btn_clear_log.setFont(QFont("Segoe UI", 9))
        btn_clear_log.setFixedHeight(30)
        btn_clear_log.clicked.connect(self._clear_log)
        log_frame_layout.addWidget(btn_clear_log, alignment=Qt.AlignmentFlag.AlignCenter)

        log_wrapper = QWidget()
        log_wrapper_layout = QVBoxLayout(log_wrapper)
        log_wrapper_layout.setContentsMargins(10, 15, 20, 15)
        log_wrapper_layout.addWidget(log_frame)
        main_grid.addWidget(log_wrapper, 1, 1)

        # ===== BARRA DE PROGRESSO (FOOTER) =====
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(70)
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(30, 10, 30, 10)

        progress_top = QHBoxLayout()
        self.status_label = QLabel("⏳ Pronto para processar")
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        progress_top.addWidget(self.status_label)
        progress_top.addStretch()

        self.percent_label = QLabel("0%")
        self.percent_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.percent_label.setStyleSheet(f"color: {self.colors['accent']};")
        progress_top.addWidget(self.percent_label)
        footer_layout.addLayout(progress_top)

        self.progress_bar = GradientProgressBar(width=1040, height=14)
        footer_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        main_grid.addWidget(footer, 2, 0, 1, 2)

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------
    def _add_log(self, message: str):
        """Adiciona mensagem ao log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        lbl = QLabel(f"[{timestamp}] {message}")
        lbl.setFont(QFont("Consolas", 10))
        lbl.setStyleSheet("color: #e0e0e0;")
        lbl.setWordWrap(True)
        self._log_layout.addWidget(lbl)
        self.log_row += 1
        # Auto-scroll
        QTimer.singleShot(50, lambda: self.log_scroll.verticalScrollBar().setValue(
            self.log_scroll.verticalScrollBar().maximum()
        ))

    def _clear_log(self):
        """Limpa o log"""
        while self._log_layout.count():
            item = self._log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.log_row = 0
        self._add_log("🗑️ Log limpo")

    def _log_callback(self, message: str):
        """Callback para log do parser (thread-safe)"""
        self._bridge.invoke(lambda: self._add_log(message))

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------
    def _show_startup_message(self):
        """Mostra mensagem inicial"""
        self._add_log("🚀 Aplicação iniciada")
        self._add_log("━" * 35)
        self._add_log("📂 MÚLTIPLOS ARQUIVOS HTML:")
        self._add_log("   • Lê TODOS os .html da pasta")
        self._add_log("   • Mescla threads de diferentes arquivos")
        self._add_log("   • Remove mensagens duplicadas")
        self._add_log("━" * 35)
        self._add_log("🔒 SEGURANÇA:")
        self._add_log("   • HTML 100% offline")
        self._add_log("   • Sem conexão com internet")
        self._add_log("   • CSS/JS embutidos no arquivo")
        self._add_log("   • Funciona sem servidor web")
        self._add_log("━" * 35)
        self._add_log("📂 Selecione uma pasta para processar")

        self.offline_status_label.setText("🔒 HTML 100% Offline | Seguro | Local")
        self.offline_status_label.setStyleSheet(f"color: {self.colors['success']};")
        self.status_label.setText("⏳ Selecione uma pasta com arquivos HTML")

    # ===== TRANSCRIÇÃO AUTOMÁTICA COM WHISPER =====

    def _open_transcription_dialog(self):
        """Abre diálogo de transcrição automática com Whisper."""
        available, msg = check_whisper_available()
        if not available:
            QMessageBox.warning(self, "Whisper não disponível", msg)
            return

        if not self.base_dir:
            QMessageBox.information(
                self, "Pasta não selecionada",
                "Selecione uma pasta com arquivos HTML primeiro.\n\n"
                "O sistema procurará áudios nas subpastas (ex: linked_media/)."
            )
            return

        gpu_info = detect_gpu()
        audio_folder = self.base_dir
        audio_files = scan_audio_files(audio_folder)
        if not audio_files:
            QMessageBox.information(
                self, "Nenhum áudio encontrado",
                f"Nenhum arquivo de áudio encontrado em:\n{audio_folder}\n\n"
                f"Extensões procuradas: {', '.join(sorted(AUDIO_EXTENSIONS))}"
            )
            return

        # Criar janela de diálogo
        dialog = QDialog(self)
        dialog.setWindowTitle("🎙️ Transcrição Automática de Áudios")
        dialog.setFixedSize(560, 620)
        dialog.setStyleSheet(f"QDialog {{ background-color: {self.colors['bg_medium']}; }}")

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setContentsMargins(25, 20, 25, 20)
        dlg_layout.setSpacing(10)

        # Título
        title_label = QLabel("🎙️ Transcrição Automática com Whisper")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {self.colors['accent']};")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dlg_layout.addWidget(title_label)

        sub_label = QLabel("Transcreve áudios localmente usando IA (opcional)")
        sub_label.setFont(QFont("Segoe UI", 10))
        sub_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dlg_layout.addWidget(sub_label)

        # GPU info
        gpu_frame = QFrame()
        gpu_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border-radius: 10px; padding: 12px;")
        gpu_fl = QVBoxLayout(gpu_frame)
        gpu_text = format_gpu_info(gpu_info)
        gpu_label = QLabel(gpu_text)
        gpu_label.setFont(QFont("Consolas", 10))
        gpu_label.setStyleSheet("color: #e0e0e0;")
        gpu_fl.addWidget(gpu_label)
        dlg_layout.addWidget(gpu_frame)

        # Audio info
        ext_counts = {}
        for af in audio_files:
            ext = af.suffix.lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        ext_str = ", ".join(f"{count}x {ext}" for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]))

        audio_frame = QFrame()
        audio_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border-radius: 10px; padding: 12px;")
        audio_fl = QVBoxLayout(audio_frame)
        audio_info = QLabel(f"📁 {len(audio_files)} arquivo(s) de áudio encontrado(s)\n   {ext_str}")
        audio_info.setFont(QFont("Consolas", 10))
        audio_info.setStyleSheet("color: #e0e0e0;")
        audio_fl.addWidget(audio_info)
        dlg_layout.addWidget(audio_frame)

        # Modelo Whisper
        model_row = QHBoxLayout()
        model_lbl = QLabel("Modelo Whisper:")
        model_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        model_row.addWidget(model_lbl)

        recommended = gpu_info.get("recommended_model", "base")
        model_options = [f"{info['label']} — {info['desc']}" for info in WHISPER_MODELS.values()]
        model_keys = list(WHISPER_MODELS.keys())
        model_display_to_key = dict(zip(model_options, model_keys))
        recommended_idx = model_keys.index(recommended)

        model_combo = QComboBox()
        model_combo.addItems(model_options)
        model_combo.setCurrentIndex(recommended_idx)
        model_combo.setFont(QFont("Segoe UI", 9))
        model_row.addWidget(model_combo, stretch=1)
        dlg_layout.addLayout(model_row)

        # Dispositivo
        device_row = QHBoxLayout()
        device_lbl = QLabel("Processamento:")
        device_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        device_row.addWidget(device_lbl)

        device_options = {"Automático": "auto", "GPU (Placa de Vídeo / CUDA)": "cuda", "CPU (Apenas Processador)": "cpu"}
        device_combo = QComboBox()
        device_combo.addItems(list(device_options.keys()))
        device_combo.setFont(QFont("Segoe UI", 9))
        device_combo.setFixedWidth(250)
        device_row.addWidget(device_combo)
        device_row.addStretch()
        dlg_layout.addLayout(device_row)

        # Idioma
        lang_row = QHBoxLayout()
        lang_lbl = QLabel("Idioma:")
        lang_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lang_row.addWidget(lang_lbl)

        lang_options = {"Português (pt)": "pt", "Inglês (en)": "en", "Espanhol (es)": "es", "Auto-detectar": None}
        lang_combo = QComboBox()
        lang_combo.addItems(list(lang_options.keys()))
        lang_combo.setFont(QFont("Segoe UI", 9))
        lang_combo.setFixedWidth(200)
        lang_row.addWidget(lang_combo)
        lang_row.addStretch()
        dlg_layout.addLayout(lang_row)

        # Forçar retranscrição
        force_check = QCheckBox("Retranscrever tudo (ignorar cache)")
        force_check.setFont(QFont("Segoe UI", 10))
        dlg_layout.addWidget(force_check)

        # Progresso
        prog_frame = QFrame()
        prog_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border-radius: 10px; padding: 10px;")
        prog_fl = QVBoxLayout(prog_frame)
        progress_label = QLabel("Aguardando início...")
        progress_label.setFont(QFont("Segoe UI", 10))
        progress_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        prog_fl.addWidget(progress_label)

        progress_bar = QProgressBar()
        progress_bar.setFixedHeight(12)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(False)
        prog_fl.addWidget(progress_bar)
        dlg_layout.addWidget(prog_frame)

        # Botões
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.setFont(QFont("Segoe UI", 11))
        btn_cancel.setFixedSize(120, 40)
        btn_cancel.clicked.connect(dialog.close)
        btn_row.addWidget(btn_cancel)

        btn_start = QPushButton("▶️ Iniciar Transcrição")
        btn_start.setObjectName("btnAccent")
        btn_start.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        btn_start.setFixedSize(200, 40)
        btn_row.addWidget(btn_start)
        dlg_layout.addLayout(btn_row)

        # --- Lógica de início ---
        def on_start():
            selected_display = model_combo.currentText()
            selected_model = model_display_to_key.get(selected_display, "base")
            selected_lang_display = lang_combo.currentText()
            selected_lang = lang_options.get(selected_lang_display, "pt")
            selected_device_display = device_combo.currentText()
            selected_device = device_options.get(selected_device_display, "auto")

            btn_start.setEnabled(False)
            btn_start.setText("⏳ Transcrevendo...")
            model_combo.setEnabled(False)
            device_combo.setEnabled(False)
            lang_combo.setEnabled(False)
            force_check.setEnabled(False)

            btn_cancel.setText("⏹️ Parar")
            btn_cancel.setStyleSheet("background-color: #aa3333; border-color: #cc4444;")
            btn_cancel.clicked.disconnect()
            btn_cancel.clicked.connect(lambda: self._cancel_transcription(btn_cancel))

            def update_progress(current, total, filename, status):
                def _update():
                    pct = current / total if total > 0 else 0
                    progress_bar.setValue(int(pct * 100))
                    if filename:
                        short_name = filename[:40] + "..." if len(filename) > 40 else filename
                        progress_label.setText(f"[{current}/{total}] {short_name}")
                        progress_label.setStyleSheet(f"color: {self.colors['text']};")
                    elif status == "concluído":
                        progress_label.setText(f"✅ Concluído! {total} arquivo(s) processado(s)")
                        progress_label.setStyleSheet(f"color: {self.colors['success']};")
                self._bridge.invoke(_update)

            def run_transcription():
                cache_dir = self.base_dir / ".chat_export_cache"
                self._transcriber = AudioTranscriber(
                    model_name=selected_model,
                    language=selected_lang,
                    device=selected_device,
                    cache_dir=cache_dir,
                    progress_callback=update_progress,
                    log_callback=lambda msg: self._bridge.invoke(lambda m=msg: self._add_log(m)),
                )
                try:
                    results = self._transcriber.transcribe_folder(
                        audio_folder, force_retranscribe=force_check.isChecked(),
                    )
                    if results:
                        self.transcriptions.update(results)
                        count = len({v for v in results.values()})

                        def on_complete():
                            btn_start.setEnabled(True)
                            btn_start.setText("✅ Concluído!")
                            btn_start.setStyleSheet(f"background-color: {self.colors['success']};")
                            btn_cancel.setText("Fechar")
                            btn_cancel.setStyleSheet("")
                            btn_cancel.clicked.disconnect()
                            btn_cancel.clicked.connect(dialog.close)
                            self.btn_whisper.setText(f"✅ {count} transcritos")
                            self.btn_whisper.setStyleSheet("background-color: #1a7a7a; border-color: #259090;")
                            self._add_log(f"🎙️ {count} transcrições de áudio prontas para uso")
                        self._bridge.invoke(on_complete)
                    else:
                        def on_empty():
                            btn_start.setEnabled(True)
                            btn_start.setText("▶️ Iniciar Transcrição")
                            btn_cancel.setText("Fechar")
                            btn_cancel.setStyleSheet("")
                            btn_cancel.clicked.disconnect()
                            btn_cancel.clicked.connect(dialog.close)
                        self._bridge.invoke(on_empty)
                except Exception as e:
                    logger.exception("Erro na transcrição")
                    def on_error():
                        progress_label.setText(f"❌ Erro: {e}")
                        progress_label.setStyleSheet("color: #ff6666;")
                        btn_start.setEnabled(True)
                        btn_start.setText("▶️ Tentar Novamente")
                        btn_cancel.setText("Fechar")
                        btn_cancel.setStyleSheet("")
                        btn_cancel.clicked.disconnect()
                        btn_cancel.clicked.connect(dialog.close)
                    self._bridge.invoke(on_error)
                finally:
                    self._transcriber = None

            threading.Thread(target=run_transcription, daemon=True).start()

        btn_start.clicked.connect(on_start)
        dialog.exec()

    def _cancel_transcription(self, btn_cancel):
        """Cancela a transcrição em andamento."""
        if self._transcriber:
            self._transcriber.cancel()
            self._add_log("⏹️ Cancelamento solicitado...")
            btn_cancel.setEnabled(False)
            btn_cancel.setText("Cancelando...")

    def _inject_transcriptions_dialog(self):
        """Permite injetar transcrições em um HTML já exportado."""
        if not self.transcriptions:
            QMessageBox.information(
                self, "Sem transcrições",
                "Nenhuma transcrição disponível.\n\n"
                "Primeiro, use '🎙️ Transcrever Áudios' para gerar as transcrições,\n"
                "ou selecione uma pasta que já possua transcrições em cache."
            )
            return

        html_file, _ = QFileDialog.getOpenFileName(
            self, "Selecionar HTML exportado para injetar transcrições",
            str(self.base_dir) if self.base_dir else "",
            "Arquivos HTML (*.html);;Todos os arquivos (*.*)"
        )
        if not html_file:
            return

        html_path = Path(html_file)
        self._add_log(f"📝 Injetando transcrições em: {html_path.name}")

        try:
            from inject_transcriptions import inject_transcriptions_into_html
            injected, already = inject_transcriptions_into_html(html_path, self.transcriptions)

            if injected > 0:
                self._add_log(f"✅ {injected} transcrição(ões) injetada(s) com sucesso!")
                if already > 0:
                    self._add_log(f"ℹ️ {already} áudio(s) já possuíam transcrição")
                QMessageBox.information(
                    self, "✅ Transcrições Injetadas",
                    f"Resultado:\n\n📝 {injected} transcrição(ões) injetada(s)\n"
                    f"ℹ️ {already} já existiam\n\nArquivo atualizado:\n{html_path.name}"
                )
            elif already > 0:
                self._add_log(f"ℹ️ Todas as {already} transcrições já estavam presentes")
                QMessageBox.information(
                    self, "ℹ️ Nenhuma alteração",
                    f"Todos os {already} áudio(s) já possuem transcrição neste HTML."
                )
            else:
                self._add_log("⚠️ Nenhum áudio correspondente encontrado no HTML")
                QMessageBox.information(
                    self, "⚠️ Nenhuma correspondência",
                    "Nenhum áudio no HTML corresponde às transcrições disponíveis.\n\n"
                    "Certifique-se de que o HTML foi exportado a partir da mesma pasta."
                )
        except Exception as e:
            self._add_log(f"❌ Erro ao injetar transcrições: {e}")
            logger.exception("Erro ao injetar transcrições")
            QMessageBox.critical(self, "Erro", f"Erro ao injetar transcrições:\n{e}")

    # ------------------------------------------------------------------
    # Timezone
    # ------------------------------------------------------------------
    def _on_timezone_change(self, value: str):
        """Atualiza o fuso horário usado no parsing (thread-safe)"""
        try:
            offset_hours = int(value.replace("UTC", ""))
            constants.set_timezone_offset(timedelta(hours=offset_hours))
            config.timezone_offset_hours = offset_hours
            self._add_log(f"🌐 Fuso horário alterado para {value}")
            if self.threads:
                self._add_log("⚠️ Recarregue a pasta para aplicar o novo fuso horário")
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Seleção de pasta / Cache / Carregamento
    # ------------------------------------------------------------------
    def _select_folder(self):
        """Seleciona pasta"""
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta com arquivos HTML")
        if not folder:
            return

        self.base_dir = Path(folder)
        html_files = list(self.base_dir.glob("*.html"))

        # Filtrar arquivos que foram gerados por este programa
        html_files = [f for f in html_files if not f.name.startswith("chat_")
                      and not f.name.startswith("todas_conversas_")
                      and not f.name.startswith("filtradas_")]

        if not html_files:
            QMessageBox.critical(self, "Erro", "Nenhum arquivo HTML encontrado na pasta!")
            self._add_log("❌ Nenhum arquivo HTML encontrado")
            return

        self._add_log(f"📂 Pasta selecionada: {folder}")
        self._add_log(f"📄 Encontrados {len(html_files)} arquivo(s) HTML")
        for hf in html_files:
            self._add_log(f"   • {hf.name}")

        self.status_label.setText("⏳ Carregando conversas de todos os HTMLs...")
        self.progress_bar.set(0)
        self.percent_label.setText("0%")
        self.btn_select.setEnabled(False)
        self.btn_export_all.setEnabled(False)

        thread = threading.Thread(target=self._load_files, args=(html_files,))
        thread.start()

    def _get_cache_key(self, html_files) -> str:
        """Gera chave de cache baseada nos arquivos (caminho + tamanho + modificação)"""
        parts = []
        for f in sorted(html_files, key=lambda x: str(x)):
            stat = f.stat()
            parts.append(f"{f}:{stat.st_size}:{stat.st_mtime_ns}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    def _get_file_cache_key(self, html_file: Path) -> str:
        """Gera chave de cache para um único arquivo"""
        stat = html_file.stat()
        return hashlib.md5(f"{html_file}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()

    def _get_cache_dir(self, html_files) -> Path:
        """Retorna diretório de cache"""
        cache_dir = html_files[0].parent / ".chat_export_cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir

    def _get_cache_path(self, html_files) -> Path:
        """Retorna caminho do arquivo de cache"""
        cache_dir = self._get_cache_dir(html_files)
        key = self._get_cache_key(html_files)
        return cache_dir / f"cache_{key}.json"

    def _load_file_cache(self, html_file: Path, cache_dir: Path):
        """Carrega cache de um único arquivo"""
        try:
            key = self._get_file_cache_key(html_file)
            cache_path = cache_dir / f"file_{key}.json"
            if cache_path.exists():
                return load_cache(cache_path)
        except Exception as e:
            logger.debug("Cache de arquivo não encontrado para %s: %s", html_file.name, e)
        return None

    def _save_file_cache(self, html_file: Path, cache_dir: Path, data: dict):
        """Salva cache de um único arquivo"""
        try:
            key = self._get_file_cache_key(html_file)
            cache_path = cache_dir / f"file_{key}.json"
            save_cache(cache_path, data)
        except Exception as e:
            logger.debug("Erro ao salvar cache de arquivo: %s", e)

    def _load_from_cache(self, html_files):
        """Tenta carregar resultado do cache"""
        try:
            cache_path = self._get_cache_path(html_files)
            if cache_path.exists():
                data = load_cache(cache_path)
                if data:
                    logger.info("Cache encontrado: %s", cache_path.name)
                    return data
        except Exception as e:
            logger.warning("Erro ao ler cache: %s", e)
        return None

    def _save_to_cache(self, html_files, data):
        """Salva resultado parseado no cache"""
        try:
            cache_path = self._get_cache_path(html_files)
            save_cache(cache_path, data)
            size_mb = cache_path.stat().st_size / (1024 * 1024)
            self._bridge.invoke(lambda: self._add_log(f"💾 Cache salvo ({size_mb:.1f} MB)"))
            logger.info("Cache salvo: %s (%.1f MB)", cache_path.name, size_mb)
        except Exception as e:
            logger.warning("Erro ao salvar cache: %s", e)

    def _load_files(self, html_files):
        """Carrega arquivos em background e consolida threads de múltiplos HTMLs"""
        logger.debug("_load_files iniciado")
        start_time = time.time()

        # Tentar carregar do cache
        cached = self._load_from_cache(html_files)
        if cached:
            self._bridge.invoke(lambda: self._add_log("⚡ Carregado do cache!"))
            self.threads = cached["threads"]
            self.owner_username = cached.get("owner_username", "")
            self.owner_id = cached.get("owner_id", "")
            self.profile_media = cached.get("profile_media", ProfileMedia())
            elapsed = time.time() - start_time
            self._bridge.invoke(lambda: self._add_log(f"⏱️ Carregado em {elapsed:.2f}s (cache)"))
            self.threads.sort(
                key=lambda t: (t.messages[-1].sent or datetime.min) if t.messages else datetime.min,
                reverse=True
            )
            self._bridge.invoke(self._update_ui)
            return

        all_threads = []
        total_files = len(html_files)
        cache_dir = self._get_cache_dir(html_files)
        cached_count = 0
        parsed_count = 0

        for i, html_file in enumerate(html_files):
            try:
                file_cached = self._load_file_cache(html_file, cache_dir)
                if file_cached:
                    threads = file_cached["threads"]
                    all_threads.extend(threads)
                    if file_cached.get("owner_username"):
                        self.owner_username = file_cached["owner_username"]
                    if file_cached.get("owner_id"):
                        self.owner_id = file_cached["owner_id"]
                    cached_count += 1
                    self._bridge.invoke(lambda f=html_file: self._add_log(f"⚡ Cache: {f.name}"))
                    if total_files > 0:
                        self._bridge.invoke(lambda v=(i + 1) / total_files: self._update_progress(v))
                    continue

                logger.debug("Processando arquivo %d/%d: %s", i + 1, total_files, html_file)
                self._bridge.invoke(lambda f=html_file: self._add_log(f"📖 Processando: {f.name}"))

                parser = MetaRecordsParser(str(html_file), self._log_callback)

                def progress_cb(p, _i=i):
                    overall = (_i + p) / total_files
                    self._bridge.invoke(lambda v=overall: self._update_progress(v))

                logger.debug("Iniciando parse...")
                threads = parser.parse(progress_cb)
                logger.debug("Parse concluído. Threads encontrados: %d", len(threads))

                all_threads.extend(threads)

                if parser.owner_username:
                    self.owner_username = parser.owner_username
                if parser.owner_id:
                    self.owner_id = parser.owner_id

                self._save_file_cache(html_file, cache_dir, {
                    "threads": threads,
                    "owner_username": parser.owner_username,
                    "owner_id": parser.owner_id,
                })
                parsed_count += 1

            except Exception as e:
                logger.error("Erro ao processar %s: %s", html_file, e, exc_info=True)
                self._bridge.invoke(lambda e=e, f=html_file: self._add_log(f"❌ Erro em {f.name}: {e}"))

        # Consolidar threads
        logger.debug("Consolidando %d threads...", len(all_threads))
        self._bridge.invoke(lambda: self._add_log(f"🔄 Consolidando {len(all_threads)} threads..."))

        self.threads = consolidate_threads(
            all_threads,
            log_callback=lambda msg: self._bridge.invoke(lambda m=msg: self._add_log(m))
        )

        elapsed = time.time() - start_time
        self._bridge.invoke(lambda: self._add_log(f"⏱️ Tempo de processamento: {elapsed:.2f}s"))
        if cached_count > 0:
            self._bridge.invoke(lambda: self._add_log(
                f"⚡ Incremental: {cached_count} do cache, {parsed_count} re-parseados"
            ))

        # Parsear mídias do perfil
        logger.debug("Parseando mídias do perfil...")
        self._bridge.invoke(lambda: self._add_log("📸 Buscando mídias do perfil (fotos, vídeos, stories)..."))
        combined_media = ProfileMedia()
        for html_file in html_files:
            try:
                mp = MediaParser(str(html_file), self._log_callback)
                pm = mp.parse()
                combined_media.photos.extend(pm.photos)
                combined_media.videos.extend(pm.videos)
                combined_media.stories.extend(pm.stories)

                gcp = GenericCategoryParser(str(html_file), self._log_callback)
                generic_cats = gcp.parse()
                for gcat in generic_cats:
                    existing = next((c for c in combined_media.generic_categories if c.category_id == gcat.category_id), None)
                    if existing:
                        existing.records.extend(gcat.records)
                    else:
                        combined_media.generic_categories.append(gcat)
            except Exception as e:
                logger.warning("Erro ao parsear mídias/categorias genéricas de %s: %s", html_file, e)
        self.profile_media = combined_media
        if not combined_media.is_empty:
            gen_cat_len = len(combined_media.generic_categories)
            self._bridge.invoke(lambda: self._add_log(
                f"📸 Mídias/Dados do perfil: {len(combined_media.photos)} fotos, "
                f"{len(combined_media.videos)} vídeos, {len(combined_media.stories)} stories, "
                f"{gen_cat_len} outras categorias"
            ))

        # Ordenar
        self.threads.sort(
            key=lambda t: (t.messages[-1].sent or datetime.min) if t.messages else datetime.min,
            reverse=True
        )

        # Salvar no cache
        self._save_to_cache(html_files, {
            "threads": self.threads,
            "owner_username": self.owner_username,
            "owner_id": self.owner_id,
            "profile_media": self.profile_media,
        })

        # Auto-carregar transcrições do cache
        cache_path = self.base_dir / ".chat_export_cache"
        transcription_cache_file = cache_path / "transcriptions" / "transcription_cache.json"
        if transcription_cache_file.exists() and not self.transcriptions:
            from transcriber import TranscriptionCache
            tc = TranscriptionCache(cache_path)
            cached_transcriptions = tc.get_all_as_dict()
            if cached_transcriptions:
                self.transcriptions.update(cached_transcriptions)
                count = len({v for v in cached_transcriptions.values()})
                self._bridge.invoke(lambda c=count: self._add_log(f"🎙️ {c} transcrições carregadas do cache"))
                self._bridge.invoke(lambda c=count: self.btn_whisper.setText(f"✅ {c} transcritos"))

        self._bridge.invoke(self._update_ui)

    # ------------------------------------------------------------------
    # UI Update
    # ------------------------------------------------------------------
    def _is_owner(self, participant: tuple) -> bool:
        """Verifica se o participante é o dono da conta"""
        username, platform, user_id = participant
        return (user_id == self.owner_id or
                username.lower() == self.owner_username.lower())

    def _update_progress(self, value: float):
        """Atualiza barra de progresso"""
        self.progress_bar.set(value)
        percent = int(value * 100)
        self.percent_label.setText(f"{percent}%")

    def _update_ui(self):
        """Atualiza UI após carregamento"""
        self.filtered_threads = None
        self.search_entry.clear()
        self.date_from_entry.clear()
        self.date_to_entry.clear()
        self.search_results_label.setText("")

        self.btn_select.setEnabled(True)
        self._update_progress(1.0)

        if not self.threads:
            self.status_label.setText("⚠️ Nenhuma conversa encontrada")
            self._add_log("⚠️ Nenhuma conversa encontrada")
            self._update_threads_list()
            return

        total_msgs = sum(len(t.messages) for t in self.threads)
        self.status_label.setText(f"✅ {len(self.threads)} conversas • {total_msgs:,} mensagens")
        self._add_log("✅ Carregamento concluído!")
        self._add_log(f"📊 Total: {len(self.threads)} conversas, {total_msgs:,} mensagens")
        self._add_log("🔒 HTML será gerado 100% offline")

        self.offline_status_label.setText("✅ Pronto | 🔒 HTML 100% Offline")
        self.offline_status_label.setStyleSheet(f"color: {self.colors['success']};")

        self._update_threads_list()
        self.btn_export_all.setEnabled(True)
        self.btn_export_json.setEnabled(True)
        self.btn_export_csv.setEnabled(True)
        self.btn_clear.setEnabled(True)

    @property
    def _display_threads(self) -> List[Thread]:
        """Retorna threads filtradas ou todas"""
        if self.filtered_threads is not None:
            return self.filtered_threads
        return self.threads

    # ------------------------------------------------------------------
    # Limpar Conversas
    # ------------------------------------------------------------------
    def _clear_conversations(self):
        """Limpa todas as conversas carregadas para permitir remontar outra"""
        if not self.threads:
            return

        reply = QMessageBox.question(
            self, "Limpar Conversas",
            "Deseja limpar todas as conversas carregadas?\n\n"
            "Você poderá selecionar uma nova pasta em seguida.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.threads = []
        self.profile_media = ProfileMedia()
        self.owner_username = ""
        self.owner_id = ""
        self.base_dir = None
        self.filtered_threads = None
        self.transcriptions = {}

        # Limpar lista de threads
        while self._threads_layout.count():
            item = self._threads_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Restaurar placeholder
        self.placeholder = QLabel(
            "📂 Nenhuma conversa carregada\n\n"
            "Clique em 'Selecionar Pasta' para carregar conversas\n"
            "de TODOS os arquivos HTML na pasta\n\n"
            "🔗 Threads de diferentes arquivos serão mesclados!"
        )
        self.placeholder.setFont(QFont("Segoe UI", 12))
        self.placeholder.setStyleSheet(f"color: {self.colors['text_dim']};")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._threads_layout.addWidget(self.placeholder)

        # Resetar pesquisa
        self.search_entry.clear()
        self.date_from_entry.clear()
        self.date_to_entry.clear()
        self.search_results_label.setText("")

        # Resetar barra de progresso
        self.progress_bar.set(0)
        self.percent_label.setText("0%")
        self.status_label.setText("⏳ Selecione uma pasta com arquivos HTML")

        # Desabilitar botões de exportação
        self.btn_export_all.setEnabled(False)
        self.btn_export_json.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.btn_clear.setEnabled(False)

        self._add_log("🗑️ Conversas limpas")
        self._add_log("📂 Selecione uma nova pasta para processar")

    # ------------------------------------------------------------------
    # Pesquisa / Filtro
    # ------------------------------------------------------------------
    def _filter_threads(self):
        """Filtra threads com base nos critérios de pesquisa"""
        query = self.search_entry.text().strip().lower()
        search_type = self.search_type.currentText()
        date_from = self._parse_filter_date(self.date_from_entry.text().strip())
        date_to = self._parse_filter_date(self.date_to_entry.text().strip())

        if not query and not date_from and not date_to:
            self._clear_search()
            return

        if date_to:
            date_to = date_to.replace(hour=23, minute=59, second=59)

        self._add_log(f"🔍 Pesquisando: '{query}' [{search_type}]...")
        self.status_label.setText("🔍 Pesquisando...")

        filtered = []
        total_msg_matches = 0

        for thread in self.threads:
            thread_match = False
            msg_count = 0

            if query and search_type in ("Tudo", "Participante"):
                if thread.thread_name and query in thread.thread_name.lower():
                    thread_match = True
                for p in thread.participants:
                    if query in p[0].lower():
                        thread_match = True
                        break

            if not thread_match or search_type != "Participante":
                for msg in thread.messages:
                    if date_from and msg.sent and msg.sent < date_from:
                        continue
                    if date_to and msg.sent and msg.sent > date_to:
                        continue
                    if search_type == "Chamadas" and not msg.is_call:
                        continue
                    if search_type == "Links" and not msg.share_url:
                        continue
                    if search_type == "Mídias" and not msg.attachments:
                        continue
                    if query:
                        body_lower = (msg.body or "").lower()
                        author_lower = msg.author.lower()
                        if query in body_lower or query in author_lower:
                            thread_match = True
                            msg_count += 1
                    elif date_from or date_to:
                        thread_match = True
                        msg_count += 1
                    elif search_type in ("Chamadas", "Links", "Mídias"):
                        thread_match = True
                        msg_count += 1

            if thread_match:
                filtered.append(thread)
                total_msg_matches += msg_count

        self.filtered_threads = filtered
        self._update_threads_list()

        result_text = f"🔍 {len(filtered)} conversas"
        if total_msg_matches > 0:
            result_text += f" ({total_msg_matches:,} msgs)"
        self.search_results_label.setText(result_text)
        self.status_label.setText(f"🔍 {len(filtered)}/{len(self.threads)} conversas encontradas")
        self._add_log(f"🔍 Resultado: {len(filtered)} conversas encontradas")

    def _clear_search(self):
        """Limpa filtros de pesquisa"""
        self.search_entry.clear()
        self.date_from_entry.clear()
        self.date_to_entry.clear()
        self.search_results_label.setText("")
        self.filtered_threads = None
        if self.threads:
            total_msgs = sum(len(t.messages) for t in self.threads)
            self.status_label.setText(f"✅ {len(self.threads)} conversas • {total_msgs:,} mensagens")
        self._update_threads_list()

    def _parse_filter_date(self, text: str):
        """Converte string dd/mm/aaaa para datetime"""
        if not text:
            return None
        try:
            return datetime.strptime(text, "%d/%m/%Y")
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Threads List
    # ------------------------------------------------------------------
    def _update_threads_list(self):
        """Atualiza lista visual de threads com paginação"""
        # Limpar widgets existentes
        while self._threads_layout.count():
            item = self._threads_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        display = self._display_threads
        if not display:
            placeholder = QLabel("⚠️ Nenhuma conversa encontrada")
            placeholder.setFont(QFont("Segoe UI", 14))
            placeholder.setStyleSheet(f"color: {self.colors['text_dim']};")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._threads_layout.addWidget(placeholder)
            return

        self._cards_per_page = 100
        self._current_page = 0
        self._total_cards_shown = 0

        total = len(display)
        self._add_log(f"📋 {total} conversas disponíveis")
        self._load_page(0)

    def _load_page(self, page: int):
        """Carrega uma página de cards"""
        display = self._display_threads
        start = page * self._cards_per_page
        end = min(start + self._cards_per_page, len(display))

        for i in range(start, end):
            self._create_thread_card(display[i], i)
            self._total_cards_shown += 1

        self._current_page = page

        remaining = len(display) - (page + 1) * self._cards_per_page
        if remaining > 0:
            self._add_load_more_button(remaining)

        self._add_log(f"✅ Mostrando {self._total_cards_shown}/{len(display)} conversas")
        self.progress_bar.set(1.0)
        self.percent_label.setText("100%")

    def _add_load_more_button(self, remaining: int):
        """Adiciona botão para carregar mais conversas"""
        # Remove botão anterior se existir
        for i in range(self._threads_layout.count()):
            item = self._threads_layout.itemAt(i)
            w = item.widget() if item else None
            if w and w.objectName() == "loadMoreBtn":
                w.deleteLater()

        btn = QPushButton(
            f"📥 Carregar mais {min(remaining, self._cards_per_page)} conversas "
            f"(+{remaining} restantes)"
        )
        btn.setObjectName("loadMoreBtn")
        btn.setFont(QFont("Segoe UI", 11))
        btn.setFixedHeight(40)
        btn.setStyleSheet(
            f"background-color: {self.colors['accent']}; border-color: {self.colors['accent2']}; "
            f"border-radius: 10px; padding: 8px;"
        )
        btn.clicked.connect(self._load_more_cards)
        self._threads_layout.addWidget(btn)

    def _load_more_cards(self):
        """Carrega próxima página de cards"""
        # Remove botão "carregar mais"
        for i in range(self._threads_layout.count()):
            item = self._threads_layout.itemAt(i)
            w = item.widget() if item else None
            if w and w.objectName() == "loadMoreBtn":
                w.deleteLater()
                break
        self._load_page(self._current_page + 1)

    def _create_thread_card(self, thread: Thread, thread_index: int):
        """Cria card para um thread"""
        others = [p for p in thread.participants if not self._is_owner(p)]

        if thread.thread_name:
            name = thread.thread_name
        else:
            name = ", ".join([p[0] for p in others[:3]]) if others else f"Thread {thread.thread_id[:8]}"
            if len(others) > 3:
                name += f" +{len(others)-3}"

        card = QFrame()
        card.setObjectName("threadCard")
        card.setFixedHeight(70)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(15, 8, 15, 8)

        avatar = QLabel("💬")
        avatar.setFont(QFont("Segoe UI", 22))
        avatar.setFixedWidth(50)
        card_layout.addWidget(avatar)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(5, 0, 0, 0)
        info_layout.setSpacing(2)

        display_name = name[:45] + ("..." if len(name) > 45 else "")
        name_label = QLabel(display_name)
        name_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {self.colors['accent']};")
        info_layout.addWidget(name_label)

        meta_parts = [f"📝 {len(thread.messages)} msgs"]
        if thread.messages:
            first = thread.messages[0].sent
            last = thread.messages[-1].sent
            if first and last:
                meta_parts.append(f"📅 {first.strftime('%d/%m/%Y')} - {last.strftime('%d/%m/%Y')}")

        meta_label = QLabel("  •  ".join(meta_parts))
        meta_label.setFont(QFont("Segoe UI", 9))
        meta_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        info_layout.addWidget(meta_label)

        card_layout.addWidget(info_widget, stretch=1)

        btn_export = QPushButton("📤")
        btn_export.setObjectName("btnExport")
        btn_export.setFont(QFont("Segoe UI", 14))
        btn_export.setFixedSize(45, 45)
        btn_export.clicked.connect(lambda checked, t=thread: self._export_thread(t))
        card_layout.addWidget(btn_export)

        self._threads_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Exportações
    # ------------------------------------------------------------------
    def _export_thread(self, thread: Thread, open_browser=True):
        """Exporta um thread"""
        try:
            self._add_log(f"📤 Exportando: {thread.thread_id[:8]}...")

            generator = ChatHTMLGenerator(thread, self.owner_username, self.owner_id, self.transcriptions)

            if thread.thread_name:
                safe_name = re.sub(r'[<>:"/\\|?*]', '_', thread.thread_name)
            else:
                participants = [p[0] for p in thread.participants if p[0] != self.owner_username]
                safe_name = "_".join(participants[:3]) if participants else thread.thread_id
                safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)

            filename = f"chat_{safe_name}_{thread.thread_id[-8:]}.html"
            output_path = thread.base_dir / filename if thread.base_dir else self.base_dir / filename

            generator.write_to_file(output_path)

            self._add_log(f"✅ Salvo: {filename}")
            self._add_log("🔒 HTML 100% offline gerado!")

            if open_browser:
                webbrowser.open(str(output_path))
                QMessageBox.information(
                    self, "✅ Exportado com Sucesso!",
                    f"Arquivo salvo:\n{output_path}\n\n"
                    "🔒 SEGURANÇA:\n• HTML 100% offline\n"
                    "• Funciona sem internet\n• CSS/JS embutidos no arquivo"
                )
            return True

        except Exception as e:
            self._add_log(f"❌ Erro ao exportar: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao exportar: {e}")
            return False

    def _export_all(self):
        """Exporta todas as conversas em um único HTML (em background)"""
        if not self.threads:
            return

        threads_to_export = self._display_threads
        is_filtered = self.filtered_threads is not None
        filter_label = " (filtradas)" if is_filtered else ""

        self._add_log(f"📦 Gerando HTML unificado{filter_label}...")
        self._add_log(f"⏳ Processando {len(threads_to_export)} conversas...")
        self.status_label.setText("⏳ Gerando HTML...")
        self.progress_bar.set(0.1)
        self.btn_select.setEnabled(False)
        self.btn_export_all.setEnabled(False)

        thread = threading.Thread(target=self._export_all_background,
                                  args=(threads_to_export, is_filtered))
        thread.start()

    def _export_all_background(self, threads_to_export, is_filtered=False):
        """Gera HTML unificado em background thread"""
        try:
            filter_label = " (filtradas)" if is_filtered else ""
            logger.info("Iniciando geração do HTML%s...", filter_label)
            # Phase 8.3: Copiar threads se modo redigido estiver ativo (evita mutação no estado da UI)
            redact = getattr(self, 'redact_mode', False)
            if redact:
                import copy
                threads_for_gen = copy.deepcopy(threads_to_export)
                self._bridge.invoke(lambda: self._add_log("🔒 Modo redigido ativo — nomes e números serão ocultados."))
            else:
                threads_for_gen = threads_to_export
            generator = AllChatsHTMLGenerator(
                threads_for_gen, self.owner_username, self.owner_id, self.transcriptions,
                self.profile_media, base_dir=self.base_dir, redact=redact
            )

            self._bridge.invoke(lambda: self._update_progress(0.7))

            suffix = "_redigido" if redact else ""
            prefix = "filtradas" if is_filtered else "todas_conversas"
            filename = f"{prefix}{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            output_path = self.base_dir / filename

            generator.write_to_file(output_path)
            logger.info("HTML gerado com sucesso!")

            total_msgs = sum(len(t.messages) for t in threads_to_export)

            def _finish():
                self._update_progress(1.0)
                self._add_log(f"✅ Exportado: {filename}")
                self._add_log(f"📊 {len(threads_to_export)} conversas, {total_msgs:,} mensagens{filter_label}")
                self._add_log("🔒 HTML 100% offline gerado!")
                self.status_label.setText(f"✅ HTML gerado com {len(threads_to_export)} conversas{filter_label}!")
                self.btn_select.setEnabled(True)
                self.btn_export_all.setEnabled(True)

                webbrowser.open(str(output_path))
                QMessageBox.information(
                    self, "✅ Exportado com Sucesso!",
                    f"Arquivo salvo:\n{output_path}\n\n"
                    f"📊 {len(threads_to_export)} conversas, {total_msgs:,} mensagens{filter_label}\n\n"
                    "🔒 SEGURANÇA:\n• HTML 100% offline\n"
                    "• Funciona sem internet\n• CSS/JS embutidos no arquivo"
                )

            self._bridge.invoke(_finish)

        except Exception as e:
            logger.error("Erro ao exportar: %s", e, exc_info=True)

            def _error():
                self._add_log(f"❌ Erro: {e}")
                self.status_label.setText("❌ Erro ao exportar")
                self.btn_select.setEnabled(True)
                self.btn_export_all.setEnabled(True)
                QMessageBox.critical(self, "Erro", f"Erro ao exportar: {e}")

            self._bridge.invoke(_error)

    def _export_json(self):
        """Exporta conversas para JSON (filtradas ou todas)"""
        if not self.threads:
            return

        threads_to_export = self._display_threads
        is_filtered = self.filtered_threads is not None
        filter_label = " (filtradas)" if is_filtered else ""

        self._add_log(f"📄 Exportando para JSON{filter_label}...")
        self.btn_export_json.setEnabled(False)

        def _background():
            try:
                prefix = "filtradas" if is_filtered else "conversas"
                filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                output_path = self.base_dir / filename

                exporter = JSONExporter(threads_to_export, self.owner_username, self.owner_id,
                                        base_dir=self.base_dir)
                exporter.export(output_path, include_stats=True)

                total_msgs = sum(len(t.messages) for t in threads_to_export)

                def _finish():
                    self._add_log(f"✅ JSON exportado: {filename}")
                    self._add_log(f"📊 {len(threads_to_export)} conversas, {total_msgs:,} mensagens{filter_label}")
                    self.btn_export_json.setEnabled(True)
                    QMessageBox.information(
                        self, "✅ JSON Exportado!",
                        f"Arquivo salvo:\n{output_path}\n\n"
                        f"📊 {len(threads_to_export)} conversas, {total_msgs:,} mensagens{filter_label}\n"
                        f"Inclui estatísticas detalhadas."
                    )
                self._bridge.invoke(_finish)

            except Exception as e:
                logger.error("Erro ao exportar JSON: %s", e, exc_info=True)
                def _error():
                    self._add_log(f"❌ Erro JSON: {e}")
                    self.btn_export_json.setEnabled(True)
                    QMessageBox.critical(self, "Erro", f"Erro ao exportar JSON: {e}")
                self._bridge.invoke(_error)

        threading.Thread(target=_background).start()

    def _export_csv(self):
        """Exporta conversas para CSV (filtradas ou todas)"""
        if not self.threads:
            return

        threads_to_export = self._display_threads
        is_filtered = self.filtered_threads is not None
        filter_label = " (filtradas)" if is_filtered else ""

        self._add_log(f"📊 Exportando para CSV{filter_label}...")
        self.btn_export_csv.setEnabled(False)

        def _background():
            try:
                prefix = "filtradas" if is_filtered else "conversas"
                filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                output_path = self.base_dir / filename

                exporter = CSVExporter(threads_to_export, self.owner_username, self.owner_id,
                                       base_dir=self.base_dir)
                exporter.export(output_path)

                stats_filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_stats.csv"
                stats_path = self.base_dir / stats_filename
                exporter.export_stats(stats_path)

                total_msgs = sum(len(t.messages) for t in threads_to_export)

                def _finish():
                    self._add_log(f"✅ CSV exportado: {filename}")
                    self._add_log(f"✅ Estatísticas: {stats_filename}")
                    self._add_log(f"📊 {len(threads_to_export)} conversas, {total_msgs:,} mensagens{filter_label}")
                    self.btn_export_csv.setEnabled(True)
                    QMessageBox.information(
                        self, "✅ CSV Exportado!",
                        f"Arquivos salvos:\n📄 {output_path}\n📊 {stats_path}\n\n"
                        f"{len(threads_to_export)} conversas, {total_msgs:,} mensagens{filter_label}"
                    )
                self._bridge.invoke(_finish)

            except Exception as e:
                logger.error("Erro ao exportar CSV: %s", e, exc_info=True)
                def _error():
                    self._add_log(f"❌ Erro CSV: {e}")
                    self.btn_export_csv.setEnabled(True)
                    QMessageBox.critical(self, "Erro", f"Erro ao exportar CSV: {e}")
                self._bridge.invoke(_error)

        threading.Thread(target=_background).start()


def main():
    # Configuração de logging: console (WARNING) + arquivo (DEBUG)
    log_format = '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Handler para console (menos verboso)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Handler para arquivo (detalhado)
    log_dir = Path(__file__).parent
    log_file = log_dir / f"chat_exporter_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logger.info("=" * 60)
    logger.info("Chat Exporter v5.2 (PyQt6) iniciado")
    logger.info("Log file: %s", log_file)
    logger.info("=" * 60)

    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)

    window = ChatExporterApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
