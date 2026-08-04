from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from app.ui.timeline_scrub_controller import TimelineScrubController


class CompositionTimeline(QWidget):
    frame_selected = Signal(int)
    layer_selected = Signal(object)
    visibility_requested = Signal(str)
    play_requested = Signal()
    previous_requested = Signal()
    next_requested = Signal()
    delete_keyframe_requested = Signal(object)
    scrub_started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent); self.rows=[]; self.localization=None; layout=QVBoxLayout(self); controls=QHBoxLayout()
        self.previous=QPushButton("◀"); self.play=QPushButton("▶"); self.play.setObjectName("resourceV2PlayButton"); self.next=QPushButton("▶|"); self.delete_keyframe=QPushButton()
        for widget in (self.previous,self.play,self.next,self.delete_keyframe): controls.addWidget(widget)
        controls.addStretch(); layout.addLayout(controls)
        self.frame_cell_width=36; self.table=QTableWidget(); self.table.setObjectName("resourceV2CompositionTimeline"); self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.table.horizontalHeader().setDefaultSectionSize(self.frame_cell_width); layout.addWidget(self.table)
        self.table.cellClicked.connect(self._clicked); self.table.verticalHeader().sectionClicked.connect(self._header_clicked)
        self.scrub_controller=TimelineScrubController(self.table,self._scrub_to,self.scrub_started.emit,self)
        self.previous.clicked.connect(self.previous_requested); self.next.clicked.connect(self.next_requested); self.play.clicked.connect(self.play_requested); self.delete_keyframe.clicked.connect(self._delete)

    def _scrub_to(self,row,column):
        self.table.setCurrentCell(row,column);self._clicked(row,column)

    def refresh(self, composition, selected_layer, frame):
        self.rows=[]
        for layer in composition.layers:
            self.rows.append((layer,None))
            for property_id in layer.tracks: self.rows.append((layer,property_id))
        self.table.blockSignals(True); self.table.clear(); self.table.setRowCount(len(self.rows)); self.table.setColumnCount(composition.frame_count); self.table.setHorizontalHeaderLabels([str(index+1) for index in range(composition.frame_count)])
        headers=[]
        for row,(layer,property_id) in enumerate(self.rows):
            property_name=self.localization.text("property."+property_id) if self.localization and property_id else property_id
            headers.append(("☑ " if layer.visible else "☐ ")+layer.name if property_id is None else "  ↳ "+property_name)
            for column in range(composition.frame_count):
                marker="◆" if property_id and any(key.frame==column for key in layer.tracks[property_id].keyframes) else "■" if property_id is None and layer.start_frame<=column<=layer.end_frame else "·"
                item=QTableWidgetItem(marker); item.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(row,column,item)
        self.table.setVerticalHeaderLabels(headers)
        target=next((index for index,value in enumerate(self.rows) if value[0] is selected_layer),0) if self.rows else -1
        if target>=0: self.table.setCurrentCell(target,frame); self.table.scrollToItem(self.table.item(target,frame))
        self.table.blockSignals(False)

    def set_frame_cell_width(self,width):
        self.frame_cell_width=max(20,min(96,int(width)));self.table.horizontalHeader().setDefaultSectionSize(self.frame_cell_width)
        for column in range(self.table.columnCount()):self.table.setColumnWidth(column,self.frame_cell_width)

    def _clicked(self,row,column):
        self.frame_selected.emit(column)
        if 0<=row<len(self.rows): self.layer_selected.emit(self.rows[row][0].id)

    def _header_clicked(self,row):
        if 0<=row<len(self.rows):
            layer,property_id=self.rows[row]
            if property_id is None: self.visibility_requested.emit(layer.id)

    def _delete(self):
        row=self.table.currentRow(); self.delete_keyframe_requested.emit(self.rows[row][1] if 0<=row<len(self.rows) else None)

    def set_playing(self,playing): self.play.setText("■" if playing else "▶")

    def retranslate(self,localization):
        self.localization=localization;self.delete_keyframe.setText(localization.text("composition.delete_keyframe")); self.previous.setToolTip(localization.text("tooltip.previous_frame")); self.next.setToolTip(localization.text("tooltip.next_frame")); self.play.setToolTip(localization.text("tooltip.play_stop")); self.delete_keyframe.setToolTip(localization.text("tooltip.delete_keyframe"))
