"""Shared Qt Widgets theme. No external assets or rendering dependencies."""

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPainterPath, QPen, QPixmap


class Theme:
    FONT = "Segoe UI"
    TEXT = "#242426"
    MUTED = "#717178"
    BORDER = "#E5E5E9"
    SURFACE = "#FFFFFF"
    SIDEBAR = "#F5F5F7"
    HOVER = "#F3F3F6"
    SELECTED = "#E9E9EE"
    ACCENT = "#C92532"
    SUCCESS = "#267049"
    WARNING = "#946516"
    INFO = "#396A9B"
    PAD = 24
    GAP = 12
    SIDEBAR_WIDTH = 232
    ROW_HEIGHT = 76
    TERMINAL_HEADER = 40


WORKSPACE_QSS = """
QWidget { font-family:"Segoe UI"; font-size:13px; color:#242426; }
QMainWindow, QWidget#workspace, QWidget#hub, QWidget#filesPage,
QWidget#listBody, QWidget#fileBody, QFrame#listPanel { background:#FFFFFF; }
QLabel { background:transparent; border:none; }
QLabel[role="title"] { font-size:26px; font-weight:600; }
QLabel[role="section"] { font-size:18px; font-weight:600; }
QLabel[role="secondary"] { color:#717178; font-size:12px; }
QLabel[role="eyebrow"] { color:#717178; font-size:11px; font-weight:600; }
QLabel[role="body"] { color:#515159; font-size:14px; }
QLabel[role="status"] { font-size:13px; font-weight:600; }
QLabel[tone="ready"] { color:#267049; }
QLabel[tone="warning"] { color:#946516; }
QLabel[tone="info"] { color:#396A9B; }
QLabel[tone="muted"] { color:#717178; }
QFrame#workspaceSidebar { background:#F5F5F7; border:0; border-right:1px solid #E5E5E9; }
QFrame#workspaceHeader { background:transparent; border:none; }
QFrame#detailPanel { background:#FAFAFC; border:0; }
QFrame#detailFooter { background:#FAFAFC; border:0; border-top:1px solid #E5E5E9; }
QWidget#detailBody { background:#FAFAFC; }
QFrame[role="separator"] { background:#E5E5E9; border:none; max-height:1px; }
QPushButton { background:#F0F0F4; border:1px solid transparent; border-radius:8px;
              padding:8px 14px; font-weight:600; }
QPushButton:hover { background:#E6E6EC; }
QPushButton:pressed { background:#DCDCE3; }
QPushButton:focus { border:1px solid #A1A1AC; }
QPushButton:disabled { background:#ECECF0; color:#91919A; }
QPushButton[role="primary"] { background:#C92532; color:white; }
QPushButton[role="primary"]:hover { background:#B11E2A; }
QPushButton[role="primary"]:disabled { background:#E5E5EA; color:#888892; }
QPushButton[role="navigation"] { background:transparent; color:#515159; text-align:left;
                                 padding:9px 12px; font-weight:500; }
QPushButton[role="navigation"]:hover { background:#ECECF0; }
QPushButton[role="navigation"]:checked { background:#E4E4EA; color:#242426; font-weight:600; }
QPushButton[role="activity"] { background:transparent; border-radius:9px; padding:0; }
QPushButton[role="activity"]:hover { background:#F3F3F6; }
QPushButton[role="activity"]:checked { background:#E9E9EE; }
QPushButton[role="iconButton"] { padding:4px; background:transparent; }
QPushButton[role="iconButton"]:hover { background:#F7E5E7; }
QLineEdit { background:#F2F2F6; border:1px solid transparent; border-radius:9px;
            padding:8px 10px; selection-background-color:#DCDCE5; selection-color:#242426; }
QLineEdit:focus { border-color:#A1A1AC; background:#F7F7FA; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:transparent; width:9px; margin:2px; }
QScrollBar::handle:vertical { background:#C6C6CF; border-radius:3px; min-height:32px; }
QScrollBar::handle:vertical:hover { background:#A4A4B0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QSplitter::handle { background:#E5E5E9; }
QSplitter::handle:hover { background:#B8B8C3; }
QToolTip { background:#303039; color:white; border:0; padding:6px; }
QFrame#rawFiles { background:white; border:1px solid #E5E5E9; border-radius:10px; }
QFrame#rawFiles[dragOver="true"] { border:1px solid #C92532; background:#FFF8F8; }
QFrame#fileRow { background:#F7F7F9; border:0; border-radius:8px; }
QFrame#fileRow:hover { background:#EDEDF2; }
QLabel#fileCount { background:#EEEEF3; color:#515159; border-radius:8px; padding:4px 10px; }
QLabel#dropHint { border:1px dashed #C9C9D2; border-radius:8px; padding:16px; color:#717178; }
"""

