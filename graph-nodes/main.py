from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel
import weakref


T = TypeVar('T', bound='Node')


class Node[P](BaseModel):
    _parent: Optional[weakref.ref] = None

    def model_post_init(self, __context: Any) -> None:
        """Post init hook to add self as parent to any 'Node' attributes."""
        super().model_post_init(__context)
        for _, v in self:
            # try to set 'parent' to 'self' for all public attributes
            try:
                v.parent = self
            except AttributeError:
                pass

    @property
    def parent(self) -> P | None:
        """Weakref to parent node or None."""
        return self._parent() if self._parent is not None else None
    
    @parent.setter
    def parent(self, parent: Optional['Node'] = None):
        """Set weakref to parent node or None."""
        print(f'setting parent to {parent}')
        self._parent = weakref.ref(parent) if parent is not None else None
    
    def find_parent(self, cls: Type[T]) -> T:
        """Find first parent node with class `cls`."""
        if isinstance(self.parent, cls):
            return self.parent
        try:
            return self.parent.find_parent(cls)  # type: ignore
        except AttributeError:
            raise ValueError(f'No parent of type {cls} found.')


n = Node[int]()
n.parent

