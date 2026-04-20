"""
Meta Platforms Chat Exporter - Widgets
Componentes visuais customizados para a interface (PyQt6)
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QBrush


class GradientProgressBar(QWidget):
    """Barra de progresso com gradiente moderno"""

    def __init__(self, parent=None, width=400, height=12):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._bar_width = width
        self._bar_height = height
        self._progress = 0.0
        self._target_progress = 0.0
        self._timer = None

        # Cores do gradiente (teal/turquesa)
        self.gradient_colors = [
            QColor("#0d5f5f"),  # Teal escuro
            QColor("#1a7a7a"),  # Teal base (cor da imagem)
            QColor("#259090"),  # Teal médio
            QColor("#30a5a5"),  # Teal claro
        ]

    def paintEvent(self, event):
        """Desenha a barra de progresso"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self._bar_width
        h = self._bar_height
        radius = 6.0

        # Fundo
        painter.setPen(QPen(QColor("#333333"), 1))
        painter.setBrush(QBrush(QColor("#1a1a1a")))
        painter.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), radius, radius)

        # Progresso
        if self._progress > 0:
            progress_width = max(12.0, (w - 4) * self._progress)

            # Criar gradiente
            gradient = QLinearGradient(2, 0, w - 2, 0)
            n = len(self.gradient_colors)
            for i, color in enumerate(self.gradient_colors):
                gradient.setColorAt(i / max(1, n - 1), color)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(QRectF(2, 2, progress_width, h - 4), radius, radius)

            # Brilho no topo
            highlight = QColor(255, 255, 255, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(highlight))
            painter.drawRoundedRect(QRectF(4, 3, min(progress_width - 4, w - 8), 3), 2, 2)

        painter.end()

    def set(self, value: float):
        """Define o progresso (0.0 a 1.0) com animação suave"""
        self._target_progress = max(0.0, min(1.0, value))
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._animate)
            self._timer.start(16)  # ~60fps

    def _animate(self):
        """Anima o progresso suavemente"""
        diff = self._target_progress - self._progress
        if abs(diff) > 0.001:
            self._progress += diff * 0.15  # Suavização
            self.update()
        else:
            self._progress = self._target_progress
            self.update()
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