TERMINAL_QSS = """
QFrame#terminal { background:#202126; border:0; }
QFrame#terminalHeader { background:#292A30; border:0; }
QFrame#terminal QLabel { color:#BFC1CC; font-family:"Segoe UI"; font-size:12px; }
QFrame#terminal QPushButton { background:transparent; color:#C6C8D2; border:1px solid transparent;
                            border-radius:6px; padding:4px 10px; font-size:12px; }
QFrame#terminal QPushButton:hover { background:#3B3D46; color:white; }
QFrame#terminal QPushButton:focus { border-color:#8B8D99; }
QFrame#terminal QTextEdit { background:#202126; color:#E0E0E0; font-family:"Cascadia Mono", "Consolas";
                           font-size:12px; border:0; padding:8px 12px; }
QFrame#terminal QScrollBar:vertical { background:#202126; width:9px; }
QFrame#terminal QScrollBar::handle:vertical { background:#535661; border-radius:3px; min-height:24px; }
QFrame#terminal QScrollBar::add-line:vertical,
QFrame#terminal QScrollBar::sub-line:vertical { height:0; }
QFrame#terminal QScrollBar::add-page:vertical,
QFrame#terminal QScrollBar::sub-page:vertical { background:transparent; }
"""


def role(widget, name):
    widget.setProperty("role", name)
    return widget


def set_tone(widget, tone):
    if widget.property("tone") != tone:
        widget.setProperty("tone", tone)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class _LineIcon(QIconEngine):
    """Paint at the requested resolution, including fractional Windows DPI."""

    def __init__(self, name, color):
        super().__init__()
        self.name, self.color = name, color

    def clone(self):
        return _LineIcon(self.name, self.color)

    def pixmap(self, size, mode, state):
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap

    def scaledPixmap(self, size, mode, state, scale):
        physical_size = QSize(round(size.width() * scale), round(size.height() * scale))
        pixmap = self.pixmap(physical_size, mode, state)
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def paint(self, painter, rect, mode, state):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(rect.x(), rect.y())
        painter.scale(rect.width() / 24, rect.height() / 24)
        color = "#9696A0" if mode == QIcon.Disabled else self.color
        painter.setPen(QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        name = self.name
        if name in ("star", "star_filled"):
            import math
            path = QPainterPath()
            for i in range(10):
                angle = math.pi * i / 5 - math.pi / 2
                radius = 9 if i % 2 == 0 else 4
                x, y = 12 + radius * math.cos(angle), 12 + radius * math.sin(angle)
                path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
            path.closeSubpath()
            if name == "star_filled":
                painter.setBrush(QColor(color))
            painter.drawPath(path)
        elif name in ("today", "business"):
            painter.drawRoundedRect(QRectF(4, 6, 16, 15 if name == "today" else 13), 2, 2)
            if name == "today":
                painter.drawLine(4, 11, 20, 11)
                painter.drawLine(8, 3, 8, 8)
                painter.drawLine(16, 3, 16, 8)
                painter.drawLine(8, 15, 11, 15)
            else:
                painter.drawRoundedRect(QRectF(9, 3, 6, 3), 1, 1)
                painter.drawLine(4, 12, 20, 12)
                painter.drawLine(12, 11, 12, 14)
        elif name == "all":
            for x in (4, 14):
                for y in (4, 14):
                    painter.drawRoundedRect(QRectF(x, y, 6, 6), 1, 1)
        elif name == "consumer":
            painter.drawEllipse(QRectF(8, 3, 8, 8))
            path = QPainterPath()
            path.moveTo(4, 21)
            path.cubicTo(4, 10, 20, 10, 20, 21)
            painter.drawPath(path)
        elif name == "campaigns":
            path = QPainterPath()
            path.moveTo(4, 10)
            path.lineTo(10, 10)
            path.lineTo(20, 5)
            path.lineTo(20, 19)
            path.lineTo(10, 14)
            path.lineTo(4, 14)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(8, 15, 10, 21)
        elif name == "files":
            path = QPainterPath()
            path.moveTo(3, 7)
            path.lineTo(3, 20)
            path.lineTo(21, 20)
            path.lineTo(21, 7)
            path.lineTo(12, 7)
            path.lineTo(10, 4)
            path.lineTo(3, 4)
            path.closeSubpath()
            painter.drawPath(path)
        elif name == "search":
            painter.drawEllipse(QRectF(4, 4, 11, 11))
            painter.drawLine(14, 14, 20, 20)
        elif name == "play":
            path = QPainterPath()
            path.moveTo(8, 4)
            path.lineTo(19, 12)
            path.lineTo(8, 20)
            path.closeSubpath()
            painter.drawPath(path)
        elif name == "exit":
            painter.drawLine(10, 4, 4, 4)
            painter.drawLine(4, 4, 4, 20)
            painter.drawLine(4, 20, 10, 20)
            painter.drawLine(10, 12, 21, 12)
            painter.drawLine(17, 8, 21, 12)
            painter.drawLine(17, 16, 21, 12)
        elif name == "trash":
            painter.drawLine(4, 6, 20, 6)
            painter.drawLine(9, 3, 15, 3)
            painter.drawRoundedRect(QRectF(6, 6, 12, 15), 2, 2)
            painter.drawLine(10, 10, 10, 17)
            painter.drawLine(14, 10, 14, 17)
        else:
            painter.drawRoundedRect(QRectF(5, 3, 14, 18), 2, 2)
            painter.drawLine(9, 9, 15, 9)
            painter.drawLine(9, 13, 15, 13)
            painter.drawLine(9, 17, 12, 17)
        painter.restore()


def line_icon(name, color=Theme.MUTED):
    return QIcon(_LineIcon(name, color))
