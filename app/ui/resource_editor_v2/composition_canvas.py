from __future__ import annotations

from copy import deepcopy
import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from app.services.resource_composition_render_service import render_composition_frame


def alpha_bounds(pixels):
    """Return half-open non-transparent bounds without changing pixel data."""
    ys,xs=np.nonzero(pixels[...,3]>0)
    if not len(xs):return None
    return int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1


class CompositionCanvas(QWidget):
    layer_selected = Signal(object)
    transform_changed = Signal(str, object, bool)
    transform_cancelled = Signal(str, object)
    drag_started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("resourceV2CompositionCanvas")
        self.setMinimumSize(320, 240); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.project = self.composition = self.layer = None; self.frame = 0; self.mode = "move"; self.mode_text = ""
        self.zoom = 8; self.pan = QPointF(); self._panning = False; self._drag = None; self._drag_axis = None; self._hover_handle=None; self._start_point = QPointF(); self._start_value = None; self._start_angle = 0.0;self._alpha_bounds_cache={}
        self.setMouseTracking(True)

    def set_context(self, project, composition, layer, frame):
        if project is not self.project:self._alpha_bounds_cache.clear()
        self.project, self.composition, self.layer, self.frame = project, composition, layer, frame; self.update()

    def set_mode(self, mode, text=""):
        self.mode, self.mode_text = mode, text; self.update()

    def origin(self):
        if not self.composition: return QPointF()
        return QPointF((self.width()-self.composition.width*self.zoom)/2+self.pan.x(), (self.height()-self.composition.height*self.zoom)/2+self.pan.y())

    def to_comp(self, point):
        origin = self.origin(); return QPointF((point.x()-origin.x())/self.zoom, (point.y()-origin.y())/self.zoom)

    def to_widget(self, point):
        origin = self.origin(); return QPointF(origin.x()+point.x()*self.zoom, origin.y()+point.y()*self.zoom)

    def _source(self, layer):
        items = self.project.source_assets if layer.source_type == "source_asset" else self.project.animation_clips
        return next((item for item in items if item.id == layer.source_id), None)

    def _source_alpha_bounds(self,source):
        key=id(source)
        if key not in self._alpha_bounds_cache:
            if hasattr(source,"pixels"):bounds=alpha_bounds(source.pixels)
            else:
                union=np.zeros((source.height,source.width),dtype=bool)
                for frame in source.frames:union|=frame[...,3]>0
                ys,xs=np.nonzero(union);bounds=None if not len(xs) else (int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1)
            self._alpha_bounds_cache[key]=bounds or (0,0,source.width,source.height)
        return self._alpha_bounds_cache[key]

    def selection_polygon_comp(self, layer):
        source = self._source(layer)
        if source is None: return QPolygonF()
        position = layer.value("position", self.frame); scale = layer.value("scale", self.frame); rotation = math.radians(float(layer.value("rotation", self.frame)))
        pivot = QPointF(self.composition.width/2+position[0], self.composition.height/2+position[1]); cosine, sine = math.cos(rotation), math.sin(rotation)
        x0,y0,x1,y1=self._source_alpha_bounds(source);result = QPolygonF()
        for x, y in ((x0-layer.pivot_x,y0-layer.pivot_y),(x1-layer.pivot_x,y0-layer.pivot_y),(x1-layer.pivot_x,y1-layer.pivot_y),(x0-layer.pivot_x,y1-layer.pivot_y)):
            x *= scale[0]; y *= scale[1]; result.append(QPointF(pivot.x()+x*cosine-y*sine, pivot.y()+x*sine+y*cosine))
        return result

    def _polygon_widget(self, layer):
        return QPolygonF([self.to_widget(point) for point in self.selection_polygon_comp(layer)])

    def _pivot_widget(self, layer):
        position = layer.value("position", self.frame); return self.to_widget(QPointF(self.composition.width/2+position[0], self.composition.height/2+position[1]))

    def rotate_handle_position(self, layer=None):
        layer=layer or self.layer
        if layer is None:return QPointF()
        polygon = self._polygon_widget(layer)
        if len(polygon) < 2: return QPointF()
        top = (polygon[0]+polygon[1])/2; pivot = self._pivot_widget(layer); vector = top-pivot; length=max(1.0,math.hypot(vector.x(),vector.y()))
        return top+QPointF(vector.x()/length*26, vector.y()/length*26)

    def move_handle_positions(self,layer=None):
        pivot=self._pivot_widget(layer or self.layer);return {"free":pivot,"x":pivot+QPointF(38,0),"y":pivot+QPointF(0,-38)}

    def scale_handle_positions(self,layer=None):
        polygon=self._polygon_widget(layer or self.layer)
        if len(polygon)<4:return {}
        return {"uniform":polygon[2],"x":(polygon[1]+polygon[2])/2,"y":(polygon[0]+polygon[1])/2,"uniform0":polygon[0],"uniform1":polygon[1],"uniform3":polygon[3]}

    def _hit_layer(self, comp_point):
        for layer in reversed(self.composition.layers):
            if layer.visible and layer.start_frame <= self.frame <= layer.end_frame and self.selection_polygon_comp(layer).containsPoint(comp_point, Qt.FillRule.OddEvenFill): return layer
        return None

    @staticmethod
    def _near(a, b, radius=10): return math.hypot(a.x()-b.x(), a.y()-b.y()) <= radius

    def wheelEvent(self, event):
        self.zoom=max(1,min(32,self.zoom+(1 if event.angleDelta().y()>0 else -1))); self.update(); event.accept()

    def paintEvent(self, event):
        painter=QPainter(self); painter.fillRect(self.rect(),QColor("#20242b"))
        if self.composition is None: return
        pixels=np.ascontiguousarray(render_composition_frame(self.project,self.composition,self.frame)); origin=self.origin(); rect=QRectF(origin.x(),origin.y(),self.composition.width*self.zoom,self.composition.height*self.zoom)
        tile=max(4,self.zoom*4)
        for y in range(int(rect.top()),int(rect.bottom())+1,tile):
            for x in range(int(rect.left()),int(rect.right())+1,tile): painter.fillRect(x,y,tile,tile,QColor("#dfe3e8") if ((x-int(rect.left()))//tile+(y-int(rect.top()))//tile)%2 else QColor("#aeb4bc"))
        image=QImage(pixels.data,self.composition.width,self.composition.height,pixels.strides[0],QImage.Format.Format_RGBA8888).copy(); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,False); painter.drawPixmap(rect,QPixmap.fromImage(image),QRectF(0,0,self.composition.width,self.composition.height)); painter.setPen(QPen(QColor("#6ea8fe"),1)); painter.drawRect(rect)
        if self.layer is None: return
        polygon=self._polygon_widget(self.layer); painter.setPen(QPen(QColor("#51cf66"),2)); painter.drawPolygon(polygon)
        pivot=self._pivot_widget(self.layer); painter.setPen(QPen(QColor("#ff6b6b"),2)); painter.drawLine(QPointF(pivot.x()-8,pivot.y()),QPointF(pivot.x()+8,pivot.y())); painter.drawLine(QPointF(pivot.x(),pivot.y()-8),QPointF(pivot.x(),pivot.y()+8))
        if self.mode=="rotate":
            handle=self.rotate_handle_position(); top=(polygon[0]+polygon[1])/2; painter.setPen(QPen(QColor("#ffd43b"),2)); painter.drawLine(top,handle); painter.setBrush(QColor("#ffd43b")); painter.drawEllipse(handle,6,6)
        elif self.mode=="scale":
            handles=self.scale_handle_positions();painter.setBrush(QColor("#74c0fc"));
            for name,point in handles.items():
                painter.setBrush(QColor("#ffd43b") if self._hover_handle==name else QColor("#74c0fc"));painter.drawRect(QRectF(point.x()-6,point.y()-6,12,12))
        elif self.mode=="move":
            handles=self.move_handle_positions();x=handles["x"];y=handles["y"]
            painter.setPen(QPen(QColor("#ff6b6b"),3));painter.drawLine(pivot,x);painter.setBrush(QColor("#ff6b6b"));painter.drawEllipse(x,6,6)
            painter.setPen(QPen(QColor("#51cf66"),3));painter.drawLine(pivot,y);painter.setBrush(QColor("#51cf66"));painter.drawEllipse(y,6,6)
        if self.mode_text:
            painter.setPen(QColor("#ffffff")); painter.drawText(12,22,self.mode_text)

    def mousePressEvent(self, event):
        if event.button()==Qt.MouseButton.MiddleButton:
            self._panning=True; self._start_point=event.position()-self.pan; event.accept(); return
        if event.button()!=Qt.MouseButton.LeftButton or self.composition is None: return super().mousePressEvent(event)
        point=event.position(); comp_point=self.to_comp(point); prop=None
        if self.layer is not None:
            polygon=self._polygon_widget(self.layer)
            if self.mode=="pivot" and self._near(point,self._pivot_widget(self.layer)): prop="pivot"
            elif self.mode=="rotate" and self._near(point,self.rotate_handle_position()): prop="rotation"
            elif self.mode=="scale":
                handle=next((name for name,pos in self.scale_handle_positions().items() if self._near(point,pos)),None)
                if handle:prop="scale";self._drag_axis=handle
            elif self.mode=="move":
                handle=next((name for name,pos in self.move_handle_positions().items() if name!="free" and self._near(point,pos)),None)
                if handle:prop="position";self._drag_axis=handle
                elif polygon.containsPoint(point,Qt.FillRule.OddEvenFill):prop="position";self._drag_axis="free"
        if prop is not None:
            self._drag=prop; self._start_point=comp_point; self._start_value=[self.layer.pivot_x,self.layer.pivot_y] if prop=="pivot" else deepcopy(self.layer.value(prop,self.frame)); pivot=self.to_comp(self._pivot_widget(self.layer)); self._start_angle=math.atan2(comp_point.y()-pivot.y(),comp_point.x()-pivot.x()); self.drag_started.emit(); event.accept(); return
        hit=self._hit_layer(comp_point)
        if hit is not self.layer:self.layer_selected.emit(None if hit is None else hit.id)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._panning: self.pan=event.position()-self._start_point; self.update(); event.accept(); return
        if not self._drag:
            old=self._hover_handle;self._hover_handle=None
            if self.layer is not None:
                handles=self.move_handle_positions() if self.mode=="move" else self.scale_handle_positions() if self.mode=="scale" else {"rotate":self.rotate_handle_position()} if self.mode=="rotate" else {}
                self._hover_handle=next((name for name,pos in handles.items() if self._near(event.position(),pos)),None)
            if old!=self._hover_handle:self.update()
            self.setCursor(Qt.CursorShape.SizeHorCursor if self._hover_handle=="x" else Qt.CursorShape.SizeVerCursor if self._hover_handle=="y" else Qt.CursorShape.CrossCursor if self._hover_handle else Qt.CursorShape.ArrowCursor)
            return super().mouseMoveEvent(event)
        point=self.to_comp(event.position()); delta=point-self._start_point
        if self._drag in {"position","pivot"}:
            dx=0 if self._drag_axis=="y" else delta.x();dy=0 if self._drag_axis=="x" else delta.y();value=[round(self._start_value[0]+dx),round(self._start_value[1]+dy)]
        elif self._drag=="rotation":
            pivot=self.to_comp(self._pivot_widget(self.layer)); angle=math.atan2(point.y()-pivot.y(),point.x()-pivot.x()); value=self._start_value+math.degrees(angle-self._start_angle); value=round(value/15)*15 if event.modifiers()&Qt.KeyboardModifier.ShiftModifier else value
        else:
            pivot=self.to_comp(self._pivot_widget(self.layer)); start=max(.001,math.hypot(self._start_point.x()-pivot.x(),self._start_point.y()-pivot.y())); ratio=max(.01,math.hypot(point.x()-pivot.x(),point.y()-pivot.y())/start); value=[max(.01,self._start_value[0]*ratio),max(.01,self._start_value[1]*ratio)]
            if self._drag_axis=="x":value[1]=self._start_value[1]
            elif self._drag_axis=="y":value[0]=self._start_value[0]
        self.transform_changed.emit(self._drag,value,False); event.accept()

    def mouseReleaseEvent(self, event):
        if self._panning and event.button()==Qt.MouseButton.MiddleButton: self._panning=False; event.accept(); return
        if self._drag:
            prop=self._drag; self._drag=None; self._drag_axis=None; value=[self.layer.pivot_x,self.layer.pivot_y] if prop=="pivot" else deepcopy(self.layer.value(prop,self.frame)); self.transform_changed.emit(prop,value,True); event.accept(); return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key()==Qt.Key.Key_Escape and self._drag:
            prop,value=self._drag,self._start_value; self._drag=None;self._drag_axis=None; self.transform_cancelled.emit(prop,value); event.accept(); return
        super().keyPressEvent(event)
