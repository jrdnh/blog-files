# Created by jrdnh 2024-01-21
# jrdnh.github.io

import weakref
from datetime import date
from typing import Annotated, Any, Optional, Type, TypeVar

from dateutil.relativedelta import relativedelta, weekday
from pydantic import BaseModel, Field, model_serializer, model_validator
from pydantic_core import core_schema


####################
# Pydantic-compatible wrappers
class WeekdayAnnotations(BaseModel):
    """Pydantic-comptible wrapper for dateutil._common.weekday."""
    weekday: int = Field(ge=0, le=6)
    n: int | None = None

    @model_validator(mode="wrap")
    def _validate(
        value, handler: core_schema.ValidatorFunctionWrapHandler
    ) -> relativedelta:
        # if already dateutil._common.weekday instance, return it
        if isinstance(value, weekday):
            return value

        # otherwise run model validation, which returns either a
        # a dateutil._common.weekday or a WeekdayAnnotations
        validated = handler(value)
        if isinstance(validated, weekday):
            return validated

        kwargs = {k: v for k, v in dict(validated).items() if v is not None}
        return weekday(**kwargs)

    @model_serializer(mode="plain")
    def _serialize(self: weekday) -> dict[str, Any]:
        return {"weekday": self.weekday, "n": self.n}


Weekday = Annotated[weekday, WeekdayAnnotations]


class RelativeDeltaAnnotation(BaseModel):
    """Pydantic-comptible wrapper for dateutil.relativedelta.relativedelta."""
    years: int | None = None
    months: int | None = None
    days: int | None = None
    hours: int | None = None
    minutes: int | None = None
    seconds: int | None = None
    microseconds: int | None = None
    year: int | None = None
    # recommended way to avoid potential errors for compound types with constraints
    # https://docs.pydantic.dev/dev/concepts/fields/#numeric-constraints
    month: Optional[Annotated[int, Field(ge=1, le=12)]] = None
    day: Optional[Annotated[int, Field(ge=0, le=31)]] = None
    hour: Optional[Annotated[int, Field(ge=0, le=23)]] = None
    minute: Optional[Annotated[int, Field(ge=0, le=59)]] = None
    second: Optional[Annotated[int, Field(ge=0, le=59)]] = None
    microsecond: Optional[Annotated[int, Field(ge=0, le=999999)]] = None
    weekday: Weekday | None = None
    leapdays: int | None = None
    # validation only fields
    yearday: int | None = Field(None, exclude=True)
    nlyearday: int | None = Field(None, exclude=True)
    weeks: int | None = Field(None, exclude=True)
    dt1: int | None = Field(None, exclude=True)
    dt2: int | None = Field(None, exclude=True)

    @model_validator(mode="wrap")
    def _validate(
        value, handler: core_schema.ValidatorFunctionWrapHandler
    ) -> relativedelta:
        if isinstance(value, relativedelta):
            return value

        validated = handler(value)
        if isinstance(validated, relativedelta):
            return validated

        kwargs = {k: v for k, v in dict(validated).items() if v is not None}
        return relativedelta(**kwargs)
    
    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """Custom serializer to remove None values and 0 values."""
        serialized_wo_nones = {k: v for k, v in handler(self).items() if v is not None}
        return {k: v for k, v in serialized_wo_nones.items() if v != 0}
        

RelativeDelta = Annotated[relativedelta, RelativeDeltaAnnotation]


####################
# Node class
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
    def parent(self) -> P:
        """Parent node or None."""
        return self._parent() if self._parent is not None else None
    
    @parent.setter
    def parent(self, parent: Optional[P] = None):
        """Set parent."""
        self._parent = weakref.ref(parent) if parent is not None else None
    
    def set_parent(self, parent: P):
        """Set parent and return self."""
        self.parent = parent
        return self
    
    def find_parent(self, cls: Type[T]) -> T:
        """Find first parent node with class `cls`."""
        if isinstance(self.parent, cls):
            return self.parent
        try:
            return self.parent.find_parent(cls)  # type: ignore
        except AttributeError:
            raise ValueError(f'No parent of type {cls} found.')


####################
# Fixed interval driver class
class FixedIntervalSeries[P](Node[P]):
    """
    Class that yields dates with a fixed interval duration.

    Args:
        ref_date: Reference date for the start of the first period.
        freq: Fixed interval duration.
    """
    ref_date: date
    freq: RelativeDelta

    def periods(self):
        """
        Yield dates with a fixed interval.
        
        Examples:
        >>> from datetime import date
        >>> from dateutil.relativedelta import relativedelta
        >>> 
        >>> series = FixedIntervalSeries(ref_date=date(2020, 1, 1), freq=relativedelta(months=1))
        >>> series_generator = series.periods()
        >>> print([next(series_generator) for _ in range(3)])
        [datetime.date(2020, 1, 1), datetime.date(2020, 2, 1), datetime.date(2020, 3, 1)]

        # Use pairwise to create (period start date, period end date) tuples
        # E.g. to create to period tuples
        >>> from itertools import islice, pairwise
        >>>
        >>> list(islice(pairwise(series.periods()), 2))
        [(datetime.date(2020, 1, 1), datetime.date(2020, 2, 1)), (datetime.date(2020, 2, 1), datetime.date(2020, 3, 1))]
        """
        index = 0
        curr_date = self.ref_date
        while True:
            yield (curr_date + self.freq * index)
            index += 1
