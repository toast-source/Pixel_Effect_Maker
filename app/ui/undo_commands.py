"""Small-value undo commands; pixel buffers and projects are never copied."""

from copy import deepcopy
from time import monotonic
from weakref import ref
from PySide6.QtGui import QUndoCommand


class EditorValueCommand(QUndoCommand):
    def __init__(self, owner, target_id, field, before, after, text, merge_id=-1):
        super().__init__(text);self._owner=ref(owner);self.target_id=target_id;self.field=field;self.before=deepcopy(before);self.after=deepcopy(after);self._merge_id=merge_id;self._changed_at=monotonic()

    def id(self):return self._merge_id
    def mergeWith(self,other):
        if not isinstance(other,EditorValueCommand) or self._merge_id<0 or (self.target_id,self.field)!=(other.target_id,other.field) or other._changed_at-self._changed_at>.6:return False
        self.after=deepcopy(other.after);self._changed_at=other._changed_at;return True
    def _apply(self,value):
        owner=self._owner()
        if owner is not None:owner.apply_undo_value(self.target_id,self.field,deepcopy(value))
    def undo(self):self._apply(self.before)
    def redo(self):self._apply(self.after)


class EditorOperationCommand(QUndoCommand):
    def __init__(self,owner,operation,state,text):
        super().__init__(text);self._owner=ref(owner);self.operation=operation;self.state=state
    def _apply(self,forward):
        owner=self._owner()
        if owner is not None:owner.apply_undo_operation(self.operation,self.state,forward)
    def undo(self):self._apply(False)
    def redo(self):self._apply(True)
