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
        self.setZValue(-10) # Behind machines
        
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
            
            # Use a cached version of member bounds to avoid self.pos() cycles
            rects = [m.sceneBoundingRect() for m in self.members]
            min_x = min(r.left() for r in rects)
            min_y = min(r.top() for r in rects)
            max_x = max(r.right() for r in rects)
            max_y = max(r.bottom() for r in rects)
            
            p = self.pos()
            lx, ly = min_x - p.x(), min_y - p.y()
            lw, lh = max_x - min_x, max_y - min_y
            
            padding = 40
            # Return local bounds. 
            # NOTE: We include extra top space for the label.
            return QRectF(lx - padding, ly - padding - 40, 
                         lw + padding*2, lh + padding*2 + 40)

    def shape(self) -> QPainterPath:
        """Define the clickable area. Hollow when expanded."""
        path = QPainterPath()
        if self.is_collapsed:
            path.addRect(self.boundingRect())
            # Add proxy ports to shape so they can be clicked/hovered
            for port in self.proxy_ports:
                path.addEllipse(port.mapToItem(self, port.boundingRect()).boundingRect())
        else:
            # Expanded: Only the border and the label area are clickable.
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
        # Draw a sleek box (Glassmorphism style)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#00d2ff"), 2))
        painter.setBrush(QBrush(QColor(0, 210, 255, 40)))
        
        rect = QRectF(0, 0, self.w, self.h)
        painter.drawRoundedRect(rect, 12, 12)
        
        # Header strip
        painter.setBrush(QBrush(QColor(0, 210, 255, 120)))
        painter.drawRoundedRect(QRectF(0, 0, self.w, 30), 12, 12)
        
        # Title
        font = QFont("Segoe UI", 10)
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(30, 0, self.w - 30, 30), Qt.AlignCenter, self.name)
        
        # Draw + / - Button Top Left
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawRect(QRectF(8, 8, 14, 14))
        painter.drawLine(10, 15, 20, 15)
        if self.is_collapsed:
            painter.drawLine(15, 10, 15, 20) # Draw the vertical line for '+'

        # Stats summary (placeholder)
        font1 = QFont("Segoe UI", 8)
        font1.setPixelSize(10)
        painter.setFont(font1)
        painter.drawText(QRectF(0, 35, self.w, 65), Qt.AlignCenter, 
                         f"{len(self.members)} Machines\nProduction Optimized")

    def _draw_expanded(self, painter):
        # Draw a dashed bounding box around members
        if not self.members: return
        
        painter.setPen(QPen(QColor("#00d2ff"), 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.boundingRect())
        
        # Draw + / - Button Top Left
        brect = self.boundingRect()
        btn_rect = QRectF(brect.left() + 5, brect.top() + 5, 20, 20)
        painter.setPen(QPen(QColor("#00d2ff"), 2))
        painter.drawRect(btn_rect)
        painter.drawLine(btn_rect.left() + 4, btn_rect.center().y(), btn_rect.right() - 4, btn_rect.center().y())
        if self.is_collapsed:
            painter.drawLine(btn_rect.center().x(), btn_rect.top() + 4, btn_rect.center().x(), btn_rect.bottom() - 4)

        # Label at top-left next to button
        font2 = QFont("Segoe UI", 9)
        font2.setPixelSize(12)
        font2.setBold(True)
        painter.setFont(font2)
        painter.setPen(QColor("#00d2ff"))
        # Draw label at the top of the padding area
        painter.drawText(QRectF(brect.left() + 35, brect.top(), 300, 30), 
                         Qt.AlignLeft | Qt.AlignVCenter, self.name.upper())

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged and hasattr(self, "_last_pos"):
            new_pos = value
            delta = new_pos - self._last_pos
            if delta.x() != 0 or delta.y() != 0:
                # Move all members with the group
                for m in self.members:
                    m.setPos(m.pos() + delta)
                self._last_pos = new_pos
                
            # Update paths for any external connections attached to our proxy ports
            if self.is_collapsed:
                for port in self.proxy_ports:
                    for conn in port.connections:
                        conn.update_path()
                        
        return super().itemChange(change, value)
        
    def mousePressEvent(self, event):
        pos = event.pos()
        # Check if clicked on the +/- button
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

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        toggle_txt = "Expand" if self.is_collapsed else "Collapse"
        from PySide6.QtGui import QAction
        
        act_toggle = QAction(toggle_txt, self)
        menu.addAction(act_toggle)
        
        act_ungroup = QAction("Ungroup", self)
        menu.addAction(act_ungroup)
        
        menu.addSeparator()
        
        act_del_all = QAction("🗑 Delete Group & Members", self)
        menu.addAction(act_del_all)
        
        chosen = menu.exec(event.screenPos())
        
        if chosen == act_toggle:
            self._toggle_state()
        elif chosen == act_ungroup:
            self._ungroup()
        elif chosen == act_del_all:
            self._delete_group_fully()
        
    def _toggle_state(self):
        from database.crud import update_group_collapse
        self.is_collapsed = not self.is_collapsed
        update_group_collapse(self.group_id, self.is_collapsed)
        
        if self.is_collapsed:
            self._create_proxy_ports()
        else:
            self._restore_original_ports()

        # Update members visibility
        for m in self.members:
            m.setVisible(not self.is_collapsed)
            
        # Refresh connections
        self.factory_scene.recalculate()
        self.prepareGeometryChange()
        self.update()

    def _create_proxy_ports(self):
        """Find connections crossing the group boundary and re-route them."""
        # Note: self.members is a list of MachineNodes
        in_nodes = set(self.members)
        
        in_proxy_count = 0
        out_proxy_count = 0
        
        # Iterate over all connections in the scene
        # (This is safer than just checking members' ports)
        for conn in self.factory_scene._connections:
            src_node = conn.src_port.parent_node
            tgt_node = conn.tgt_port.parent_node
            
            src_in = src_node in in_nodes
            tgt_in = tgt_node in in_nodes
            
            if src_in and tgt_in:
                # Internal connection - hide it
                self.connection_storage[conn] = (conn.src_port, conn.tgt_port, conn.isVisible())
                conn.setVisible(False)
            elif src_in and not tgt_in:
                # Output connection crossing OUT
                self._add_proxy(conn, "out", out_proxy_count)
                out_proxy_count += 1
            elif not src_in and tgt_in:
                # Input connection crossing IN
                self._add_proxy(conn, "in", in_proxy_count)
                in_proxy_count += 1

    def _add_proxy(self, conn, ptype, index):
        # Create a proxy port on the SubFactoryNode
        # Position it on the left (in) or right (out)
        x = 0 if ptype == "in" else self.w
        y = 40 + index * 20
        
        proxy = PortItem(ptype, self, self, index=index, side="left" if ptype=="in" else "right")
        proxy.setPos(x, y)
        self.proxy_ports.append(proxy)
        proxy.show() # Ensure it's visually shown
        
        # Store original ports and visibility
        self.connection_storage[conn] = (conn.src_port, conn.tgt_port, conn.isVisible())
        
        # Re-link connection
        if ptype == "out":
            # conn.src_port was inside, now it's our proxy
            conn.src_port.connections.remove(conn)
            conn.src_port = proxy
            proxy.connections.append(conn)
        else:
            # conn.tgt_port was inside, now it's our proxy
            conn.tgt_port.connections.remove(conn)
            conn.tgt_port = proxy
            proxy.connections.append(conn)
            
        conn.setVisible(True) # Force it to show since the port is external
        conn.update_path()

    def _restore_original_ports(self):
        """Return all connections to their original machine ports."""
        for conn, (old_src, old_tgt, old_vis) in self.connection_storage.items():
            # Remove from proxy if it was proxied
            if conn.src_port in self.proxy_ports:
                conn.src_port.connections.remove(conn)
            if conn.tgt_port in self.proxy_ports:
                conn.tgt_port.connections.remove(conn)
            
            # Restore ports
            conn.src_port = old_src
            conn.tgt_port = old_tgt
            if conn not in old_src.connections:
                old_src.connections.append(conn)
            if conn not in old_tgt.connections:
                old_tgt.connections.append(conn)
            
            # Restore visibility
            conn.setVisible(old_vis)
            conn.update_path()
            
        # Clean up
        for p in self.proxy_ports:
            if self.scene():
                self.scene().removeItem(p)
        self.proxy_ports.clear()
        self.connection_storage.clear()
        
    def _ungroup(self):
        from database.crud import set_node_group, delete_group
        for m in self.members:
            set_node_group(m.db_id, None)
            m.group_id = None
            m.setVisible(True)
        
        delete_group(self.group_id)
        if hasattr(self.factory_scene, "remove_group"):
            self.factory_scene.remove_group(self)
        else:
            if self.scene():
                self.scene().removeItem(self)
        
        self.factory_scene.recalculate()
    def _delete_group_fully(self):
        """Delete this group and ALL machines inside it."""
        from database.crud import delete_group
        
        # 1. Delete all members using their own deletion logic (cleans up DB + scene)
        # We use list() because members will be modified during iteration
        for m in list(self.members):
            m._delete_self()
        
        # 2. Delete group from DB
        delete_group(self.group_id)
        
        # 3. Remove from scene
        if hasattr(self.factory_scene, "remove_group"):
            self.factory_scene.remove_group(self)
        
        self.factory_scene.recalculate()
