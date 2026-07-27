"""
Meta Chat Exporter - Template HTML completo do export "Todas as conversas".

Apresentação separada de generators_all.py (lógica de geração). Fornecida como
mixin para AllChatsHTMLGenerator, preservando o acesso a self.* (redact,
profile_media, tokens de stream, etc.).
"""

from typing import Any

from meta_chat_exporter.constants import (
    COLOR_RECEIVED_DARK_END,
    COLOR_RECEIVED_DARK_START,
    COLOR_RECEIVED_END,
    COLOR_RECEIVED_LABEL,
    COLOR_RECEIVED_START,
    COLOR_SENT_DARK_END,
    COLOR_SENT_DARK_START,
    COLOR_SENT_END,
    COLOR_SENT_LABEL,
    COLOR_SENT_START,
)


class AllChatsTemplateMixin:
    """Métodos de template (HTML/CSS/JS) do gerador de todas as conversas.

    Atributos ``redact`` e ``profile_media`` são definidos em
    ``AllChatsHTMLGenerator``; declarados aqui para o mypy no mixin.
    """

    redact: bool
    profile_media: Any

    def _get_profile_media_css(self) -> str:
        """CSS para o painel de mídias do perfil"""
        return """
        .pm-panel {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.92);
            z-index: 10000;
            flex-direction: column;
            overflow: hidden;
        }
        .pm-panel.active { display: flex; }
        .pm-panel-header {
            padding: 20px 30px 10px;
            background: #1a1a2e;
            border-bottom: 2px solid #333;
            position: relative;
        }
        .pm-panel-header h2 {
            color: #fff;
            font-size: 22px;
            margin-bottom: 5px;
        }
        .pm-summary {
            color: #aaa;
            font-size: 13px;
            margin-bottom: 12px;
        }
        .pm-summary span { margin-right: 15px; }
        .pm-close {
            position: absolute;
            top: 15px; right: 20px;
            background: #ff4757;
            color: #fff;
            border: none;
            border-radius: 50%;
            width: 36px; height: 36px;
            font-size: 18px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .pm-close:hover { background: #ff6b81; transform: scale(1.1); }
        .pm-tabs {
            display: flex;
            gap: 8px;
        }
        .pm-tab {
            background: #2d2d44;
            color: #ccc;
            border: 1px solid #444;
            border-radius: 8px 8px 0 0;
            padding: 8px 18px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        .pm-tab:hover { background: #3d3d5c; }
        .pm-tab.active {
            background: #4a4a6a;
            color: #fff;
            border-bottom-color: #4a4a6a;
        }
        .pm-tabs-scrollable {
            overflow-x: auto;
            white-space: nowrap;
            padding-bottom: 5px;
        }
        .pm-tabs-scrollable::-webkit-scrollbar {
            height: 6px;
        }
        .pm-tabs-scrollable::-webkit-scrollbar-thumb {
            background: #444;
            border-radius: 4px;
        }
        .pm-tab-gen {
            background: #2a3a4a;
            border-color: #3b4b5b;
        }
        .pm-panel-body {
            flex: 1;
            overflow-y: auto;
            padding: 20px 30px;
        }
        .pm-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 12px;
        }
        .pm-grid-stories {
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        }
        .pm-item {
            position: relative;
            border-radius: 10px;
            overflow: hidden;
            background: #222;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .pm-gen-container {
            display: flex;
            flex-direction: column;
            gap: 15px;
            padding: 10px;
        }
        .pm-gen-table {
            width: 100%;
            border-collapse: collapse;
            background: #222;
            border-radius: 8px;
            overflow: hidden;
            font-size: 13px;
            color: #ccc;
        }
        .pm-gen-table th, .pm-gen-table td {
            padding: 10px 15px;
            border-bottom: 1px solid #333;
            text-align: left;
            vertical-align: top;
        }
        .pm-gen-table th {
            background: #2a2a3a;
            color: #fff;
            width: 30%;
            font-weight: 500;
        }
        .pm-gen-table tr:last-child th, .pm-gen-table tr:last-child td {
            border-bottom: none;
        }
        .pm-item:hover { transform: scale(1.03); }
        .pm-item img {
            width: 100%;
            display: block;
            aspect-ratio: 1;
            object-fit: cover;
        }
        .pm-story-item img {
            aspect-ratio: 9/16;
        }
        /* Video items: no pointer cursor on container, info below */
        .pm-video-item {
            cursor: default;
            display: flex;
            flex-direction: column;
        }
        .pm-video-wrapper {
            position: relative;
            width: 100%;
            background: #000;
        }
        .pm-video-wrapper video {
            width: 100%;
            display: block;
            aspect-ratio: 1;
            object-fit: contain;
            background: #000;
        }
        .pm-story-item .pm-video-wrapper video {
            aspect-ratio: 9/16;
        }
        .pm-video-badge {
            position: absolute;
            top: 10px; right: 10px;
            background: rgba(0,0,0,0.6);
            border-radius: 50%;
            width: 32px; height: 32px;
            display: flex; align-items: center; justify-content: center;
            font-size: 14px;
            pointer-events: none;
        }
        /* Info bar below video (not overlay) */
        .pm-info-bar {
            background: #1a1a2e;
            padding: 8px 10px;
            color: #fff;
            font-size: 11px;
            border-top: 1px solid #333;
        }
        /* Overlay for photo items (hover) */
        .pm-overlay {
            position: absolute;
            bottom: 0; left: 0; right: 0;
            background: linear-gradient(transparent, rgba(0,0,0,0.85));
            padding: 30px 10px 10px;
            color: #fff;
            font-size: 11px;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .pm-item:hover .pm-overlay { opacity: 1; }
        .pm-date { font-size: 11px; color: #ccc; }
        .pm-caption { margin-top: 4px; font-size: 12px; line-height: 1.3; }
        .pm-location { margin-top: 3px; color: #8bc34a; }
        .pm-likes { color: #ff6b6b; }
        .pm-privacy {
            margin-top: 3px;
            font-size: 10px;
            color: #888;
            text-transform: uppercase;
        }
        .pm-ai-badge {
            display: inline-block;
            background: #9b59b6;
            color: #fff;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            margin-top: 3px;
        }
        .pm-category-badge {
            position: absolute;
            top: 8px;
            left: 8px;
            background: rgba(66, 103, 178, 0.9);
            color: #fff;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            z-index: 2;
            pointer-events: none;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }
        .pm-source {
            margin-top: 3px;
            color: #64b5f6;
            font-size: 11px;
        }
        .pm-filepath {
            margin-top: 4px;
            font-size: 9px;
            color: #999;
            font-family: 'Consolas', 'Courier New', monospace;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 100%;
            cursor: default;
        }
        .pm-filepath:hover {
            color: #ccc;
            white-space: normal;
            word-break: break-all;
        }
        .pm-lightbox {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.95);
            z-index: 10001;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        }
        .pm-lightbox.active { display: flex; }
        .pm-lightbox img {
            max-width: 90vw;
            max-height: 90vh;
            object-fit: contain;
            border-radius: 4px;
        }
        """

    def _get_profile_media_js(self) -> str:
        """JavaScript para o painel de mídias do perfil"""
        return """
        function toggleProfileMediaPanel() {
            var panel = document.getElementById('pm-panel');
            if (panel) panel.classList.toggle('active');
        }
        function toggleGlobalCatPanel() {
            var panel = document.getElementById('global-cat-panel');
            if (panel) panel.classList.toggle('active');
        }
        function switchPMTab(btn, sectionId) {
            var panel = btn.closest('.pm-panel');
            if(panel) {
                panel.querySelectorAll('.pm-tab').forEach(function(t) { t.classList.remove('active'); });
                panel.querySelectorAll('.pm-section').forEach(function(s) { s.style.display = 'none'; });
            }
            btn.classList.add('active');
            var el = document.getElementById(sectionId);
            if (el) el.style.display = 'block';
        }
        function openProfileMediaLightbox(el) {
            var lb = document.getElementById('pm-lightbox');
            if (!lb) return;
            var src = el.tagName === 'IMG' ? el.src : el.querySelector('img') ? el.querySelector('img').src : '';
            if (!src) return;
            lb.querySelector('img').src = src;
            lb.classList.add('active');
        }
        document.addEventListener('click', function(e) {
            var lb = document.getElementById('pm-lightbox');
            if (lb && lb.classList.contains('active') && e.target === lb) {
                lb.classList.remove('active');
            }
        });
        """

    def _get_full_template(
        self,
        sidebar: str,
        chats: str,
        total_threads: int,
        total_msgs: int,
        min_date: str = "",
        max_date: str = "",
        global_media_html: str = "",
        total_media: int = 0,
        stats_html: str = "",
        stats_css: str = "",
        stats_js: str = "",
        profile_media_html: str = "",
        profile_media_css: str = "",
        profile_media_js: str = "",
        global_categories_html: str = "",
        global_categories_buttons: str = "",
    ) -> str:
        """Retorna template HTML completo"""
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Meta Chat Exporter - {total_threads} conversas, {total_msgs:,} mensagens">
    <title>Meta Chat Exporter - {total_threads} conversas</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        /* Skip link para navegação por teclado */
        .skip-link {{
            position: absolute;
            top: -40px;
            left: 0;
            background: #333;
            color: #fff;
            padding: 8px 16px;
            z-index: 9999;
            font-size: 14px;
            transition: top 0.2s;
        }}
        .skip-link:focus {{
            top: 0;
        }}

        /* Focus visible para acessibilidade */
        *:focus-visible {{
            outline: 2px solid #6366f1;
            outline-offset: 2px;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #d9d9d9;
            height: 100vh;
            overflow: hidden;
            color: #333;
        }}

        .app-container {{
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}

        /* SIDEBAR */
        .sidebar {{
            width: 320px;
            min-width: 320px;
            max-width: 320px;
            flex-shrink: 0;
            background: linear-gradient(180deg, #ffffff 0%, #f0f0f0 100%);
            border-right: 1px solid #e0e0e0;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .sidebar-header {{
            padding: 12px 15px;
            background: #fff;
            border-bottom: 1px solid #e0e0e0;
        }}

        .sidebar-header h1 {{
            font-size: 16px;
            color: #333;
            margin-bottom: 2px;
        }}

        .sidebar-header p {{
            font-size: 11px;
            color: #888;
        }}

        .sidebar-title-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            flex-wrap: nowrap;
        }}

        .sidebar-title-row h1 {{
            flex-shrink: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .sidebar-header-buttons {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            flex-shrink: 0;
        }}

        .btn-global-media {{
            background: #666;
            border: none;
            color: #fff;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 10px;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 500;
            white-space: nowrap;
            text-align: center;
        }}

        .btn-global-media:hover {{
            background: #555;
            transform: translateY(-1px);
        }}

        .btn-global-media.active {{
            background: linear-gradient(135deg, #8B4513, #A0522D);
            box-shadow: 0 0 8px rgba(139, 69, 19, 0.5);
        }}

        .message.disappearing-hidden {{
            display: none !important;
        }}

        .date-separator.disappearing-hidden {{
            display: none !important;
        }}

        .media-gallery-panel.global-panel {{
            max-width: 1400px;
            width: 98%;
        }}

        .media-gallery-item-chat {{
            font-size: 10px;
            color: #666;
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-weight: 500;
        }}

        .warning-note {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 6px;
            padding: 6px 10px;
            margin-bottom: 8px;
            font-size: 10px;
            color: #856404;
            line-height: 1.3;
        }}

        .warning-note strong {{
            color: #664d03;
        }}

        .sidebar-search {{
            padding: 5px 15px;
        }}

        .sidebar-search input {{
            width: 100%;
            padding: 7px 10px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #fff;
            color: #333;
            font-size: 12px;
            outline: none;
        }}

        .sidebar-search input:focus {{
            border-color: #999;
        }}

        .sidebar-search input::placeholder {{
            color: #999;
        }}

        .sidebar-filter {{
            padding: 8px 15px;
            border-bottom: 1px solid #e0e0e0;
            background: #fafafa;
        }}

        .filter-title {{
            font-size: 11px;
            color: #666;
            margin-bottom: 5px;
            font-weight: 500;
        }}

        .filter-dates {{
            display: flex;
            gap: 8px;
            margin-bottom: 6px;
        }}

        .filter-date-group {{
            flex: 1;
        }}

        .filter-date-group label {{
            font-size: 10px;
            color: #666;
            display: block;
            margin-bottom: 2px;
        }}

        .filter-date-group input {{
            width: 100%;
            padding: 4px 6px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background: #fff;
            color: #333;
            font-size: 11px;
            outline: none;
        }}

        .filter-date-group input::-webkit-calendar-picker-indicator {{
            cursor: pointer;
        }}

        .filter-clear {{
            width: 100%;
            padding: 4px;
            border: none;
            border-radius: 5px;
            background: #e0e0e0;
            color: #555;
            font-size: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .filter-clear:hover {{
            background: #d0d0d0;
            color: #333;
        }}

        .contacts-list {{
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }}

        .contact-item {{
            display: flex;
            align-items: center;
            padding: 12px 15px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 5px;
            background: #fff;
            border: 1px solid transparent;
        }}

        .contact-item:hover {{
            background: #f0f0f0;
            border-color: #ddd;
        }}

        .contact-item.active {{
            background: #e8e8e8;
            border: 1px solid #ccc;
        }}

        .contact-avatar {{
            width: 45px;
            height: 45px;
            border-radius: 50%;
            background: linear-gradient(135deg, #666, #888);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            margin-right: 12px;
        }}

        .contact-info {{
            flex: 1;
            min-width: 0;
            overflow: hidden;
        }}

        .contact-name {{
            font-weight: 600;
            font-size: 14px;
            color: #333;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .contact-username {{
            font-size: 11px;
            color: #888;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-top: 1px;
        }}

        .contact-preview {{
            font-size: 12px;
            color: #666;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-top: 3px;
        }}

        .contact-meta {{
            text-align: right;
            margin-left: 10px;
        }}

        .contact-time {{
            font-size: 11px;
            color: #999;
        }}

        .contact-count {{
            font-size: 10px;
            background: #666;
            color: #fff;
            padding: 3px 8px;
            border-radius: 12px;
            margin-top: 5px;
            min-width: 20px;
            text-align: center;
            display: inline-block;
            white-space: nowrap;
        }}

        .search-badge {{
            font-size: 9px;
            background: #e67e22;
            color: #fff;
            padding: 3px 7px;
            border-radius: 10px;
            margin-left: 5px;
            display: none;
            min-width: 16px;
            text-align: center;
            white-space: nowrap;
        }}

        .disappearing-badge-count {{
            font-size: 9px;
            background: #8B4513;
            color: #fff;
            padding: 3px 7px;
            border-radius: 10px;
            margin-left: 5px;
            display: none;
            min-width: 16px;
            text-align: center;
            white-space: nowrap;
        }}

        .search-highlight {{
            animation: highlightPulse 2s ease-in-out;
            box-shadow: 0 0 15px rgba(230, 126, 34, 0.8) !important;
            border: 2px solid #e67e22 !important;
        }}

        @keyframes highlightPulse {{
            0%, 100% {{ box-shadow: 0 0 5px rgba(230, 126, 34, 0.5); }}
            50% {{ box-shadow: 0 0 20px rgba(230, 126, 34, 1); }}
        }}

        /* Destaque da palavra pesquisada */
        .word-highlight {{
            background: #ffd700;
            font-weight: 600;
            padding: 1px 4px;
            border-radius: 3px;
            scroll-margin: 200px;
            color: #333;
        }}

        .word-highlight.current {{
            background: #ffcc00;
            box-shadow: 0 0 10px rgba(255, 204, 0, 0.9);
            animation: wordPulse 1s ease-in-out infinite;
        }}

        @keyframes wordPulse {{
            0%, 100% {{ box-shadow: 0 0 5px rgba(255, 204, 0, 0.6); }}
            50% {{ box-shadow: 0 0 15px rgba(255, 204, 0, 1); }}
        }}

        /* CHAT AREA */
        .chat-area {{
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            background: linear-gradient(180deg, #c8c8c8 0%, #d9d9d9 50%, #e5e5e5 100%);
            overflow: hidden;
        }}

        .chat-container {{
            display: flex;
            flex-direction: column;
            height: 100%;
            overflow: hidden;
        }}

        .chat-container[style*="display: none"] {{
            content-visibility: hidden;
        }}

        .chat-header {{
            padding: 15px 25px;
            background: #fff;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .chat-header-info {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .chat-header-avatar {{
            width: 45px;
            height: 45px;
            border-radius: 50%;
            background: linear-gradient(135deg, #666, #888);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }}

        .chat-header-name {{
            font-size: 16px;
            font-weight: 600;
            color: #333;
        }}

        .chat-header-participants {{
            font-size: 12px;
            color: #888;
        }}

        .chat-header-meta {{
            font-size: 13px;
            color: #666;
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .search-nav {{
            display: flex;
            align-items: center;
            gap: 5px;
            background: #f0f0f0;
            padding: 4px 8px;
            border-radius: 15px;
            font-size: 12px;
        }}

        .search-nav-btn {{
            background: #ddd;
            border: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }}

        .search-nav-btn:hover {{
            background: #ccc;
        }}

        .search-nav-info {{
            font-weight: 600;
            color: #555;
            min-width: 40px;
            text-align: center;
        }}

        .btn-media-gallery {{
            background: linear-gradient(135deg, #555, #666);
            border: none;
            color: #fff;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 500;
        }}

        .btn-media-gallery:hover {{
            background: linear-gradient(135deg, #666, #777);
            transform: translateY(-1px);
        }}

        .btn-details-toggle {{
            background: linear-gradient(135deg, #4a6670, #5a7a85);
            border: none;
            color: #fff;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 500;
        }}

        .btn-details-toggle:hover {{
            background: linear-gradient(135deg, #5a7a85, #6a8a95);
            transform: translateY(-1px);
        }}

        .btn-details-toggle.active {{
            background: linear-gradient(135deg, #2a8a9a, #3a9aaa);
            box-shadow: 0 0 8px rgba(42, 138, 154, 0.5);
        }}

        /* ÍCONE DE DETALHES/ORIGEM DA MENSAGEM */
        .msg-details-icon {{
            display: none;
            position: absolute;
            top: -8px;
            right: -8px;
            font-size: 11px;
            cursor: help;
            opacity: 0.7;
            transition: all 0.2s;
            z-index: 10;
            background: #666;
            color: #fff;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            text-align: center;
            line-height: 18px;
            font-style: normal;
            font-weight: bold;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}

        .message.sent .msg-details-icon {{
            background: rgba(255,255,255,0.4);
        }}

        .message.received .msg-details-icon {{
            background: rgba(255,255,255,0.4);
        }}

        .msg-details-icon:hover {{
            opacity: 1;
            transform: scale(1.1);
        }}

        .details-visible .msg-details-icon {{
            display: inline-block;
        }}

        /* Tooltip customizado para detalhes */
        .msg-details-icon::after {{
            content: attr(data-tooltip);
            position: absolute;
            top: -30px;
            right: 0;
            background: #333;
            color: #fff;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 11px;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: all 0.2s;
            pointer-events: none;
            z-index: 100;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            font-family: monospace;
        }}

        .msg-details-icon:hover::after {{
            opacity: 1;
            visibility: visible;
            top: -35px;
        }}

        /* MEDIA GALLERY PANEL */
        .media-gallery-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.85);
            z-index: 2000;
            justify-content: center;
            align-items: center;
        }}

        .media-gallery-overlay.active {{
            display: flex;
        }}

        .media-gallery-panel {{
            background: #fff;
            border-radius: 16px;
            width: 95%;
            max-width: 1200px;
            height: 90vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
            overflow: hidden;
        }}

        .media-gallery-header {{
            padding: 20px 25px;
            background: linear-gradient(135deg, #505050, #666);
            color: #fff;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .media-gallery-header h3 {{
            font-size: 18px;
            font-weight: 600;
            margin: 0;
        }}

        .media-gallery-close {{
            background: rgba(255,255,255,0.2);
            border: none;
            color: #fff;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            font-size: 20px;
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .media-gallery-close:hover {{
            background: rgba(255,255,255,0.3);
        }}

        .media-gallery-filters {{
            padding: 15px 25px;
            background: #f5f5f5;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .media-filter-btn {{
            background: #e0e0e0;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            color: #555;
            font-weight: 500;
        }}

        .media-filter-btn:hover {{
            background: #d0d0d0;
        }}

        .media-filter-btn.active {{
            background: linear-gradient(135deg, #555, #666);
            color: #fff;
        }}

        .media-filter-count {{
            background: rgba(0,0,0,0.15);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            margin-left: 5px;
        }}

        .media-filter-btn.active .media-filter-count {{
            background: rgba(255,255,255,0.25);
        }}

        .filter-icon-img {{
            display: inline-block;
            width: 16px;
            height: 12px;
            background: linear-gradient(135deg, #666 0%, #999 50%, #777 100%);
            border-radius: 2px;
            position: relative;
            margin-right: 2px;
            vertical-align: middle;
        }}

        .filter-icon-img::before {{
            content: '';
            position: absolute;
            top: 2px;
            left: 2px;
            width: 4px;
            height: 4px;
            background: #fff;
            border-radius: 50%;
        }}

        .filter-icon-img::after {{
            content: '';
            position: absolute;
            bottom: 2px;
            left: 3px;
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid #fff;
        }}

        .media-filter-btn.active .filter-icon-img {{
            background: linear-gradient(135deg, #aaa 0%, #ddd 50%, #bbb 100%);
        }}

        .media-gallery-content {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }}

        .media-gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }}

        .media-gallery-item {{
            background: #f5f5f5;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #e0e0e0;
            transition: all 0.2s;
            position: relative;
        }}

        .media-gallery-item:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            border-color: #ccc;
        }}

        .media-gallery-item.type-image .media-thumb {{
            aspect-ratio: 1;
            overflow: hidden;
        }}

        .media-gallery-item.type-image .media-thumb img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .media-gallery-item.type-video .media-thumb {{
            aspect-ratio: 16/9;
            overflow: hidden;
            position: relative;
            background: #f0f0f0;
        }}

        .media-gallery-item.type-video .media-thumb video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .media-gallery-item.type-audio .media-thumb {{
            padding: 15px 10px;
            background: linear-gradient(135deg, #667, #556);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 140px;
        }}

        .media-gallery-item.type-audio .audio-icon {{
            font-size: 40px;
            margin-bottom: 10px;
        }}

        .media-gallery-item.type-audio audio {{
            width: 100%;
            height: 36px;
        }}

        .gallery-audio-container {{
            width: 100%;
            padding: 8px 5px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .gallery-audio-container audio {{
            width: 100%;
            height: 32px;
            min-width: 0;
        }}

        .gallery-audio-container .audio-speed {{
            display: flex;
            gap: 5px;
            justify-content: center;
        }}

        .gallery-audio-container .audio-speed button {{
            padding: 3px 8px;
            border: none;
            border-radius: 10px;
            background: #ddd;
            color: #555;
            font-size: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .gallery-audio-container .audio-speed button:hover {{
            background: #ccc;
            color: #333;
        }}

        .gallery-audio-container .audio-speed button.active {{
            background: linear-gradient(135deg, #555, #777);
            color: #fff;
        }}

        .gallery-transcription {{
            margin-top: 8px;
            padding: 8px 10px;
            background: rgba(255,255,255,0.9);
            border-radius: 6px;
            font-size: 11px;
            line-height: 1.4;
            color: #333;
            max-height: 60px;
            overflow-y: auto;
        }}

        .gallery-transcription em {{
            font-style: italic;
        }}

        .media-gallery-item-info {{
            padding: 12px;
            background: #fff;
        }}

        .media-gallery-item-filename {{
            font-size: 10px;
            color: #555;
            margin-bottom: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-family: monospace;
        }}

        .media-gallery-item-date {{
            font-size: 11px;
            color: #444;
            margin-bottom: 8px;
        }}

        .media-gallery-item-author {{
            font-size: 12px;
            color: #333;
            font-weight: 600;
            margin-bottom: 8px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .media-go-to-msg {{
            background: linear-gradient(135deg, #555, #666);
            border: none;
            color: #fff;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 11px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s;
        }}

        .media-go-to-msg:hover {{
            background: linear-gradient(135deg, #666, #777);
        }}

        .media-gallery-empty {{
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }}

        .media-gallery-empty .empty-icon {{
            font-size: 50px;
            margin-bottom: 15px;
            opacity: 0.5;
        }}

        .chat-messages {{
            flex: 1;
            overflow-y: auto;
            padding: 20px 25px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            contain: layout style;
            will-change: scroll-position;
        }}

        .load-more-container {{
            text-align: center;
            padding: 12px 0;
        }}

        .btn-load-more {{
            background: linear-gradient(135deg, #2a5298, #1e3c72);
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(30, 60, 114, 0.3);
        }}

        .btn-load-more:hover {{
            background: linear-gradient(135deg, #3a6cc8, #2a5298);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(30, 60, 114, 0.4);
        }}

        .chat-messages::-webkit-scrollbar {{
            width: 10px;
        }}

        .chat-messages::-webkit-scrollbar-track {{
            background: transparent;
        }}

        .chat-messages::-webkit-scrollbar-thumb {{
            background: #888;
            border-radius: 5px;
        }}

        .chat-messages::-webkit-scrollbar-thumb:hover {{
            background: #aaa;
        }}

        /* MESSAGES */
        .date-separator {{
            text-align: center;
            padding: 15px 0;
        }}

        .date-separator span {{
            background: #555;
            padding: 6px 16px;
            border-radius: 15px;
            font-size: 11px;
            color: #fff;
            font-weight: 500;
        }}

        .message {{
            display: flex;
            flex-direction: column;
            max-width: 80%;
            /* Phase 7.1 — Virtual scrolling nativo via CSS */
            content-visibility: auto;
            contain-intrinsic-size: auto 60px;
        }}

        .message.sent {{
            align-self: flex-end;
        }}

        .message.received {{
            align-self: flex-start;
        }}

        .message-bubble {{
            padding: 10px 14px;
            border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            position: relative;
        }}

        .message.sent .message-bubble {{
            background: linear-gradient(135deg, {COLOR_SENT_START}, {COLOR_SENT_END});
            color: #fff;
            border-bottom-right-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}

        .message.received .message-bubble {{
            background: linear-gradient(135deg, {COLOR_RECEIVED_START}, {COLOR_RECEIVED_END});
            color: #fff;
            border-bottom-left-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}

        .color-legend {{
            display: flex;
            gap: 14px;
            flex-wrap: wrap;
            font-size: 12px;
            color: #666;
            padding: 8px 12px;
            margin: 0 0 8px 0;
        }}
        .color-legend span {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .color-legend .swatch {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
            display: inline-block;
        }}
        .color-legend .swatch-sent {{
            background: linear-gradient(135deg, {COLOR_SENT_START}, {COLOR_SENT_END});
        }}
        .color-legend .swatch-received {{
            background: linear-gradient(135deg, {COLOR_RECEIVED_START}, {COLOR_RECEIVED_END});
        }}
        body.dark-mode .color-legend {{ color: #aaa; }}
        body.dark-mode .color-legend .swatch-sent {{
            background: linear-gradient(135deg, {COLOR_SENT_DARK_START}, {COLOR_SENT_DARK_END});
        }}
        body.dark-mode .color-legend .swatch-received {{
            background: linear-gradient(135deg, {COLOR_RECEIVED_DARK_START}, {COLOR_RECEIVED_DARK_END});
        }}

        /* Grouped messages (consecutive from same author) */
        .message.grouped {{
            margin-top: 2px;
        }}
        .message.grouped .message-author {{
            display: none;
        }}
        .message.grouped.sent .message-bubble {{
            border-radius: 16px;
            border-bottom-right-radius: 4px;
            border-top-right-radius: 4px;
        }}
        .message.grouped.received .message-bubble {{
            border-radius: 16px;
            border-bottom-left-radius: 4px;
            border-top-left-radius: 4px;
        }}

        .message-author {{
            display: table;
            width: fit-content;
            padding: 2px 7px;
            border-radius: 8px;
            background: rgba(255,255,255,0.9);
            font-size: 11px;
            font-weight: 700;
            margin-bottom: 4px;
        }}

        .message-author-sent {{ color: {COLOR_SENT_LABEL}; }}
        .message-author-received {{ color: {COLOR_RECEIVED_LABEL}; }}

        .message-content {{
            font-size: 14px;
            line-height: 1.4;
            word-wrap: break-word;
        }}

        .message.received .message-content {{
            color: #fff;
        }}

        .message.sent .message-content {{
            color: #fff;
        }}

        .message-time {{
            font-size: 10px;
            color: rgba(255,255,255,0.7);
            margin-top: 4px;
            text-align: right;
        }}

        .message.sent .message-time {{
            color: rgba(255,255,255,0.7);
        }}

        .edited-badge {{
            font-size: 10px;
            opacity: 0.7;
            margin-left: 2px;
        }}

        .message-content.emoji-only {{
            font-size: 36px;
            line-height: 1.3;
            letter-spacing: 4px;
        }}

        .attachment {{
            margin-top: 8px;
            border-radius: 10px;
            overflow: hidden;
        }}

        .audio-container {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: 8px;
            background: rgba(255,255,255,0.2);
            border-radius: 10px;
            min-width: 280px;
        }}

        .message.sent .audio-container {{
            background: rgba(255,255,255,0.2);
        }}

        .audio-container audio {{
            width: 100%;
            height: 36px;
        }}

        .audio-transcription {{
            margin-top: 8px;
            padding: 10px 12px;
            background: rgba(255,255,255,0.15);
            border-radius: 8px;
            font-size: 13px;
            line-height: 1.5;
        }}

        .message.sent .audio-transcription {{
            background: rgba(255,255,255,0.15);
        }}

        .transcription-label {{
            font-weight: 600;
            color: rgba(255,255,255,0.8);
            display: block;
            margin-bottom: 4px;
            font-size: 11px;
        }}

        .message.sent .transcription-label {{
            color: rgba(255,255,255,0.8);
        }}

        .transcription-text {{
            color: rgba(255,255,255,0.9);
        }}

        .message.sent .transcription-text {{
            color: rgba(255,255,255,0.9);
        }}

        .audio-speed {{
            display: flex;
            gap: 5px;
            justify-content: center;
        }}

        .audio-speed button {{
            padding: 4px 10px;
            border: none;
            border-radius: 12px;
            background: rgba(255,255,255,0.3);
            color: #fff;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .audio-speed button:hover {{
            background: rgba(255,255,255,0.4);
            color: #fff;
        }}

        .audio-speed button.active {{
            background: linear-gradient(135deg, #555, #777);
            color: #fff;
        }}

        .attachment audio {{
            width: 100%;
            height: 36px;
        }}

        .attachment video, .attachment img {{
            max-width: 100%;
            max-height: 250px;
            border-radius: 10px;
            cursor: pointer;
        }}

        .attachment-file {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.2);
            border-radius: 8px;
            font-size: 12px;
        }}

        .message.sent .attachment-file {{
            background: rgba(255,255,255,0.2);
        }}

        .attachment-file a {{
            color: #fff;
            text-decoration: none;
        }}

        .message.sent .attachment-file a {{
            color: #fff;
        }}

        .attachment-filename {{
            font-size: 10px;
            color: rgba(255,255,255,0.7);
            margin-top: 6px;
            padding: 4px 8px;
            word-break: break-word;
            text-align: center;
            line-height: 1.3;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
        }}

        .message.sent .attachment-filename {{
            color: rgba(255,255,255,0.7);
            background: rgba(255,255,255,0.1);
        }}

        .call-info {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.2);
            border-radius: 8px;
        }}

        .message.sent .call-info {{
            background: rgba(255,255,255,0.2);
        }}

        .call-info.missed {{
            border-left: 3px solid #e74c3c;
        }}

        .call-info.video-call {{
            border-left: 3px solid #9b59b6;
        }}

        .call-info.video-call.ended {{
            border-left: 3px solid #95a5a6;
        }}

        .call-info.audio-call {{
            border-left: 3px solid #3498db;
        }}

        .call-info.audio-call.ended {{
            border-left: 3px solid #95a5a6;
        }}

        .share-link {{
            margin-top: 6px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.2);
            border-radius: 8px;
        }}

        .message.sent .share-link {{
            background: rgba(255,255,255,0.2);
        }}

        .share-link a {{
            color: #fff;
            text-decoration: none;
            font-size: 12px;
            word-break: break-all;
        }}

        .message.sent .share-link a {{
            color: #fff;
        }}

        .share-link a:hover {{
            text-decoration: underline;
        }}

        .share-url {{
            font-size: 10px;
            color: rgba(255,255,255,0.6);
            margin-top: 6px;
            word-break: break-all;
            line-height: 1.3;
            padding: 4px 6px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            font-family: monospace;
        }}

        .message.sent .share-url {{
            color: rgba(255,255,255,0.6);
            background: rgba(255,255,255,0.1);
        }}

        /* ============================================
           Phase 6 — Rich Share Cards
           ============================================ */
        .share-card {{
            margin-top: 8px;
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 12px;
            overflow: hidden;
            background: rgba(255,255,255,0.15);
            max-width: 320px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        .share-card:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }}
        .share-card-link {{
            display: block;
            padding: 10px 12px;
            text-decoration: none;
            color: inherit;
        }}
        .share-card-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
        }}
        .share-card-icon {{
            font-size: 22px;
            line-height: 1;
        }}
        .share-card-meta {{
            flex: 1;
            min-width: 0;
        }}
        .share-card-title {{
            font-weight: 600;
            font-size: 13px;
            color: #fff;
        }}
        .share-card-id {{
            font-size: 10px;
            color: rgba(255,255,255,0.6);
            font-family: monospace;
            margin-top: 2px;
        }}
        .share-card-caption {{
            font-size: 13px;
            color: rgba(255,255,255,0.9);
            margin: 6px 0;
            word-break: break-word;
            line-height: 1.4;
        }}
        .share-card-url {{
            font-size: 9px;
            color: rgba(255,255,255,0.6);
            font-family: monospace;
            word-break: break-all;
            margin-top: 6px;
            opacity: 0.7;
        }}
        .share-card-instagram {{
            border-left: 3px solid #e1306c;
        }}
        .message.sent .share-card {{
            background: rgba(255,255,255,0.15);
            border-color: rgba(255,255,255,0.25);
        }}
        .message.sent .share-card-title {{ color: #fff; }}
        .message.sent .share-card-caption {{ color: rgba(255,255,255,0.9); }}
        .message.sent .share-card-id,
        .message.sent .share-card-url {{ color: rgba(255,255,255,0.6); }}

        /* ============================================
           Phase 6 — @mentions
           ============================================ */
        .mention {{
            color: #fff;
            font-weight: 600;
            background: rgba(255,255,255,0.25);
            padding: 0 4px;
            border-radius: 4px;
            cursor: default;
        }}
        .message.sent .mention {{
            color: #fff;
            background: rgba(255,255,255,0.25);
        }}

        /* ============================================
           Phase 6 — Auto-linkified URLs in body
           ============================================ */
        .body-link {{
            color: #cce0ff;
            text-decoration: underline;
            word-break: break-all;
        }}
        .body-link:hover {{ text-decoration: none; }}
        .body-link.link-whatsapp {{ color: #a0ffc0; }}
        .body-link.link-payment {{ color: #ffd28c; font-weight: 600; }}
        .body-link.link-instagram {{ color: #ffb8d4; }}
        .message.sent .body-link {{ color: #cce0ff; }}
        .message.sent .body-link.link-whatsapp {{ color: #a0ffc0; }}
        .message.sent .body-link.link-payment {{ color: #ffd28c; }}
        .message.sent .body-link.link-instagram {{ color: #ffb8d4; }}

        /* ============================================
           Phase 6 — Voice message placeholder (no attachment)
           ============================================ */
        .voice-msg-placeholder {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 8px 14px;
            background: rgba(255,255,255,0.15);
            border-radius: 18px;
            font-size: 13px;
            color: #fff;
        }}
        .voice-msg-icon {{ font-size: 18px; }}
        .voice-msg-waveform {{
            display: inline-flex;
            align-items: center;
            gap: 2px;
            height: 20px;
        }}
        .voice-msg-waveform span {{
            display: inline-block;
            width: 2px;
            background: linear-gradient(180deg, #fff, #cce0ff);
            border-radius: 1px;
            opacity: 0.7;
        }}
        .voice-msg-label {{ font-style: italic; opacity: 0.85; }}
        .message.sent .voice-msg-placeholder {{ background: rgba(255,255,255,0.15); color: #fff; }}
        .message.sent .voice-msg-waveform span {{
            background: linear-gradient(180deg, #fff, #cce0ff);
        }}

        /* ============================================
           Phase 6 — System messages (past participants, etc.)
           ============================================ */
        .system-message {{
            text-align: center;
            padding: 10px 0;
        }}
        .system-message span {{
            display: inline-block;
            background: #e8eef5;
            color: #555;
            padding: 5px 14px;
            border-radius: 14px;
            font-size: 12px;
            font-style: italic;
        }}

        .removed-message {{
            font-style: italic;
            color: rgba(255,255,255,0.5);
            font-size: 13px;
        }}

        .disappearing-badge {{
            margin-left: 6px;
            font-size: 14px;
            filter: grayscale(100%);
            opacity: 0.7;
            cursor: help;
        }}

        .disappearing-badge.view-once {{
            filter: sepia(1) saturate(5) hue-rotate(175deg);
            opacity: 1;
        }}

        /* LIGHTBOX */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 3000;
            justify-content: center;
            align-items: center;
            cursor: pointer;
        }}

        .lightbox img {{
            max-width: 95%;
            max-height: 95%;
            object-fit: contain;
        }}

        .lightbox.active {{
            display: flex;
        }}

        /* SCROLLBAR */
        ::-webkit-scrollbar {{
            width: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: transparent;
        }}

        ::-webkit-scrollbar-thumb {{
            background: #999;
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: #bbb;
        }}

        /* EMPTY STATE */
        .empty-chat {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #999;
        }}

        .empty-chat .icon {{
            font-size: 60px;
            margin-bottom: 20px;
        }}

        {stats_css}

        /* ============================================
           DARK MODE — Complete Theme Override
           ============================================ */
        body.dark-mode {{
            background: #1a1a2e;
            color: #e0e0e0;
        }}

        /* --- Sidebar --- */
        body.dark-mode .sidebar {{
            background: linear-gradient(180deg, #16213e 0%, #0f3460 100%);
            border-right-color: #2a2a4a;
        }}
        body.dark-mode .sidebar-header {{
            background: #16213e;
            border-bottom-color: #2a2a4a;
        }}
        body.dark-mode .sidebar-header h1 {{ color: #e0e0e0; }}
        body.dark-mode .sidebar-header p {{ color: #aaa; }}
        body.dark-mode .warning-note {{
            background: #332b00;
            border-color: #665500;
            color: #ffcc00;
        }}
        body.dark-mode .warning-note strong {{ color: #ffdd33; }}
        body.dark-mode .sidebar-search input {{
            background: #1a1a2e;
            color: #e0e0e0;
            border-color: #444;
        }}
        body.dark-mode .sidebar-filter {{
            background: rgba(255,255,255,0.05);
            border-bottom-color: #2a2a4a;
        }}
        body.dark-mode .filter-title {{ color: #aaa; }}
        body.dark-mode .sidebar-filter input,
        body.dark-mode .sidebar-filter select {{
            background: #1a1a2e;
            color: #e0e0e0;
            border-color: #444;
        }}
        body.dark-mode .sidebar-filter label {{ color: #ccc; }}
        body.dark-mode .filter-clear {{
            color: #aaa;
        }}
        body.dark-mode .filter-clear:hover {{
            color: #e0e0e0;
        }}

        /* --- Contacts list --- */
        body.dark-mode .contact-item {{
            border-bottom-color: #2a2a4a;
        }}
        body.dark-mode .contact-item:hover {{
            background: #1a1a3e;
        }}
        body.dark-mode .contact-item.active {{
            background: #1e3a5f;
        }}
        body.dark-mode .contact-name {{ color: #e0e0e0; }}
        body.dark-mode .contact-username {{ color: #888; }}
        body.dark-mode .contact-preview {{ color: #999; }}
        body.dark-mode .contact-time {{ color: #777; }}
        body.dark-mode .contact-count {{
            background: #444;
            color: #ddd;
        }}

        /* --- Chat area & header --- */
        body.dark-mode .chat-area {{
            background: linear-gradient(180deg, #0f0f23 0%, #151530 50%, #1a1a35 100%);
        }}
        body.dark-mode .chat-header {{
            background: linear-gradient(135deg, #16213e, #1a1a2e);
            border-bottom-color: #2a2a4a;
        }}
        body.dark-mode .chat-header-name {{ color: #e0e0e0; }}
        body.dark-mode .chat-header-participants {{ color: #888; }}
        body.dark-mode .chat-header-meta {{ color: #999; }}
        body.dark-mode .chat-msg-count {{ color: #aaa; }}

        /* --- Messages --- */
        body.dark-mode .message.sent .message-bubble {{
            background: linear-gradient(135deg, {COLOR_SENT_DARK_START}, {COLOR_SENT_DARK_END});
            color: #fdeaea;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        }}
        body.dark-mode .message.received .message-bubble {{
            background: linear-gradient(135deg, {COLOR_RECEIVED_DARK_START}, {COLOR_RECEIVED_DARK_END});
            color: #e0e0e0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        body.dark-mode .message-author {{ background: rgba(255,255,255,0.92); }}
        body.dark-mode .message-author-sent {{ color: {COLOR_SENT_LABEL}; }}
        body.dark-mode .message-author-received {{ color: {COLOR_RECEIVED_LABEL}; }}
        body.dark-mode .message-content {{ color: #ddd; }}
        body.dark-mode .message.sent .message-content {{ color: #fdeaea; }}
        body.dark-mode .message.received .message-content {{ color: #e0e0e0; }}
        body.dark-mode .message-time {{ color: rgba(255,255,255,0.6); }}
        body.dark-mode .message.sent .message-time {{ color: rgba(255,200,200,0.6); }}
        body.dark-mode .date-separator span {{
            background: #2a2a4a;
            color: #aaa;
        }}
        body.dark-mode .removed-message {{ color: rgba(255,255,255,0.4); }}

        /* --- Attachments --- */
        body.dark-mode .audio-container {{
            background: rgba(255,255,255,0.1);
        }}
        body.dark-mode .message.sent .audio-container {{
            background: rgba(255,255,255,0.1);
        }}
        body.dark-mode .audio-transcription {{
            background: rgba(255,255,255,0.08);
        }}
        body.dark-mode .message.sent .audio-transcription {{
            background: rgba(255,255,255,0.1);
        }}
        body.dark-mode .transcription-label {{ color: rgba(255,255,255,0.8); }}
        body.dark-mode .transcription-text {{ color: #ddd; }}
        body.dark-mode .audio-speed button {{
            background: rgba(255,255,255,0.2);
            color: #ccc;
        }}
        body.dark-mode .audio-speed button:hover {{
            background: rgba(255,255,255,0.3);
            color: #fff;
        }}
        body.dark-mode .audio-speed button.active {{
            background: linear-gradient(135deg, {COLOR_SENT_START}, {COLOR_SENT_END});
            color: #fff;
        }}
        body.dark-mode .attachment-file {{
            background: rgba(255,255,255,0.1);
            color: #ccc;
        }}
        body.dark-mode .message.sent .attachment-file {{
            background: rgba(255,255,255,0.1);
        }}
        body.dark-mode .attachment-file a {{ color: #bbd4ff; }}
        body.dark-mode .message.sent .attachment-file a {{ color: #ffd4d4; }}
        body.dark-mode .attachment-filename {{
            color: rgba(255,255,255,0.5);
            background: rgba(255,255,255,0.05);
        }}
        body.dark-mode .message.sent .attachment-filename {{
            color: rgba(255,200,200,0.5);
            background: rgba(255,255,255,0.08);
        }}

        /* --- Calls --- */
        body.dark-mode .call-info {{
            background: rgba(255,255,255,0.1);
            color: #ccc;
        }}
        body.dark-mode .message.sent .call-info {{
            background: rgba(255,255,255,0.1);
        }}

        /* --- Shared links --- */
        body.dark-mode .share-link {{
            background: rgba(255,255,255,0.1);
        }}
        body.dark-mode .message.sent .share-link {{
            background: rgba(255,255,255,0.1);
        }}
        body.dark-mode .share-link a {{ color: #bbd4ff; }}
        body.dark-mode .message.sent .share-link a {{ color: #ffd4d4; }}
        body.dark-mode .share-url {{
            color: rgba(255,255,255,0.5);
            background: rgba(255,255,255,0.05);
        }}
        body.dark-mode .message.sent .share-url {{
            color: rgba(255,200,200,0.5);
            background: rgba(255,255,255,0.08);
        }}

        /* --- Phase 6 dark mode --- */
        body.dark-mode .share-card {{
            background: rgba(255,255,255,0.08);
            border-color: rgba(255,255,255,0.15);
        }}
        body.dark-mode .share-card-title {{ color: #e0e0e0; }}
        body.dark-mode .share-card-caption {{ color: #b0bec5; }}
        body.dark-mode .share-card-id,
        body.dark-mode .share-card-url {{ color: rgba(255,255,255,0.5); }}
        body.dark-mode .share-card:hover {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }}
        body.dark-mode .mention {{
            color: #bbd4ff;
            background: rgba(187,212,255,0.15);
        }}
        body.dark-mode .message.sent .mention {{
            color: #ffd4d4;
            background: rgba(255,255,255,0.2);
        }}
        body.dark-mode .body-link {{ color: #bbd4ff; }}
        body.dark-mode .body-link.link-whatsapp {{ color: #5bdd85; }}
        body.dark-mode .body-link.link-payment {{ color: #ffb74d; }}
        body.dark-mode .body-link.link-instagram {{ color: #f48fb1; }}
        body.dark-mode .voice-msg-placeholder {{
            background: rgba(255,255,255,0.08);
            color: #cfd8dc;
        }}
        body.dark-mode .voice-msg-waveform span {{
            background: linear-gradient(180deg, #bbd4ff, #5a9bd6);
        }}
        body.dark-mode .system-message span {{
            background: #2a3450;
            color: #b0bec5;
        }}

        /* --- Search highlight --- */
        body.dark-mode .word-highlight {{
            background: #b8860b;
            color: #fff;
        }}
        body.dark-mode .word-highlight.current {{
            background: #daa520;
            box-shadow: 0 0 10px rgba(218,165,32,0.9);
        }}
        body.dark-mode .search-nav {{
            background: #2a2a4a;
            color: #ccc;
        }}
        body.dark-mode .search-nav-btn {{
            background: #3a3a5a;
            color: #ccc;
        }}
        body.dark-mode .search-nav-btn:hover {{
            background: #4a4a6a;
        }}
        body.dark-mode .search-nav-info {{ color: #aaa; }}

        /* --- Message details icon --- */
        body.dark-mode .msg-details-icon {{
            background: #444;
            color: #ddd;
        }}
        body.dark-mode .msg-details-icon::after {{
            background: #1a1a2e;
            color: #e0e0e0;
        }}

        /* --- Media gallery --- */
        body.dark-mode .media-gallery-panel {{
            background: #1a1a2e;
        }}
        body.dark-mode .media-gallery-header {{
            background: linear-gradient(135deg, #16213e, #0f3460);
        }}
        body.dark-mode .media-gallery-filters {{
            background: #16213e;
            border-bottom-color: #2a2a4a;
        }}
        body.dark-mode .media-filter-btn {{
            background: #2a2a4a;
            color: #ccc;
        }}
        body.dark-mode .media-filter-btn:hover {{
            background: #3a3a5a;
        }}
        body.dark-mode .media-filter-btn.active {{
            background: linear-gradient(135deg, #1e3a5f, #2a5090);
            color: #fff;
        }}
        body.dark-mode .media-gallery-content {{
            background: #1a1a2e;
        }}
        body.dark-mode .media-gallery-item {{
            background: #252545;
            border-color: #333;
        }}
        body.dark-mode .media-gallery-item:hover {{
            border-color: #555;
            box-shadow: 0 8px 25px rgba(0,0,0,0.4);
        }}
        body.dark-mode .media-gallery-item-info {{
            background: #1e1e3f;
        }}
        body.dark-mode .media-gallery-item-filename {{ color: #888; }}
        body.dark-mode .media-gallery-item-date {{ color: #aaa; }}
        body.dark-mode .media-gallery-item-author {{ color: #ccc; }}
        body.dark-mode .media-go-to-msg {{
            background: linear-gradient(135deg, #1e3a5f, #2a5090);
        }}
        body.dark-mode .media-go-to-msg:hover {{
            background: linear-gradient(135deg, #2a5090, #3a60a0);
        }}
        body.dark-mode .media-gallery-empty {{ color: #666; }}
        body.dark-mode .gallery-transcription {{
            background: rgba(255,255,255,0.08);
            color: #ccc;
        }}
        body.dark-mode .gallery-audio-container .audio-speed button {{
            background: #3a3a5a;
            color: #ccc;
        }}

        /* --- Load more / pagination --- */
        body.dark-mode .btn-load-more {{
            background: linear-gradient(135deg, #1e3a5f, #2a5090);
        }}
        body.dark-mode .btn-load-more:hover {{
            background: linear-gradient(135deg, #2a5090, #3a60a0);
        }}

        /* --- Button styles in header --- */
        body.dark-mode .btn-media-gallery {{
            background: linear-gradient(135deg, #2a2a4a, #3a3a5a);
        }}
        body.dark-mode .btn-media-gallery:hover {{
            background: linear-gradient(135deg, #3a3a5a, #4a4a6a);
        }}
        body.dark-mode .btn-details-toggle {{
            background: linear-gradient(135deg, #1e3a5f, #2a5090);
        }}
        body.dark-mode .btn-details-toggle:hover {{
            background: linear-gradient(135deg, #2a5090, #3a60a0);
        }}

        /* --- Lightbox --- */
        body.dark-mode .lightbox {{
            background: rgba(0,0,0,0.98);
        }}

        /* --- Empty state --- */
        body.dark-mode .empty-chat {{ color: #555; }}

        /* --- Scrollbar --- */
        body.dark-mode ::-webkit-scrollbar-thumb {{
            background: #444;
        }}
        body.dark-mode ::-webkit-scrollbar-thumb:hover {{
            background: #555;
        }}

        /* --- Global buttons --- */
        body.dark-mode .btn-global-media {{
            background: linear-gradient(135deg, #1e3a5f, #2a5090);
        }}
        body.dark-mode .btn-global-media:hover {{
            background: linear-gradient(135deg, #2a5090, #3a60a0);
        }}
        body.dark-mode .btn-dark-mode.active {{
            background: linear-gradient(135deg, #f9a825, #ff8f00);
        }}

        /* --- Stats panel dark mode --- */
        body.dark-mode .stats-panel {{
            background: rgba(0,0,0,0.92);
        }}
        body.dark-mode .stats-container {{
            background: #1a1a2e;
            color: #e0e0e0;
        }}
        body.dark-mode .stats-title {{ color: #e0e0e0; }}
        body.dark-mode .stats-section {{
            background: #16213e;
        }}
        body.dark-mode .stats-section h3 {{ color: #ccc; }}
        body.dark-mode .stat-card {{
            background: #1e1e3f;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        body.dark-mode .stat-number {{ color: #e0e0e0; }}
        body.dark-mode .stat-label {{ color: #888; }}
        body.dark-mode .stats-period {{ color: #777; }}
        body.dark-mode .bar-label {{ color: #aaa; }}
        body.dark-mode .bar-track {{ background: #2a2a4a; }}
        body.dark-mode .bar-fill {{
            background: linear-gradient(135deg, #3a6090, #5a80b0);
        }}
        body.dark-mode .bar-value {{ color: #ccc; }}
        body.dark-mode .stats-note {{ color: #777; }}
        body.dark-mode .stats-note strong {{ color: #aaa; }}
        body.dark-mode .hour-bar {{
            background: linear-gradient(180deg, #3a6090, #5a80b0);
        }}
        body.dark-mode .hour-bar:hover {{
            background: linear-gradient(180deg, #4a70a0, #6a90c0);
        }}
        body.dark-mode .hours-labels {{ color: #666; }}
        body.dark-mode .weekday-bar-track {{ background: #2a2a4a; }}
        body.dark-mode .weekday-bar-fill {{
            background: linear-gradient(180deg, #3a6090, #5a80b0);
        }}
        body.dark-mode .weekday-label {{ color: #aaa; }}
        body.dark-mode .weekday-value {{ color: #777; }}
        body.dark-mode .month-bar-fill {{
            background: linear-gradient(180deg, #3a6090, #5a80b0);
        }}
        body.dark-mode .month-label {{ color: #666; }}
        body.dark-mode .media-stat-item {{
            background: #1e1e3f;
        }}
        body.dark-mode .media-stat-value {{ color: #e0e0e0; }}
        body.dark-mode .media-stat-label {{ color: #888; }}
        body.dark-mode .call-stat {{
            background: #1e1e3f;
            color: #ccc;
        }}
        body.dark-mode .word-tag {{
            background: #1e1e3f;
            color: #ccc;
        }}
        body.dark-mode .word-tag small {{ color: #777; }}
        body.dark-mode .top-conv-item {{
            background: #1e1e3f;
        }}
        body.dark-mode .top-rank {{ color: #777; }}
        body.dark-mode .top-name {{ color: #ccc; }}
        body.dark-mode .top-msgs {{ color: #aaa; }}
        body.dark-mode .rt-row {{
            background: #1e1e3f;
        }}
        body.dark-mode .rt-name {{ color: #ccc; }}
        body.dark-mode .rt-stat {{ color: #aaa; }}
        body.dark-mode .rt-count {{ color: #777; }}
        body.dark-mode .hm-label {{ color: #aaa; }}
        body.dark-mode .hm-hour {{ color: #777; }}
        body.dark-mode .hm-cell {{ color: #ccc; }}
        body.dark-mode .emoji-tag small {{ color: #777; }}
        body.dark-mode .emoji-author-row {{
            background: #1e1e3f;
        }}
        body.dark-mode .emoji-author-name {{ color: #ccc; }}
        body.dark-mode .emoji-author-count {{ color: #aaa; }}
        body.dark-mode .integrity-bar {{ background: #2a2a4a; }}
        body.dark-mode .integrity-info {{ color: #ccc; }}
        body.dark-mode .integrity-missing {{
            background: #3a1a1a;
            color: #ff6b6b;
        }}
        body.dark-mode .integrity-meta {{ color: #777; }}
        body.dark-mode .gap-item {{
            background: #2a2a1a;
            border-left-color: #cc7a00;
        }}
        body.dark-mode .gap-conv {{ color: #ccc; }}
        body.dark-mode .gap-period {{ color: #888; }}
        body.dark-mode .gap-days {{ color: #ff9800; }}
        body.dark-mode .msg-len-label {{ color: #aaa; }}
        body.dark-mode .msg-len-bar-bg {{ background: #2a2a4a; }}
        body.dark-mode .msg-len-count {{ color: #ccc; }}
        body.dark-mode .comp-table th {{
            background: #1e1e3f;
            color: #ccc;
            border-bottom-color: #333;
        }}
        body.dark-mode .comp-table td {{
            color: #ddd;
            border-bottom-color: #333;
        }}
        body.dark-mode .comp-table tbody tr:hover {{
            background: #252545;
        }}

        /* --- SVG grafo --- */
        body.dark-mode .stats-section svg {{
            background: #16213e !important;
        }}
        body.dark-mode .stats-section svg text {{
            fill: #aaa !important;
        }}
        body.dark-mode .stats-section svg circle {{
            fill: #5a80b0 !important;
        }}
        body.dark-mode .stats-section svg line {{
            stroke: #5a80b0 !important;
        }}

        /* Categorias Globais Styles */
        .global-cat-panel {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.92);
            z-index: 10000;
            flex-direction: column;
            overflow: hidden;
            backdrop-filter: blur(10px);
        }}
        .global-cat-panel.active {{ display: flex; }}
        .btn-cat {{
            background: #2a3a4a;
            border-color: #3b4b5b;
        }}

        {profile_media_css}

        /* ============================================
           RESPONSIVE — Mobile Layout
           ============================================ */
        .sidebar-toggle {{
            display: none;
            position: fixed;
            top: 12px;
            left: 12px;
            z-index: 1100;
            background: linear-gradient(135deg, #505050, #6b6b6b);
            color: #fff;
            border: none;
            border-radius: 10px;
            width: 40px;
            height: 40px;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            align-items: center;
            justify-content: center;
            line-height: 1;
        }}
        body.dark-mode .sidebar-toggle {{
            background: linear-gradient(135deg, #1e3a5f, #2a5090);
        }}

        @media (max-width: 768px) {{
            .sidebar-toggle {{
                display: flex;
            }}
            .sidebar {{
                position: fixed;
                top: 0;
                left: 0;
                bottom: 0;
                z-index: 1050;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                width: 85vw;
                max-width: 360px;
            }}
            .sidebar.open {{
                transform: translateX(0);
            }}
            .sidebar-overlay {{
                display: none;
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.5);
                z-index: 1040;
            }}
            .sidebar-overlay.open {{
                display: block;
            }}
            .chat-area {{
                width: 100vw !important;
                margin-left: 0 !important;
            }}
            .chat-header {{
                padding-left: 56px !important;
            }}
            .message-bubble {{
                max-width: 90% !important;
            }}
            .message {{
                max-width: 85% !important;
            }}
            .btn-media-gallery,
            .btn-details-toggle,
            .btn-global-media,
            .btn-dark-mode,
            .sidebar-toggle {{
                min-height: 44px;
                min-width: 44px;
            }}
            .contact-item {{
                min-height: 44px;
            }}
            .media-gallery-panel {{
                width: 100vw !important;
                right: 0 !important;
            }}
            .stats-container {{
                width: 95vw !important;
                max-width: none !important;
                margin: 10px !important;
                padding: 15px !important;
            }}
            .stats-row {{
                flex-direction: column;
            }}
        }}

        /* ============================================
           Phase 7.2 — Copy button + toast
           ============================================ */
        .message-bubble {{ position: relative; }}
        .msg-copy-btn {{
            position: absolute;
            top: 4px;
            right: 4px;
            background: rgba(255,255,255,0.85);
            border: 1px solid #ccc;
            border-radius: 6px;
            width: 26px;
            height: 26px;
            font-size: 12px;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.2s;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2;
        }}
        .message:hover .msg-copy-btn {{ opacity: 1; }}
        .msg-copy-btn:hover {{ background: #fff; transform: scale(1.08); }}
        .message.sent .msg-copy-btn {{
            background: rgba(255,255,255,0.25);
            border-color: rgba(255,255,255,0.4);
            color: #fff;
        }}
        body.dark-mode .msg-copy-btn {{
            background: rgba(40,40,60,0.9);
            border-color: #3a3a5a;
            color: #e0e0e0;
        }}

        .toast-copy {{
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%) translateY(30px);
            background: #323232;
            color: #fff;
            padding: 10px 18px;
            border-radius: 20px;
            font-size: 13px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s, transform 0.2s;
            z-index: 10000;
        }}
        .toast-copy.show {{
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }}
        @media (prefers-reduced-motion: reduce) {{
            .toast-copy, .msg-copy-btn {{ transition: none; }}
        }}

        /* ============================================
           Phase 7.3 — Date picker popover + Jump highlight
           ============================================ */
        .btn-date-picker,
        .btn-chat-stats,
        .btn-chat-pdf {{
            background: #f0f0f0;
            border: 1px solid #d0d0d0;
            color: #444;
            padding: 6px 10px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.15s;
        }}
        .btn-date-picker:hover,
        .btn-chat-stats:hover,
        .btn-chat-pdf:hover {{
            background: #e0e0e0;
        }}
        body.dark-mode .btn-date-picker,
        body.dark-mode .btn-chat-stats,
        body.dark-mode .btn-chat-pdf {{
            background: #2a2a4a;
            border-color: #3a3a5a;
            color: #ddd;
        }}
        body.dark-mode .btn-date-picker:hover,
        body.dark-mode .btn-chat-stats:hover,
        body.dark-mode .btn-chat-pdf:hover {{
            background: #3a3a6a;
        }}
        .date-picker-popover {{
            display: none;
            position: absolute;
            top: 60px;
            right: 20px;
            background: #fff;
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 10px 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 500;
            gap: 8px;
            align-items: center;
        }}
        .date-picker-popover.open {{ display: flex; }}
        .date-picker-popover label {{
            font-size: 13px;
            color: #555;
            font-weight: 600;
        }}
        .date-picker-popover input[type="date"] {{
            padding: 4px 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }}
        body.dark-mode .date-picker-popover {{
            background: #1a1a2e;
            border-color: #3a3a5a;
            color: #e0e0e0;
        }}
        body.dark-mode .date-picker-popover label {{ color: #bbb; }}
        body.dark-mode .date-picker-popover input {{
            background: #2a2a4a;
            border-color: #3a3a5a;
            color: #e0e0e0;
        }}

        .message.jump-highlight .message-bubble,
        .date-separator.jump-highlight span {{
            animation: jump-pulse 2s ease-out;
        }}
        @keyframes jump-pulse {{
            0%, 100% {{ box-shadow: 0 1px 3px rgba(0,0,0,0.12); }}
            30%, 70% {{ box-shadow: 0 0 0 4px rgba(255,193,7,0.6); background: rgba(255,193,7,0.15); }}
        }}

        /* ============================================
           Phase 7.6 — Compact mode
           ============================================ */
        body.compact-mode .message {{
            margin-top: 1px !important;
            margin-bottom: 1px !important;
            font-size: 13px;
        }}
        body.compact-mode .message-bubble {{
            padding: 5px 9px !important;
        }}
        body.compact-mode .message-content {{
            font-size: 13px;
            line-height: 1.3;
        }}
        body.compact-mode .message-time {{
            font-size: 10px;
            margin-top: 2px;
        }}
        body.compact-mode .message-author {{
            font-size: 11px;
            margin-bottom: 1px;
        }}
        body.compact-mode .date-separator {{ padding: 6px 0; }}
        body.compact-mode .date-separator span {{ font-size: 11px; padding: 3px 10px; }}
        body.compact-mode .chat-messages {{ padding: 10px 16px !important; }}
        body.compact-mode .btn-global-media#btn-compact-mode {{
            background: linear-gradient(135deg, #43a047, #66bb6a);
        }}

        /* ============================================
           Phase 8.3 — Redact badge
           ============================================ */
        .redact-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #d32f2f, #e53935);
            color: #fff;
            font-size: 10px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 10px;
            margin-left: 8px;
            letter-spacing: 0.5px;
            vertical-align: middle;
        }}

        /* ============================================
           Phase 8.4 — Mini stats panel
           ============================================ */
        .chat-mini-stats {{
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
            padding: 12px 20px;
            font-size: 13px;
        }}
        .chat-mini-stats-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 8px;
        }}
        .chat-mini-stat {{
            flex: 1;
            min-width: 120px;
        }}
        .chat-mini-stat-label {{
            color: #777;
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .chat-mini-stat-value {{
            color: #222;
            font-size: 15px;
            font-weight: 700;
            margin-top: 2px;
        }}
        .chat-mini-stat-bar {{
            display: flex;
            height: 12px;
            border-radius: 6px;
            overflow: hidden;
            margin-top: 6px;
            background: #e0e0e0;
        }}
        .chat-mini-stat-bar-sent {{ background: linear-gradient(90deg, #4a90d9, #64b5f6); }}
        .chat-mini-stat-bar-received {{ background: linear-gradient(90deg, #a0a8b4, #bdbfc5); }}
        body.dark-mode .chat-mini-stats {{
            background: #1a1a2e;
            border-color: #2a2a4a;
            color: #ddd;
        }}
        body.dark-mode .chat-mini-stat-label {{ color: #888; }}
        body.dark-mode .chat-mini-stat-value {{ color: #eee; }}
        body.dark-mode .chat-mini-stat-bar {{ background: #2a2a4a; }}

        /* ============================================
           PRINT — Export to PDF Stylesheet
           ============================================ */
        @media print {{
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
            body {{
                background: #fff !important;
                font-size: 11pt;
            }}
            .sidebar,
            .sidebar-toggle,
            .sidebar-overlay,
            .btn-media-gallery,
            .btn-details-toggle,
            .btn-dark-mode,
            .btn-global-media,
            .btn-load-more,
            .load-more-container,
            .sidebar-search,
            .sidebar-filter,
            .lightbox,
            .media-gallery-overlay,
            .stats-panel,
            .global-cat-panel,
            .pm-panel,
            .msg-details-icon,
            .skip-link,
            .search-nav,
            .audio-speed,
            .msg-copy-btn,
            .btn-date-picker,
            .btn-chat-stats,
            .btn-chat-pdf,
            .date-picker-popover,
            .chat-mini-stats,
            .toast-copy {{
                display: none !important;
            }}
            /* Phase 8.1: Revelar todas as mensagens paginadas ao imprimir */
            [data-paginated="true"] {{
                display: block !important;
            }}
            .message {{ content-visibility: visible !important; }}
            .chat-area {{
                width: 100% !important;
                margin: 0 !important;
                position: static !important;
                overflow: visible !important;
                height: auto !important;
            }}
            .chat-header {{
                background: #f5f5f5 !important;
                color: #333 !important;
                position: static !important;
                box-shadow: none !important;
                border-bottom: 2px solid #333;
                page-break-after: avoid;
            }}
            .chat-header-name {{
                color: #000 !important;
                font-size: 14pt;
            }}
            .chat-messages {{
                overflow: visible !important;
                height: auto !important;
                padding: 10px !important;
            }}
            .message {{
                page-break-inside: avoid;
                max-width: 100% !important;
                box-shadow: none !important;
            }}
            .message-bubble {{
                box-shadow: none !important;
                border: 1px solid #ccc !important;
                max-width: 100% !important;
            }}
            .message.sent .message-bubble {{
                background: #e8e8e8 !important;
                color: #000 !important;
            }}
            .message.sent .message-time {{
                color: #666 !important;
            }}
            .date-separator {{
                page-break-after: avoid;
            }}
            .date-separator span {{
                background: #eee !important;
                color: #333 !important;
                border: 1px solid #ccc !important;
            }}
            .empty-chat {{
                display: none !important;
            }}
            a {{
                color: #000 !important;
                text-decoration: underline !important;
            }}
        }}
    </style>
</head>
<body>
    <a href="#chat-area" class="skip-link">Pular para mensagens</a>
    <button class="sidebar-toggle" onclick="toggleSidebar()" aria-label="Abrir menu">☰</button>
    <div class="sidebar-overlay" onclick="toggleSidebar()"></div>
    <div class="app-container" role="application" aria-label="Meta Chat Exporter">
        <!-- SIDEBAR -->
        <nav class="sidebar" role="navigation" aria-label="Lista de conversas">
            <div class="sidebar-header">
                <div class="warning-note">
                    <strong>⚠️ Nota:</strong> O chat remontado pode conter erros ou inconsistências nas mensagens. Considere sempre revisar o conteúdo no arquivo original. Além disso, os áudios que estiverem transcritos também podem conter imprecisões, revise-os nas mídias originais do mesmo modo.
                </div>
                <div class="sidebar-title-row">
                <h1>Conversas<br>Remontadas{' <span class="redact-badge" title="Dados redigidos: nomes e n\u00fameros ocultos">\U0001f512 Redigido</span>' if self.redact else ''}</h1>
                    <div class="sidebar-header-buttons">
                        <button class="btn-global-media" onclick="openGlobalMediaGallery()" aria-label="Abrir galeria de mídias"> Mídias ({total_media})</button>
                        {f'<button class="btn-global-media" onclick="toggleProfileMediaPanel()" aria-label="Abrir mídias do perfil">📸 Perfil ({self.profile_media.media_total})</button>' if self.profile_media.has_media else ''}
                        <button class="btn-global-media" onclick="toggleStatsPanel()" aria-label="Abrir painel de estatísticas">📊 Estatísticas</button>
                        {global_categories_buttons}
                        <button class="btn-global-media" id="btn-filter-disappearing" onclick="toggleDisappearingFilter()" aria-label="Filtrar mensagens temporárias"> Temporárias</button>
                        <button class="btn-global-media" id="btn-toggle-disappearing-icon" onclick="toggleDisappearingIcon()" aria-label="Ocultar ícones de mensagens temporárias">Ocultar ícones<br>das mensagens temporárias</button>
                        <button class="btn-global-media" id="btn-dark-mode" onclick="toggleDarkMode()" aria-label="Alternar modo escuro">🌙 Modo Escuro</button>
                        <button class="btn-global-media" id="btn-compact-mode" onclick="toggleCompactMode()" aria-label="Alternar modo compacto" title="Modo compacto: reduz espaçamento para ver mais mensagens">🗜️ Compacto</button>
                    </div>
                </div>
                <p>{total_threads} conversas • {total_msgs:,} mensagens</p>
            </div>
            <div class="sidebar-filter">
                <div class="filter-title">📅 Filtrar por período</div>
                <div class="filter-dates">
                    <div class="filter-date-group">
                        <label>De:</label>
                        <input type="date" id="date-start" min="{min_date}" max="{max_date}" onchange="filterByDate()" aria-label="Data inicial do filtro">
                    </div>
                    <div class="filter-date-group">
                        <label>Até:</label>
                        <input type="date" id="date-end" min="{min_date}" max="{max_date}" onchange="filterByDate()" aria-label="Data final do filtro">
                    </div>
                </div>
                <button class="filter-clear" onclick="clearDateFilter()">🗑️ Limpar tudo</button>
            </div>
            <div class="sidebar-search">
                <input type="text" id="search-messages" placeholder="🔍 Buscar nas mensagens..." oninput="searchInMessages(this.value)" aria-label="Buscar nas mensagens">
            </div>
            <div class="sidebar-search">
                <input type="text" id="search-input" placeholder="🔍 Buscar conversa..." oninput="filterContacts(this.value)" aria-label="Buscar conversa">
            </div>
            <div class="contacts-list" id="contacts-list" role="listbox" aria-label="Conversas">
                {sidebar}
            </div>
        </nav>

        <!-- CHAT AREA -->
        <main class="chat-area" id="chat-area" role="main" aria-label="Mensagens">
            {chats}
        </main>
    </div>

    {global_media_html}

    {stats_html}

    {profile_media_html}

    {global_categories_html}

    <div class="pm-lightbox" id="pm-lightbox" role="dialog" aria-label="Visualização de mídia">
        <img src="" alt="Imagem ampliada">
    </div>

    <div class="lightbox" onclick="this.classList.remove('active')" role="dialog" aria-label="Visualização de imagem">
        <img src="" alt="Imagem ampliada">
    </div>

    <script>
        // ===== CAPTURA DE ERROS PARA DEBUG =====
        window.onerror = function(message, source, lineno, colno, error) {{
            console.error('=== ERRO CAPTURADO ===');
            console.error('Mensagem:', message);
            console.error('Arquivo:', source);
            console.error('Linha:', lineno, 'Coluna:', colno);
            console.error('Erro completo:', error);
            console.error('Stack:', error ? error.stack : 'N/A');
            return false;
        }};

        window.addEventListener('unhandledrejection', function(event) {{
            console.error('=== PROMISE REJEITADA ===');
            console.error('Razão:', event.reason);
        }});

        let currentChat = 0;
        let disappearingFilterActive = false;
        let disappearingByChat = {{}};
        let disappearingIconHidden = false;
        // Phase 7.4 — Scroll position memory per chat (session only)
        const __scrollMemory = new Map();

        function __saveScroll(chatIndex) {{
            const chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            const msgs = chatDiv.querySelector('.chat-messages');
            if (msgs) __scrollMemory.set(chatIndex, msgs.scrollTop);
        }}

        function __restoreScroll(chatIndex) {{
            const chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            const msgs = chatDiv.querySelector('.chat-messages');
            if (!msgs) return;
            const saved = __scrollMemory.get(chatIndex);
            requestAnimationFrame(() => {{
                msgs.scrollTop = (saved !== undefined) ? saved : msgs.scrollHeight;
            }});
        }}

        function showChat(index) {{
            __saveScroll(currentChat);
            document.getElementById('chat-' + currentChat).style.display = 'none';
            document.querySelectorAll('.contact-item')[currentChat].classList.remove('active');
            document.getElementById('chat-' + index).style.display = 'flex';
            document.querySelectorAll('.contact-item')[index].classList.add('active');
            currentChat = index;
            applyDateFilterToMessages(index);
            if (disappearingFilterActive) {{
                updateDisappearingHeaderCount(index);
            }}
            setupAudioLazyLoad();
            setupVideoLazyLoad();
            __setupAutoLoadObserver(index);
            __restoreScroll(index);
        }}

        // Phase 7.1 — Auto-load next batch when load-more button is near viewport
        const __autoLoadObservers = new Map();
        function __setupAutoLoadObserver(chatIndex) {{
            if (__autoLoadObservers.has(chatIndex)) return;
            const btn = document.getElementById('load-more-' + chatIndex);
            if (!btn || !('IntersectionObserver' in window)) return;
            const chatDiv = document.getElementById('chat-' + chatIndex);
            const root = chatDiv ? chatDiv.querySelector('.chat-messages') : null;
            const obs = new IntersectionObserver((entries) => {{
                for (const e of entries) {{
                    if (e.isIntersecting) {{
                        loadMoreMessages(chatIndex);
                    }}
                }}
            }}, {{ root: root, rootMargin: '500px 0px 0px 0px', threshold: 0.01 }});
            obs.observe(btn);
            __autoLoadObservers.set(chatIndex, obs);
        }}

        function loadMoreMessages(chatIndex) {{
            const BATCH = 200;
            const chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            const hidden = chatDiv.querySelectorAll('[data-paginated="true"]');
            if (hidden.length === 0) {{
                const btn = document.getElementById('load-more-' + chatIndex);
                if (btn) btn.style.display = 'none';
                return;
            }}
            // Reveal last BATCH hidden items (closest to visible area)
            const start = Math.max(0, hidden.length - BATCH);
            for (let i = start; i < hidden.length; i++) {{
                hidden[i].style.display = '';
                hidden[i].removeAttribute('data-paginated');
            }}
            setupAudioLazyLoad();
            setupVideoLazyLoad();
            // Update button text with remaining count
            const remaining = start;
            const btn = document.getElementById('load-more-' + chatIndex);
            if (remaining <= 0) {{
                if (btn) btn.style.display = 'none';
            }} else if (btn) {{
                btn.querySelector('button').textContent = '⬆️ Carregar ' + remaining + ' mensagens anteriores';
            }}
            // Scroll to top of newly revealed messages
            chatDiv.querySelector('.chat-messages').scrollTop = 0;
        }}

        function applyDateFilterToMessages(chatIndex) {{
            const dateStart = document.getElementById('date-start').value;
            const dateEnd = document.getElementById('date-end').value;
            const chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;

            const messages = chatDiv.querySelectorAll('.message, .date-separator');
            let firstVisibleMessage = null;
            let hasVisibleMessages = false;

            messages.forEach(el => {{
                const msgDate = el.dataset.date;
                if (!dateStart && !dateEnd) {{
                    el.style.display = '';
                    if (!firstVisibleMessage && el.classList.contains('message')) {{
                        firstVisibleMessage = el;
                    }}
                    hasVisibleMessages = true;
                    return;
                }}
                if (!msgDate) {{
                    el.style.display = 'none';
                    return;
                }}
                let inRange = true;
                if (dateStart && msgDate < dateStart) inRange = false;
                if (dateEnd && msgDate > dateEnd) inRange = false;
                if (inRange) {{
                    el.style.display = '';
                    if (!firstVisibleMessage && el.classList.contains('message')) {{
                        firstVisibleMessage = el;
                    }}
                    hasVisibleMessages = true;
                }} else {{
                    el.style.display = 'none';
                }}
            }});

            if (firstVisibleMessage) {{
                setTimeout(() => {{
                    firstVisibleMessage.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                }}, 100);
            }}
        }}

        function filterContacts(query) {{
            const contacts = document.querySelectorAll('.contact-item');
            query = query.toLowerCase();
            const dateStart = document.getElementById('date-start').value;
            const dateEnd = document.getElementById('date-end').value;

            contacts.forEach(contact => {{
                const name = contact.querySelector('.contact-name').textContent.toLowerCase();
                const username = contact.querySelector('.contact-username') ? contact.querySelector('.contact-username').textContent.toLowerCase() : '';
                const preview = contact.querySelector('.contact-preview').textContent.toLowerCase();
                const contactStart = contact.dataset.start;
                const contactEnd = contact.dataset.end;

                let matchesText = !query || name.includes(query) || username.includes(query) || preview.includes(query);
                let matchesDate = true;
                if (dateStart && dateStart !== '') {{
                    if (!contactEnd || contactEnd < dateStart) matchesDate = false;
                }}
                if (dateEnd && dateEnd !== '') {{
                    if (!contactStart || contactStart > dateEnd) matchesDate = false;
                }}

                contact.style.display = (matchesText && matchesDate) ? 'flex' : 'none';
            }});
        }}

        function filterByDate() {{
            const query = document.getElementById('search-input').value;
            filterContacts(query);
            applyDateFilterToMessages(currentChat);
            const dateStart = document.getElementById('date-start').value;
            const dateEnd = document.getElementById('date-end').value;
            const hasDateFilter = (dateStart && dateStart !== '') || (dateEnd && dateEnd !== '');
            document.querySelectorAll('.contact-time').forEach(el => {{
                el.style.display = hasDateFilter ? 'none' : '';
            }});
            updateMessageCounts(dateStart, dateEnd);
        }}

        function updateMessageCounts(dateStart, dateEnd) {{
            const contacts = document.querySelectorAll('.contact-item');
            const hasFilter = (dateStart && dateStart !== '') || (dateEnd && dateEnd !== '');

            contacts.forEach((contact, index) => {{
                const countEl = contact.querySelector('.contact-count');
                const headerCountEl = document.getElementById('chat-msg-count-' + index);
                if (!countEl) return;
                if (!hasFilter) {{
                    countEl.textContent = countEl.dataset.total;
                    if (headerCountEl) headerCountEl.textContent = '📝 ' + headerCountEl.dataset.total + ' mensagens';
                    return;
                }}
                const chatDiv = document.getElementById('chat-' + index);
                if (!chatDiv) return;
                const messages = chatDiv.querySelectorAll('.message');
                let count = 0;
                messages.forEach(msg => {{
                    const msgDate = msg.dataset.date;
                    if (!msgDate) return;
                    let inRange = true;
                    if (dateStart && msgDate < dateStart) inRange = false;
                    if (dateEnd && msgDate > dateEnd) inRange = false;
                    if (inRange) count++;
                }});
                countEl.textContent = count;
                if (headerCountEl) headerCountEl.textContent = '📝 ' + count + ' mensagens no período';
            }});
        }}

        function clearDateFilter() {{
            document.getElementById('date-start').value = '';
            document.getElementById('date-end').value = '';
            document.getElementById('search-messages').value = '';
            messageSearchTerm = '';
            messageSearchRegex = null;
            foundMessages = {{}};
            foundWords = [];
            currentWordIndex = 0;
            currentSearchIndex = {{}};
            restoreOriginalContent();
            document.querySelectorAll('.search-highlight').forEach(el => el.classList.remove('search-highlight'));
            document.querySelectorAll('.search-nav').forEach(nav => nav.style.display = 'none');
            document.querySelectorAll('.search-badge').forEach(badge => badge.style.display = 'none');
            document.getElementById('search-input').value = '';
            document.querySelectorAll('.contact-item').forEach(c => c.style.display = 'flex');
            document.querySelectorAll('.message, .date-separator').forEach(el => el.style.display = '');
            // Preserve pagination: re-hide elements that were paginated out
            document.querySelectorAll('[data-paginated="true"]').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.contact-time').forEach(el => el.style.display = '');
            document.querySelectorAll('.contact-count').forEach(el => el.textContent = el.dataset.total);
            document.querySelectorAll('.chat-msg-count').forEach(el => el.textContent = '📝 ' + el.dataset.total + ' mensagens');
        }}

        // Busca global nas mensagens
        let messageSearchTerm = '';
        let messageSearchRegex = null;
        let foundMessages = {{}};
        let foundWords = [];
        let currentWordIndex = 0;
        let currentSearchIndex = {{}};
        let originalContents = new Map();

        function searchInMessages(query) {{
            messageSearchTerm = query.toLowerCase().trim();
            const contacts = document.querySelectorAll('.contact-item');
            foundMessages = {{}};
            foundWords = [];
            currentWordIndex = 0;
            currentSearchIndex = {{}};
            restoreOriginalContent();
            document.querySelectorAll('.search-highlight').forEach(el => el.classList.remove('search-highlight'));
            document.querySelectorAll('.search-nav').forEach(nav => nav.style.display = 'none');

            if (!messageSearchTerm) {{
                contacts.forEach(c => {{
                    c.style.display = 'flex';
                    const badge = c.querySelector('.search-badge');
                    if (badge) badge.style.display = 'none';
                }});
                return;
            }}

            const escaped = messageSearchTerm.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
            messageSearchRegex = new RegExp('\\\\b(' + escaped + ')\\\\b', 'gi');
            const testRegex = new RegExp('\\\\b' + escaped + '\\\\b', 'i');

            contacts.forEach((contact, index) => {{
                const chatDiv = document.getElementById('chat-' + index);
                if (!chatDiv) return;
                const messages = chatDiv.querySelectorAll('.message');
                let found = false;
                foundMessages[index] = [];
                currentSearchIndex[index] = 0;

                messages.forEach(msg => {{
                    const content = msg.querySelector('.message-content');
                    const transcription = msg.querySelector('.transcription-text');
                    let hasMatch = false;
                    if (content && testRegex.test(content.textContent)) {{
                        hasMatch = true;
                        highlightWordsInElement(content, messageSearchRegex);
                    }}
                    if (transcription && testRegex.test(transcription.textContent)) {{
                        hasMatch = true;
                        highlightWordsInElement(transcription, messageSearchRegex);
                    }}
                    if (hasMatch) {{
                        found = true;
                        foundMessages[index].push(msg);
                    }}
                }});

                if (found) {{
                    contact.style.display = 'flex';
                    let badge = contact.querySelector('.search-badge');
                    if (!badge) {{
                        badge = document.createElement('span');
                        badge.className = 'search-badge';
                        contact.querySelector('.contact-meta').appendChild(badge);
                    }}
                    badge.textContent = foundMessages[index].length;
                    badge.style.display = 'inline-block';
                }} else {{
                    contact.style.display = 'none';
                    const badge = contact.querySelector('.search-badge');
                    if (badge) badge.style.display = 'none';
                }}
            }});

            foundWords = Array.from(document.querySelectorAll('.word-highlight'));
            currentWordIndex = 0;
            if (foundWords.length > 0) {{
                foundWords[0].classList.add('current');
            }}
        }}

        function highlightWordsInElement(element, regex) {{
            if (!originalContents.has(element)) {{
                originalContents.set(element, element.innerHTML);
            }}
            const html = element.innerHTML;
            const newHtml = html.replace(regex, '<span class="word-highlight">$1</span>');
            element.innerHTML = newHtml;
        }}

        function restoreOriginalContent() {{
            originalContents.forEach((originalHtml, element) => {{
                if (element && element.parentNode) {{
                    element.innerHTML = originalHtml;
                }}
            }});
            originalContents.clear();
        }}

        function updateSearchNav(chatIndex) {{
            const nav = document.getElementById('search-nav-' + chatIndex);
            const info = document.getElementById('search-nav-info-' + chatIndex);
            const chatDiv = document.getElementById('chat-' + chatIndex);
            const wordsInChat = chatDiv ? chatDiv.querySelectorAll('.word-highlight').length : 0;

            if (wordsInChat > 0) {{
                nav.style.display = 'flex';
                const currentInChat = chatDiv.querySelector('.word-highlight.current');
                const allInChat = Array.from(chatDiv.querySelectorAll('.word-highlight'));
                const currentIdx = currentInChat ? allInChat.indexOf(currentInChat) + 1 : 1;
                info.textContent = currentIdx + '/' + wordsInChat;
            }} else {{
                nav.style.display = 'none';
            }}
        }}

        function navSearchPrev(chatIndex) {{
            const chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            const wordsInChat = Array.from(chatDiv.querySelectorAll('.word-highlight'));
            if (wordsInChat.length === 0) return;
            let currentIdx = wordsInChat.findIndex(w => w.classList.contains('current'));
            if (currentIdx === -1) currentIdx = 0;
            wordsInChat[currentIdx].classList.remove('current');
            const newIdx = (currentIdx - 1 + wordsInChat.length) % wordsInChat.length;
            const targetWord = wordsInChat[newIdx];
            targetWord.classList.add('current');
            targetWord.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            const parentMsg = targetWord.closest('.message');
            document.querySelectorAll('.search-highlight').forEach(el => el.classList.remove('search-highlight'));
            if (parentMsg) parentMsg.classList.add('search-highlight');
            updateSearchNav(chatIndex);
        }}

        function navSearchNext(chatIndex) {{
            const chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            const wordsInChat = Array.from(chatDiv.querySelectorAll('.word-highlight'));
            if (wordsInChat.length === 0) return;
            let currentIdx = wordsInChat.findIndex(w => w.classList.contains('current'));
            if (currentIdx === -1) currentIdx = -1;
            if (currentIdx >= 0) wordsInChat[currentIdx].classList.remove('current');
            const newIdx = (currentIdx + 1) % wordsInChat.length;
            const targetWord = wordsInChat[newIdx];
            targetWord.classList.add('current');
            targetWord.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            const parentMsg = targetWord.closest('.message');
            document.querySelectorAll('.search-highlight').forEach(el => el.classList.remove('search-highlight'));
            if (parentMsg) parentMsg.classList.add('search-highlight');
            updateSearchNav(chatIndex);
        }}

        let detailsVisible = {{}};

        const originalShowChat = showChat;
        showChat = function(index) {{
            originalShowChat(index);
            if (messageSearchTerm && foundMessages[index] && foundMessages[index].length > 0) {{
                const chatDiv = document.getElementById('chat-' + index);
                if (chatDiv) {{
                    document.querySelectorAll('.word-highlight.current').forEach(w => w.classList.remove('current'));
                    const firstWord = chatDiv.querySelector('.word-highlight');
                    if (firstWord) {{
                        firstWord.classList.add('current');
                        setTimeout(() => {{
                            firstWord.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}, 100);
                        const parentMsg = firstWord.closest('.message');
                        if (parentMsg) parentMsg.classList.add('search-highlight');
                    }}
                    updateSearchNav(index);
                }}
            }}
            const btn = document.getElementById('btn-details-' + index);
            if (btn) {{
                if (detailsVisible[index]) {{
                    btn.classList.add('active');
                    btn.textContent = '✅ Detalhes visíveis';
                }} else {{
                    btn.classList.remove('active');
                    btn.textContent = 'ℹ️ Ver detalhes';
                }}
            }}
        }};

        function openLightbox(src) {{
            const lightbox = document.querySelector('.lightbox');
            lightbox.querySelector('img').src = src;
            lightbox.classList.add('active');
        }}

        function syncAudioSpeed(container, speed) {{
            container.querySelectorAll('button[data-playback-rate]').forEach(button => {{
                const active = Number(button.dataset.playbackRate) === speed;
                button.classList.toggle('active', active);
                button.setAttribute('aria-pressed', String(active));
            }});
        }}

        function setAudioSpeed(container, speed) {{
            if (![1, 1.5, 2].includes(speed)) return;
            const audio = document.getElementById(container.dataset.audioId);
            if (!(audio instanceof HTMLMediaElement)) return;
            audio.playbackRate = speed;
            syncAudioSpeed(container, speed);
        }}

        document.addEventListener('click', event => {{
            if (!(event.target instanceof Element)) return;
            const button = event.target.closest('.audio-speed button[data-playback-rate]');
            if (!button) return;
            const container = button.closest('.audio-speed');
            if (!container) return;
            setAudioSpeed(container, Number(button.dataset.playbackRate));
        }});

        document.querySelectorAll('audio').forEach(audio => {{
            audio.addEventListener('ratechange', () => {{
                const container = document.querySelector('.audio-speed[data-audio-id="' + audio.id + '"]');
                if (container) syncAudioSpeed(container, audio.playbackRate);
            }});
        }});

        // ===== FILTRO DE MENSAGENS TEMPORÁRIAS =====
        function toggleDisappearingFilter() {{
            const btn = document.getElementById('btn-filter-disappearing');
            disappearingFilterActive = !disappearingFilterActive;
            const contacts = document.querySelectorAll('.contact-item');
            const allDateSeps = document.querySelectorAll('.date-separator');
            let totalDisappearing = 0;
            disappearingByChat = {{}};

            if (disappearingFilterActive) {{
                contacts.forEach((contact, index) => {{
                    const chatDiv = document.getElementById('chat-' + index);
                    if (!chatDiv) return;
                    const messages = chatDiv.querySelectorAll('.message');
                    let countInChat = 0;
                    messages.forEach(msg => {{
                        if (msg.dataset.disappearing === 'true') {{
                            msg.classList.remove('disappearing-hidden');
                            countInChat++;
                            totalDisappearing++;
                        }} else {{
                            msg.classList.add('disappearing-hidden');
                        }}
                    }});
                    disappearingByChat[index] = countInChat;
                    if (countInChat > 0) {{
                        contact.style.display = 'flex';
                        let badge = contact.querySelector('.disappearing-badge-count');
                        if (!badge) {{
                            badge = document.createElement('span');
                            badge.className = 'disappearing-badge-count';
                            contact.querySelector('.contact-meta').appendChild(badge);
                        }}
                        badge.textContent = '⏱️ ' + countInChat;
                        badge.style.display = 'inline-block';
                    }} else {{
                        contact.style.display = 'none';
                        const badge = contact.querySelector('.disappearing-badge-count');
                        if (badge) badge.style.display = 'none';
                    }}
                }});
                allDateSeps.forEach(sep => sep.classList.add('disappearing-hidden'));
                btn.classList.add('active');
                btn.textContent = '⏱️ Temporárias (' + totalDisappearing + ')';
                updateDisappearingHeaderCount(currentChat);
            }} else {{
                contacts.forEach((contact, index) => {{
                    const chatDiv = document.getElementById('chat-' + index);
                    if (!chatDiv) return;
                    chatDiv.querySelectorAll('.message').forEach(msg => msg.classList.remove('disappearing-hidden'));
                    contact.style.display = 'flex';
                    const badge = contact.querySelector('.disappearing-badge-count');
                    if (badge) badge.style.display = 'none';
                }});
                allDateSeps.forEach(sep => sep.classList.remove('disappearing-hidden'));
                btn.classList.remove('active');
                btn.textContent = '⏱️ Temporárias';
                const headerCountEl = document.getElementById('chat-msg-count-' + currentChat);
                if (headerCountEl) headerCountEl.textContent = '📝 ' + headerCountEl.dataset.total + ' mensagens';
            }}
        }}

        function updateDisappearingHeaderCount(chatIndex) {{
            if (!disappearingFilterActive) return;
            const headerCountEl = document.getElementById('chat-msg-count-' + chatIndex);
            if (headerCountEl && disappearingByChat[chatIndex] !== undefined) {{
                headerCountEl.textContent = '⏱️ ' + disappearingByChat[chatIndex] + ' temporárias';
            }}
        }}

        // ===== OCULTAR/MOSTRAR ÍCONE DE TEMPORÁRIAS =====
        function toggleDisappearingIcon() {{
            const btn = document.getElementById('btn-toggle-disappearing-icon');
            disappearingIconHidden = !disappearingIconHidden;
            const allBadges = document.querySelectorAll('.disappearing-badge');
            if (disappearingIconHidden) {{
                allBadges.forEach(badge => badge.style.display = 'none');
                btn.classList.add('active');
                btn.innerHTML = 'Mostrar ícones<br>das mensagens temporárias';
            }} else {{
                allBadges.forEach(badge => badge.style.display = '');
                btn.classList.remove('active');
                btn.innerHTML = 'Ocultar ícones<br>das mensagens temporárias';
            }}
        }}

        // ===== DETALHES/ORIGEM DAS MENSAGENS =====
        function toggleDetails(chatIndex) {{
            const btn = document.getElementById('btn-details-' + chatIndex);
            const chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            detailsVisible[chatIndex] = !detailsVisible[chatIndex];
            if (detailsVisible[chatIndex]) {{
                chatDiv.classList.add('details-visible');
                btn.classList.add('active');
                btn.textContent = '✅ Detalhes visíveis';
            }} else {{
                chatDiv.classList.remove('details-visible');
                btn.classList.remove('active');
                btn.textContent = 'ℹ️ Ver detalhes';
            }}
        }}

        // ===== MEDIA GALLERY FUNCTIONS =====
        function openMediaGallery(chatIndex) {{
            const gallery = document.getElementById('media-gallery-' + chatIndex);
            if (gallery) {{
                gallery.classList.add('active');
                const allBtn = gallery.querySelector('.media-filter-btn');
                if (allBtn) filterMedia(chatIndex, 'all', allBtn);
            }}
        }}

        function closeMediaGallery(chatIndex) {{
            const gallery = document.getElementById('media-gallery-' + chatIndex);
            if (gallery) {{
                gallery.classList.remove('active');
                gallery.querySelectorAll('audio, video').forEach(media => media.pause());
            }}
        }}

        function filterMedia(chatIndex, type, btn) {{
            const gallery = document.getElementById('media-gallery-' + chatIndex);
            if (!gallery) return;
            gallery.querySelectorAll('.media-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            gallery.querySelectorAll('.media-gallery-item').forEach(item => {{
                item.style.display = (type === 'all' || item.dataset.type === type) ? '' : 'none';
            }});
        }}

        function scrollToMessage(msgId) {{
            const msg = document.getElementById(msgId);
            if (!msg) return;
            msg.style.display = '';
            msg.classList.remove('disappearing-hidden');
            msg.scrollIntoView({{ behavior: 'auto', block: 'center' }});
            msg.style.outline = '5px solid #a855f7';
            msg.style.outlineOffset = '5px';
            msg.style.backgroundColor = '#f3e8ff';
            msg.style.boxShadow = '0 0 30px rgba(168, 85, 247, 0.7)';
            setTimeout(() => {{
                msg.style.outline = '';
                msg.style.outlineOffset = '';
                msg.style.backgroundColor = '';
                msg.style.boxShadow = '';
            }}, 5000);
        }}

        function goToMediaMessage(chatIndex, msgId) {{
            closeMediaGallery(chatIndex);
            setTimeout(() => scrollToMessage(msgId), 300);
        }}

        // ===== GALERIA GLOBAL DE MÍDIAS =====
        function openGlobalMediaGallery() {{
            const gallery = document.getElementById('global-media-gallery');
            if (gallery) {{
                gallery.classList.add('active');
                const allBtn = gallery.querySelector('.media-filter-btn');
                if (allBtn) filterGlobalMedia('all', allBtn);
            }}
        }}

        function closeGlobalMediaGallery() {{
            const gallery = document.getElementById('global-media-gallery');
            if (gallery) {{
                gallery.classList.remove('active');
                gallery.querySelectorAll('audio, video').forEach(media => media.pause());
            }}
        }}

        function filterGlobalMedia(type, btn) {{
            const gallery = document.getElementById('global-media-gallery');
            if (!gallery) return;
            gallery.querySelectorAll('.media-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            gallery.querySelectorAll('.media-gallery-item').forEach(item => {{
                item.style.display = (type === 'all' || item.dataset.type === type) ? '' : 'none';
            }});
        }}

        function goToGlobalMediaMessage(chatIndex, msgId) {{
            closeGlobalMediaGallery();
            showChat(chatIndex);
            setTimeout(() => scrollToMessage(msgId), 500);
        }}

        // Fechar galeria ao clicar fora do painel
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('media-gallery-overlay')) {{
                e.target.classList.remove('active');
                e.target.querySelectorAll('audio, video').forEach(media => media.pause());
            }}
        }});

        // Fechar galeria com ESC
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                document.querySelectorAll('.media-gallery-overlay.active').forEach(g => {{
                    g.classList.remove('active');
                    g.querySelectorAll('audio, video').forEach(media => media.pause());
                }});
            }}
        }});

        // Lazy load de metadados de áudio
        const audioObserver = 'IntersectionObserver' in window ? new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    const audio = entry.target;
                    if (audio.preload === 'none') audio.preload = 'metadata';
                    audioObserver.unobserve(audio);
                }}
            }});
        }}, {{ rootMargin: '100px' }}) : null;

        function setupAudioLazyLoad() {{
            document.querySelectorAll('audio').forEach(audio => {{
                if (audioObserver) {{
                    audioObserver.observe(audio);
                }} else if (audio.preload === 'none') {{
                    audio.preload = 'metadata';
                }}
            }});
        }}

        // Lazy load de vídeos
        const videoObserver = 'IntersectionObserver' in window ? new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    const video = entry.target;
                    if (video.dataset.src && !video.src) {{
                        video.src = video.dataset.src;
                        video.preload = 'metadata';
                    }}
                    videoObserver.unobserve(video);
                }}
            }});
        }}, {{ rootMargin: '200px' }}) : null;

        function setupVideoLazyLoad() {{
            document.querySelectorAll('video.lazy-video').forEach(video => {{
                if (videoObserver) {{
                    videoObserver.observe(video);
                }} else if (video.dataset.src && !video.src) {{
                    video.src = video.dataset.src;
                    video.preload = 'metadata';
                }}
            }});
        }}

        // Pausar outros áudios/vídeos quando um novo é iniciado
        let currentlyPlaying = null;

        function setupMediaExclusivity() {{
            const allMedia = document.querySelectorAll('audio, video');
            allMedia.forEach(media => {{
                media.addEventListener('play', function() {{
                    if (currentlyPlaying && currentlyPlaying !== this) currentlyPlaying.pause();
                    currentlyPlaying = this;
                }});
                media.addEventListener('ended', function() {{
                    if (currentlyPlaying === this) currentlyPlaying = null;
                }});
                media.addEventListener('error', function(e) {{
                    console.error('Erro ao carregar mídia:', this.src, e);
                    const container = this.closest('.audio-container, .gallery-audio-container');
                    if (!container || container.dataset.loadError === '1') return;
                    container.dataset.loadError = '1';
                    const source = this.querySelector('source');
                    const notice = document.createElement('div');
                    notice.style.cssText = 'color:#c00;padding:10px;font-size:12px;';
                    notice.append('⚠️ Erro ao carregar áudio. ');
                    if (source && source.src) {{
                        const link = document.createElement('a');
                        link.href = source.src;
                        link.target = '_blank';
                        link.rel = 'noopener noreferrer';
                        link.style.color = '#555';
                        link.textContent = 'Abrir arquivo';
                        notice.appendChild(link);
                    }}
                    container.replaceChildren(notice);
                }});
            }});
        }}

        // Configurar quando a página carrega
        document.addEventListener('DOMContentLoaded', function() {{
            setupVideoLazyLoad();
            if ('requestIdleCallback' in window) {{
                requestIdleCallback(function() {{
                    setupMediaExclusivity();
                    setupAudioLazyLoad();
                }}, {{ timeout: 2000 }});
            }} else {{
                setTimeout(function() {{
                    setupMediaExclusivity();
                    setupAudioLazyLoad();
                }}, 100);
            }}
        }});

        // ===== DARK MODE =====
        function toggleDarkMode() {{
            document.body.classList.toggle('dark-mode');
            const btn = document.getElementById('btn-dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            btn.classList.toggle('active', isDark);
            btn.textContent = isDark ? '☀️ Modo Claro' : '🌙 Modo Escuro';
            try {{ localStorage.setItem('dark-mode', isDark ? '1' : '0'); }} catch(e) {{}}
        }}
        // Restaurar preferência salva
        try {{
            if (localStorage.getItem('dark-mode') === '1') {{
                document.body.classList.add('dark-mode');
                const btn = document.getElementById('btn-dark-mode');
                if (btn) {{ btn.classList.add('active'); btn.textContent = '☀️ Modo Claro'; }}
            }}
        }} catch(e) {{}}

        // ===== ESTATÍSTICAS =====
        {stats_js}

        // ===== MÍDIAS DO PERFIL =====
        {profile_media_js}

        // ===== SIDEBAR MOBILE TOGGLE =====
        function toggleSidebar() {{
            var sidebar = document.querySelector('.sidebar');
            var overlay = document.querySelector('.sidebar-overlay');
            var btn = document.querySelector('.sidebar-toggle');
            if (sidebar && overlay) {{
                sidebar.classList.toggle('open');
                overlay.classList.toggle('open');
                btn.textContent = sidebar.classList.contains('open') ? '✕' : '☰';
            }}
        }}

        // ===== KEYBOARD SHORTCUTS =====
        document.addEventListener('keydown', function(e) {{
            // Ctrl+K or Cmd+K: focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{
                e.preventDefault();
                var searchInput = document.querySelector('.sidebar-search input');
                if (searchInput) {{
                    // On mobile, open sidebar first
                    var sidebar = document.querySelector('.sidebar');
                    if (sidebar && window.innerWidth <= 768 && !sidebar.classList.contains('open')) {{
                        toggleSidebar();
                    }}
                    searchInput.focus();
                }}
            }}
            // Ctrl+D or Cmd+D: toggle dark mode
            if ((e.ctrlKey || e.metaKey) && e.key === 'd') {{
                e.preventDefault();
                toggleDarkMode();
            }}
            // Escape: close any open panel or sidebar
            if (e.key === 'Escape') {{
                // Close mobile sidebar
                var sidebar = document.querySelector('.sidebar.open');
                if (sidebar) {{ toggleSidebar(); return; }}
                // Close lightbox
                var lb = document.querySelector('.lightbox');
                if (lb && lb.style.display !== 'none') {{ lb.style.display = 'none'; return; }}
                // Close media galleries
                var galleries = document.querySelectorAll('.media-gallery-overlay');
                for (var i = 0; i < galleries.length; i++) {{
                    if (galleries[i].style.display !== 'none' && galleries[i].classList.contains('active')) {{
                        galleries[i].classList.remove('active');
                        return;
                    }}
                }}
            }}
            // Arrow keys: navigate contacts when sidebar is focused
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {{
                var active = document.activeElement;
                if (active && active.closest && active.closest('.sidebar')) {{
                    var items = Array.from(document.querySelectorAll('.contact-item'));
                    if (items.length === 0) return;
                    var currentIdx = items.indexOf(document.querySelector('.contact-item.active'));
                    var nextIdx;
                    if (e.key === 'ArrowDown') {{
                        nextIdx = currentIdx < items.length - 1 ? currentIdx + 1 : 0;
                    }} else {{
                        nextIdx = currentIdx > 0 ? currentIdx - 1 : items.length - 1;
                    }}
                    items[nextIdx].click();
                    items[nextIdx].scrollIntoView({{ block: 'nearest' }});
                    e.preventDefault();
                }}
            }}
            // Phase 7.5 — End / Home / PageUp / PageDown for chat navigation
            var tag = (document.activeElement && document.activeElement.tagName) || '';
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
            var activeChat = document.getElementById('chat-' + currentChat);
            if (!activeChat) return;
            var msgsContainer = activeChat.querySelector('.chat-messages');
            if (!msgsContainer) return;
            if (e.key === 'End') {{
                e.preventDefault();
                msgsContainer.scrollTop = msgsContainer.scrollHeight;
            }} else if (e.key === 'Home') {{
                e.preventDefault();
                // Revelar lotes paginados antes de ir ao topo
                while (msgsContainer.querySelector('[data-paginated="true"]')) {{
                    loadMoreMessages(currentChat);
                }}
                msgsContainer.scrollTop = 0;
            }} else if (e.key === 'PageDown') {{
                e.preventDefault();
                msgsContainer.scrollBy({{ top: msgsContainer.clientHeight * 0.8, behavior: 'smooth' }});
            }} else if (e.key === 'PageUp') {{
                e.preventDefault();
                msgsContainer.scrollBy({{ top: -msgsContainer.clientHeight * 0.8, behavior: 'smooth' }});
            }}
        }});

        // ============================================
        // Phase 7.2 — Copy-to-clipboard em mensagens
        // ============================================
        function __copyMsgText(msgEl) {{
            if (!msgEl) return;
            var contentEl = msgEl.querySelector('.message-content');
            var text = contentEl ? contentEl.textContent : msgEl.textContent;
            text = (text || '').trim();
            if (!text) return;
            try {{
                navigator.clipboard.writeText(text).then(__showToast, () => __fallbackCopy(text));
            }} catch (err) {{
                __fallbackCopy(text);
            }}
        }}
        function __fallbackCopy(text) {{
            var ta = document.createElement('textarea');
            ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
            document.body.appendChild(ta); ta.select();
            try {{ document.execCommand('copy'); __showToast(); }} catch (e) {{}}
            document.body.removeChild(ta);
        }}
        function __showToast() {{
            var t = document.getElementById('__toast');
            if (!t) {{
                t = document.createElement('div'); t.id = '__toast';
                t.className = 'toast-copy'; t.textContent = '✅ Copiado!';
                document.body.appendChild(t);
            }}
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 1500);
        }}
        // Event delegation: clique no botão .msg-copy-btn
        document.addEventListener('click', function(e) {{
            var btn = e.target.closest && e.target.closest('.msg-copy-btn');
            if (!btn) return;
            e.stopPropagation();
            var msg = btn.closest('.message');
            __copyMsgText(msg);
        }});
        // Long-press mobile: 500ms
        (function setupLongPress() {{
            var timer = null, pressed = null;
            document.addEventListener('touchstart', function(e) {{
                var msg = e.target.closest && e.target.closest('.message');
                if (!msg) return;
                pressed = msg;
                timer = setTimeout(() => {{
                    __copyMsgText(pressed);
                    pressed = null;
                }}, 500);
            }}, {{ passive: true }});
            document.addEventListener('touchend', function() {{
                if (timer) {{ clearTimeout(timer); timer = null; }}
                pressed = null;
            }}, {{ passive: true }});
            document.addEventListener('touchmove', function() {{
                if (timer) {{ clearTimeout(timer); timer = null; }}
            }}, {{ passive: true }});
        }})();

        // ============================================
        // Phase 7.3 — Jump-to-date picker
        // ============================================
        function __jumpToDate(chatIndex, dateStr) {{
            if (!dateStr) return;
            var chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            // Revelar lotes paginados até encontrar a data alvo
            var target = null, guard = 0;
            while (guard < 50) {{
                target = chatDiv.querySelector('.message[data-date="' + dateStr + '"], .date-separator[data-date="' + dateStr + '"]');
                if (target) break;
                // Se ainda há paginados, revelar mais
                if (chatDiv.querySelector('[data-paginated="true"]')) {{
                    loadMoreMessages(chatIndex);
                    guard++;
                }} else {{
                    break;
                }}
            }}
            if (!target) {{
                // Fallback: buscar primeiro com data >= alvo
                var all = chatDiv.querySelectorAll('.message[data-date]');
                for (var i = 0; i < all.length; i++) {{
                    if (all[i].dataset.date >= dateStr) {{ target = all[i]; break; }}
                }}
            }}
            if (target) {{
                target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                target.classList.add('jump-highlight');
                setTimeout(() => target.classList.remove('jump-highlight'), 2000);
            }}
        }}
        function toggleDatePicker(chatIndex) {{
            var popover = document.getElementById('date-picker-' + chatIndex);
            if (popover) popover.classList.toggle('open');
        }}
        // Close popover on outside click
        document.addEventListener('click', function(e) {{
            if (e.target.closest && e.target.closest('.date-picker-popover')) return;
            if (e.target.closest && e.target.closest('.btn-date-picker')) return;
            document.querySelectorAll('.date-picker-popover.open').forEach(p => p.classList.remove('open'));
        }});

        // ============================================
        // Phase 7.6 — Compact mode toggle
        // ============================================
        function toggleCompactMode() {{
            var body = document.body;
            body.classList.toggle('compact-mode');
            var isCompact = body.classList.contains('compact-mode');
            var btn = document.getElementById('btn-compact-mode');
            if (btn) btn.classList.toggle('active', isCompact);
            try {{ localStorage.setItem('compact-mode', isCompact ? '1' : '0'); }} catch (e) {{}}
        }}
        try {{
            if (localStorage.getItem('compact-mode') === '1') {{
                document.body.classList.add('compact-mode');
                var btn = document.getElementById('btn-compact-mode');
                if (btn) btn.classList.add('active');
            }}
        }} catch (e) {{}}

        // ============================================
        // Phase 8.1 — Export chat as PDF (via window.print)
        // ============================================
        function exportChatPDF(chatIndex) {{
            // Revelar todas as mensagens paginadas do chat atual antes de imprimir
            var chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return;
            var safety = 100;
            while (chatDiv.querySelector('[data-paginated="true"]') && safety > 0) {{
                loadMoreMessages(chatIndex);
                safety--;
            }}
            // Ajustar título da aba para gerar nome de arquivo PDF melhor
            var origTitle = document.title;
            var nameEl = chatDiv.querySelector('.chat-header-name');
            if (nameEl) {{
                document.title = 'Conversa - ' + nameEl.textContent.trim();
            }}
            // Disparar impressão após pequeno delay para garantir render
            setTimeout(function() {{
                window.print();
                document.title = origTitle;
            }}, 300);
        }}

        // ============================================
        // Phase 8.4 — Mini-stats por conversa (client-side)
        // ============================================
        function toggleChatStats(chatIndex) {{
            var panel = document.getElementById('chat-mini-stats-' + chatIndex);
            if (!panel) return;
            if (panel.style.display !== 'none' && panel.dataset.loaded === '1') {{
                panel.style.display = 'none';
                return;
            }}
            if (panel.dataset.loaded !== '1') {{
                panel.innerHTML = __computeChatStats(chatIndex);
                panel.dataset.loaded = '1';
            }}
            panel.style.display = 'block';
        }}
        function __computeChatStats(chatIndex) {{
            var chatDiv = document.getElementById('chat-' + chatIndex);
            if (!chatDiv) return '';
            // Revelar todas as mensagens antes de contar (para stats completas)
            var safety = 100;
            while (chatDiv.querySelector('[data-paginated="true"]') && safety > 0) {{
                loadMoreMessages(chatIndex);
                safety--;
            }}
            var msgs = chatDiv.querySelectorAll('.message');
            var sent = 0, received = 0;
            var hourBuckets = new Array(24).fill(0);
            var authorCounts = {{}};
            var firstDate = null, lastDate = null;
            msgs.forEach(function(m) {{
                if (m.classList.contains('sent')) sent++; else received++;
                // Autor
                var authorEl = m.querySelector('.message-author');
                var author = authorEl ? authorEl.textContent.trim() : (m.classList.contains('sent') ? 'Você' : 'Desconhecido');
                authorCounts[author] = (authorCounts[author] || 0) + 1;
                // Horário via tooltip do time? Usar data-date como proxy
                var date = m.dataset.date;
                if (date) {{
                    if (!firstDate || date < firstDate) firstDate = date;
                    if (!lastDate || date > lastDate) lastDate = date;
                    var timeEl = m.querySelector('.message-time');
                    if (timeEl) {{
                        var t = timeEl.textContent.match(/\\b(\\d{{2}}):\\d{{2}}/);
                        if (t) hourBuckets[parseInt(t[1], 10)]++;
                    }}
                }}
            }});
            var total = sent + received;
            var sentPct = total > 0 ? Math.round(sent / total * 100) : 0;
            var recvPct = 100 - sentPct;
            // Hora mais ativa
            var maxHour = 0, maxHourCount = 0;
            for (var h = 0; h < 24; h++) {{
                if (hourBuckets[h] > maxHourCount) {{ maxHourCount = hourBuckets[h]; maxHour = h; }}
            }}
            // Autor mais ativo
            var topAuthor = '', topCount = 0;
            Object.keys(authorCounts).forEach(function(a) {{
                if (authorCounts[a] > topCount) {{ topCount = authorCounts[a]; topAuthor = a; }}
            }});
            return (
                '<div class="chat-mini-stats-row">' +
                '<div class="chat-mini-stat">' +
                '<div class="chat-mini-stat-label">Total</div>' +
                '<div class="chat-mini-stat-value">' + total.toLocaleString() + '</div>' +
                '</div>' +
                '<div class="chat-mini-stat">' +
                '<div class="chat-mini-stat-label">Enviadas vs. Recebidas</div>' +
                '<div class="chat-mini-stat-value">' + sent + ' / ' + received + '</div>' +
                '<div class="chat-mini-stat-bar">' +
                '<div class="chat-mini-stat-bar-sent" style="width:' + sentPct + '%"></div>' +
                '<div class="chat-mini-stat-bar-received" style="width:' + recvPct + '%"></div>' +
                '</div>' +
                '</div>' +
                '<div class="chat-mini-stat">' +
                '<div class="chat-mini-stat-label">Hora mais ativa</div>' +
                '<div class="chat-mini-stat-value">' + (maxHourCount > 0 ? (maxHour + 'h (' + maxHourCount + ')') : '—') + '</div>' +
                '</div>' +
                '<div class="chat-mini-stat">' +
                '<div class="chat-mini-stat-label">Participante mais ativo</div>' +
                '<div class="chat-mini-stat-value">' + (topAuthor || '—') + '</div>' +
                '</div>' +
                '<div class="chat-mini-stat">' +
                '<div class="chat-mini-stat-label">Período</div>' +
                '<div class="chat-mini-stat-value">' + (firstDate && lastDate ? (firstDate + ' → ' + lastDate) : '—') + '</div>' +
                '</div>' +
                '</div>'
            );
        }}

        // Initialize auto-load observer for chat 0 after DOMContentLoaded
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', () => __setupAutoLoadObserver(0));
        }} else {{
            __setupAutoLoadObserver(0);
        }}
    </script>
</body>
</html>"""
