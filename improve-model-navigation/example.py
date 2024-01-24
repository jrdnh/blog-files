# Created by jrdnh 2024-01-23
# jrdnh.github.io


####################
# Initial Node class
import weakref
from typing import Optional
from pydantic import BaseModel

# from typing import Generic, TypeVar

# P = TypeVar("P")
# class Node(BaseModel, Generic[P]):
#     ...

class Node[P](BaseModel):
    _parent: Optional[weakref.ref] = None

    @property
    def parent(self) -> P | None:
        """Parent node or None."""
        return self._parent() if self._parent is not None else None

    @parent.setter
    def parent(self, parent: Optional[P] = None):
        """Set parent."""
        self._parent = weakref.ref(parent) if parent is not None else None

# Example
class Parent(Node[None]):
    luftballons: int

class Child(Node[Parent]):
    pass

child = Child()
child.parent = Parent(luftballons=99)


####################
# Search parent types
from typing import Type, TypeVar

T = TypeVar("T", bound="Node")

class Node[P](BaseModel):
    _parent: Optional[weakref.ref] = None

    @property
    def parent(self) -> P:
        """Parent node or None."""
        return self._parent() if self._parent is not None else None

    @parent.setter
    def parent(self, parent: Optional[P] = None):
        """Set parent."""
        self._parent = weakref.ref(parent) if parent is not None else None

    def find_parent(self, cls: Type[T]) -> T:
        """Find first parent node with class `cls`."""
        if isinstance(self.parent, cls):
            return self.parent
        try:
            return self.parent.find_parent(cls)  # type: ignore
        except AttributeError:
            raise ValueError(f"No parent of type {cls} found.")

####################
# Setting the parent attribute
from typing import Any, Type, TypeVar


T = TypeVar("T", bound="Node")


class Node[P](BaseModel):
    _parent: Optional[weakref.ref] = None

    def model_post_init(self, __context: Any) -> None:
        """Post init hook to add self as parent to any 'Node' attributes."""
        super().model_post_init(__context)
        for _, v in self:
            if isinstance(v, Node):
                v.parent = self

    @property
    def parent(self) -> P:
        """Parent node or None."""
        return self._parent() if self._parent is not None else None

    @parent.setter
    def parent(self, parent: Optional[P] = None):
        """Set parent."""
        self._parent = weakref.ref(parent) if parent is not None else None

    def find_parent(self, cls: Type[T]) -> T:
        """Find first parent node with class `cls`."""
        if isinstance(self.parent, cls):
            return self.parent
        try:
            return self.parent.find_parent(cls)  # type: ignore
        except AttributeError:
            raise ValueError(f"No parent of type {cls} found.")


####################
# A simple model
class Revenue(Node["NetIncome"]):
    def __call__(self, year: int):
        return 1000 * (1.1 ** (year - 2020))


class VariableExpenses(Node["NetIncome"]):
    def __call__(self, year: int):
        # Find NetIncome class
        ni = self.find_parent(NetIncome)
        return ni.revenue(year) * -0.6  # 60% of revenue


class Expenses(Node["NetIncome"]):
    variable: "VariableExpenses"

    def __call__(self, year: int):
        # total expenses = 100 + variable expenses
        return -100 + self.variable(year)


class NetIncome(Node[None]):
    revenue: "Revenue"
    expenses: "Expenses"

    def __call__(self, year: int):
        return self.revenue(year) + self.expenses(year)


# Confirm that the model works
income = NetIncome(revenue=Revenue(), expenses=Expenses(variable=VariableExpenses()))
income(2025)
