from __future__ import annotations
import PySide6.QtWidgets as QtWidgets
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainterPath, QPainter
from ui.port_item import PortItem

class SubFactoryNode(QtWidgets.QGraphicsItem):
    """
    A visual container for a group of MachineNodes.
    Can be in 'Expanded' state (shows a dashed border around members)
    or 'Collapsed' state (shows a compact box with proxy ports).
    """
    
    def __init__(self, group_data: dict, scene, members: list = None):
        super().__init__()
        self.group_id = group_data.get("id")
        self.name = group_data.get("name", "Sub-Factory")
        self.is_collapsed = bool(group_data.get("is_collapsed", 0))
        self.factory_scene = scene
        self.members = members or [] # MachineNode instances
        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        
        self.setPos(group_data.get("pos_x", 0), group_data.get("pos_y", 0))
        self._last_pos = self.pos()
        self.setZValue(10 if self.is_collapsed else -10)
        
        self.w = 200
        self.h = 100
        
        self.proxy_ports = []
        self.connection_storage = {} # ConnectionLine -> (original_src, original_tgt, original_visible)
        
    def boundingRect(self) -> QRectF:
        if self.is_collapsed:
            return QRectF(0, 0, self.w, self.h)
        else:
            if not self.members:
                return QRectF(0, 0, 100, 100)
            
            rects = [m.sceneBoundingRect() for m in self.members]
            min_x = min(r.left() for r in rects)
            min_y = min(r.top() for r in rects)
            max_x = max(r.right() for r in rects)
            max_y = max(r.bottom() for r in rects)
            
            p = self.pos()
            lx, ly = min_x - p.x(), min_y - p.y()
            lw, lh = max_x - min_x, max_y - min_y
            
            padding = 40
            return QRectF(lx - padding, ly - padding - 40, 
                         lw + padding*2, lh + padding*2 + 40)

    def shape(self) -> QPainterPath:
        """Define the clickable area. Hollow when expanded."""
        path = QPainterPath()
        if self.is_collapsed:
            path.addRect(self.boundingRect())
            for port in self.proxy_ports:
                path.addEllipse(port.mapToItem(self, port.boundingRect()).boundingRect())
        else:
            brect = self.boundingRect()
            path.addRect(brect.left(), brect.top(), brect.width(), 40)
            S = 20
            path.addRect(brect.left(), brect.top(), S, brect.height())
            path.addRect(brect.right() - S, brect.top(), S, brect.height())
            path.addRect(brect.left(), brect.top(), brect.width(), S)
            path.addRect(brect.left(), brect.bottom() - S, brect.width(), S)
        return path

    def refresh_bounds(self):
        """Called when a member machine moves, to update the group's visual box."""
        self.prepareGeometryChange()
        self.update()

    def paint(self, painter, option, widget=None):
        if self.is_collapsed:
            self._draw_collapsed(painter)
        else:
            self._draw_expanded(painter)
            
    def _draw_collapsed(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#00d2ff"), 2))
        painter.setBrush(QBrush(QColor(0, 210, 255, 40)))
        
        rect = QRectF(0, 0, self.w, self.h)
        painter.drawRoundedRect(rect, 12, 12)
        
        painter.setBrush(QBrush(QColor(0, 210, 255, 120)))
        painter.drawRoundedRect(QRectF(0, 0, self.w, 30), 12, 12)
        
        font = QFont("Segoe UI", 10)
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(30, 0, self.w - 30, 30), Qt.AlignCenter, self.name)
        
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawRect(QRectF(8, 8, 14, 14))
        painter.drawLine(10, 15, 20, 15)
        if self.is_collapsed:
            painter.drawLine(15, 10, 15, 20)

        font1 = QFont("Segoe UI", 8)
        font1.setPixelSize(10)
        painter.setFont(font1)
        painter.drawText(QRectF(0, 35, self.w, 65), Qt.AlignCenter, 
                         f"{len(self.members)} Machines\nProduction Optimized")

    def _draw_expanded(self, painter):
        if not self.members: return
        
        painter.setPen(QPen(QColor("#00d2ff"), 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.boundingRect())
        
        brect = self.boundingRect()
        btn_rect = QRectF(brect.left() + 5, brect.top() + 5, 20, 20)
        painter.setPen(QPen(QColor("#00d2ff"), 2))
        painter.drawRect(btn_rect)
        painter.drawLine(btn_rect.left() + 4, btn_rect.center().y(), btn_rect.right() - 4, btn_rect.center().y())
        if self.is_collapsed:
            painter.drawLine(btn_rect.center().x(), btn_rect.top() + 4, btn_rect.center().x(), btn_rect.bottom() - 4)

        font2 = QFont("Segoe UI", 9)
        font2.setPixelSize(12)
        font2.setBold(True)
        painter.setFont(font2)
        painter.setPen(QColor("#00d2ff"))
        painter.drawText(QRectF(brect.left() + 35, brect.top(), 300, 30), 
                         Qt.AlignLeft | Qt.AlignVCenter, self.name.upper())

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged and hasattr(self, "_last_pos"):
            new_pos = value
            delta = new_pos - self._last_pos
            if delta.x() != 0 or delta.y() != 0:
                for m in self.members:
                    m.setPos(m.pos() + delta)
                self._last_pos = new_pos
                
            if self.is_collapsed:
                for port in self.proxy_ports:
                    for conn in port.connections:
                        conn.update_path()
                        
        return super().itemChange(change, value)
        
    def mousePressEvent(self, event):
        pos = event.pos()
        if self.is_collapsed:
            btn_rect = QRectF(8, 8, 14, 14)
        else:
            brect = self.boundingRect()
            btn_rect = QRectF(brect.left() + 5, brect.top() + 5, 20, 20)
            
        if btn_rect.contains(pos):
            self._toggle_state()
            event.accept()
            return
            
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Context menu: Collapse/Expand + Disband Group
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background:#16213e; color:#eaeaea; border:1px solid #4a4a8a; font-size:13px; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background:#0f3460; }"
            "QMenu::separator { height:1px; background:#4a4a8a; margin:4px 0; }"
        )

        toggle_txt = "📂 Expand Group" if self.is_collapsed else "📁 Collapse Group"
        act_toggle = QAction(toggle_txt)
        menu.addAction(act_toggle)

        menu.addSeparator()

        act_ungroup = QAction("🔓 Disband Group")
        menu.addAction(act_ungroup)

        chosen = menu.exec(event.screenPos())

        if chosen == act_toggle:
            self._toggle_state()
        elif chosen == act_ungroup:
            self._ungroup()

    # ------------------------------------------------------------------
    # Toggle collapse / expand
    # ------------------------------------------------------------------
    def _toggle_state(self):
        from database.crud import update_group_collapse
        self.is_collapsed = not self.is_collapsed
        update_group_collapse(self.group_id, self.is_collapsed)
        
        if self.is_collapsed:
            self.setZValue(10)  # Above machines so it receives clicks
            self._create_proxy_ports()
        else:
            self.setZValue(-10)  # Behind machines
            self._restore_original_ports()

        for m in self.members:
            m.setVisible(not self.is_collapsed)
            
        self.factory_scene.recalculate()
        self.prepareGeometryChange()
        self.update()

    # ------------------------------------------------------------------
    # Proxy port management for collapsed state
    # ------------------------------------------------------------------
    def _create_proxy_ports(self):
        """Find connections crossing the group boundary and re-route them."""
        in_nodes = set(self.members)
        in_proxy_count = 0
        out_proxy_count = 0
        
        for conn in list(self.factory_scene._connections):
            try:
                src_node = conn.src_port.parent_node
                tgt_node = conn.tgt_port.parent_node
            except RuntimeError:
                continue
            
            src_in = src_node in in_nodes
            tgt_in = tgt_node in in_nodes
            
            if src_in and tgt_in:
                self.connection_storage[conn] = (conn.src_port, conn.tgt_port, conn.isVisible())
                conn.setVisible(False)
            elif src_in and not tgt_in:
                self._add_proxy(conn, "out", out_proxy_count)
                out_proxy_count += 1
            elif not src_in and tgt_in:
                self._add_proxy(conn, "in", in_proxy_count)
                in_proxy_count += 1

    def _add_proxy(self, conn, ptype, index):
        x = 0 if ptype == "in" else self.w
        y = 40 + index * 20
        
        proxy = PortItem(ptype, self, self, index=index, side="left" if ptype=="in" else "right")
        proxy.setPos(x, y)
        self.proxy_ports.append(proxy)
        proxy.show()
        
        self.connection_storage[conn] = (conn.src_port, conn.tgt_port, conn.isVisible())
        
        try:
            if ptype == "out":
                conn.src_port.connections.remove(conn)
                conn.src_port = proxy
                proxy.connections.append(conn)
            else:
                conn.tgt_port.connections.remove(conn)
                conn.tgt_port = proxy
                proxy.connections.append(conn)
        except (RuntimeError, ValueError):
            pass
            
        conn.setVisible(True)
        conn.update_path()

    def _restore_original_ports(self):
        """Return all connections to their original machine ports."""
        for conn, (old_src, old_tgt, old_vis) in self.connection_storage.items():
            try:
                if conn.src_port in self.proxy_ports:
                    conn.src_port.connections.remove(conn)
                if conn.tgt_port in self.proxy_ports:
                    conn.tgt_port.connections.remove(conn)
            except (RuntimeError, ValueError):
                pass
            
            conn.src_port = old_src
            conn.tgt_port = old_tgt
            try:
                if conn not in old_src.connections:
                    old_src.connections.append(conn)
                if conn not in old_tgt.connections:
                    old_tgt.connections.append(conn)
            except RuntimeError:
                pass
            
            conn.setVisible(old_vis)
            conn.update_path()
            
        for p in self.proxy_ports:
            try:
                if self.scene():
                    self.scene().removeItem(p)
            except RuntimeError:
                pass
        self.proxy_ports.clear()
        self.connection_storage.clear()

    # ------------------------------------------------------------------
    # Disband: release machines, remove group
    # ------------------------------------------------------------------
    def _ungroup(self):
        """Disband group: release all machines back to the canvas."""
        from database.crud import set_node_group, delete_group
        
        if self.is_collapsed:
            self._restore_original_ports()
        
        for m in self.members:
            try:
                set_node_group(m.db_id, None)
                m.group_id = None
                m.setVisible(True)
            except RuntimeError:
                pass
        
        delete_group(self.group_id)
        if hasattr(self.factory_scene, "remove_group"):
            self.factory_scene.remove_group(self)
        
        self.factory_scene.recalculate()
