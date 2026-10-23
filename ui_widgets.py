"""Small presentation-only widgets shared by the workspace."""

from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QRegion
from PySide6.QtWidgets import QLabel, QSizePolicy, QComboBox, QListView, QStyledItemDelegate, QStyle
from ui_theme import COMBOBOX_QSS, COMBO_POPUP_QSS


class _ComboItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width() + 24, 36)

    def paint(self, painter, option, index):
        # Draw explicitly to avoid Fusion's native blue selection/focus rectangle.
        self.initStyleOption(option, index)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#E8E8ED" if selected else "#F5F5F7" if hovered else "#FFFFFF"))
        painter.drawRoundedRect(QRectF(option.rect), 6, 6)
        rect = option.rect.adjusted(8, 0, -8, 0)
        if not option.icon.isNull():
            icon_rect = rect.adjusted(0, 8, 0, -8)
            icon_rect.setWidth(20)
            option.icon.paint(painter, icon_rect)
            rect.setLeft(rect.left() + 28)
        painter.setFont(option.font)
        painter.setPen(QColor("#1D1D1F" if option.state & QStyle.State_Enabled else "#A1A1A6"))
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft,
                         option.fontMetrics.elidedText(option.text, Qt.ElideRight, rect.width()))
        painter.restore()


class StyledComboBox(QComboBox):
    """Presentation-only combo: retain Qt's model, signals and keyboard handling."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(COMBOBOX_QSS)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setMaximumHeight(8 * 36 + 10)
        view.setMouseTracking(True)
        view.setVerticalScrollMode(QListView.ScrollPerPixel)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet(COMBO_POPUP_QSS)
        self.setView(view)
        self.setItemDelegate(_ComboItemDelegate(view))
        self.setMaxVisibleItems(8)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#717178" if self.isEnabled() else "#AEAEB2"),
                            1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        x, y = self.width() - 19, self.height() / 2
        path = QPainterPath()
        path.moveTo(x - 4, y - 2)
        path.lineTo(x, y + 2)
        path.lineTo(x + 4, y - 2)
        painter.drawPath(path)

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        popup.setStyleSheet("QFrame { background:#FFFFFF; border:none; }")
        path = QPainterPath()
        path.addRoundedRect(QRectF(popup.rect()), 10, 10)
        popup.setMask(QRegion(path.toFillPolygon().toPolygon()))


class ElidedLabel(QLabel):
    """Keep the full text selectable/accessible without widening its layout."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(text)

    def setText(self, text):
        super().setText(text)
        self.setToolTip(text)

    def paintEvent(self, event):
        if self.fontMetrics().horizontalAdvance(self.text()) <= self.contentsRect().width():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.contentsRect(), Qt.AlignLeft | Qt.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(), Qt.ElideMiddle, self.contentsRect().width()))

    def minimumSizeHint(self):
        return QSize(0, self.fontMetrics().height() + 4)
