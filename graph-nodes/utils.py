# Created by jrdnh 2024-01-21
# jrdnh.github.io

import calendar
import heapq
import math
from datetime import date
from itertools import dropwhile, pairwise, takewhile
from typing import Generator

from pydantic import BaseModel
from models import FixedIntervalSeries


####################
# Date functions
def is_month_end(dt: date):
    return dt.day == calendar.monthrange(dt.year, dt.month)[1]


class YF:
    @staticmethod
    def actual360(dt1: date, dt2: date):
        return (dt2 - dt1).days / 360

    @staticmethod
    def thirty360(dt1: date, dt2: date):
        """
        Returns the fraction of a year between `dt1` and `dt2` on 30 / 360 day count basis.
        """
        # Based on this answer https://stackoverflow.com/a/62232820/18582661
        # swap so dt1 is always before dt2
        flipped = 1
        if dt1 > dt2:
            dt1, dt2 = dt2, dt1
            flipped = -1

        y1, m1, d1 = dt1.year, dt1.month, dt1.day
        y2, m2, d2 = dt2.year, dt2.month, dt2.day

        if (m2 == 2 and is_month_end(dt2)) and (m1 == 2 and is_month_end(dt1)):
            d2 = 30
        if d2 == 31 and d1 >= 30:
            d2 = 30
        if d1 == 31:
            d1 = 30
        if m1 == 2 and is_month_end(dt1):
            d1 = 30

        days = (d2 + m2 * 30 + y2 * 360) - (d1 + m1 * 30 + y1 * 360)
        return days / 360 * flipped

    @staticmethod
    def monthly(dt1: date, dt2: date):
        """
        Year fraction from but excluding `dt1` to and including `dt2` where each calendar
        month is 1/12th of a year.
        Partial calendar months are treated as actual days elapsed over actual days in the month.

        Example:
        >>> YF.monthly(date(2020, 1, 31), date(2020, 2, 29))
        0.08333333333333333
        >>> # Not equal to 1/12th of a year because June and July have different number of days
        >>> # equals [(29/30) + (1/31/)] / 12
        >>> YF.monthly(date(2020, 6, 1), date(2020, 7, 1))
        0.0832437275985663
        """
        # swap so dt1 is always before dt2
        flipped = 1
        if dt1 > dt2:
            dt1, dt2 = dt2, dt1
            flipped = -1

        y1, m1, d1 = dt1.year, dt1.month, dt1.day
        y2, m2, d2 = dt2.year, dt2.month, dt2.day

        # year frac assuming whole months
        year_month_frac = ((y2 * 360 + m2 * 30) - (y1 * 360 + m1 * 30)) / 360

        # year frac of starting month stub in range (if any)
        start_month_last_day = calendar.monthrange(y1, m1)[1]
        start_stub = (start_month_last_day - d1) / start_month_last_day

        # year frac of ending month stub *NOT* in range (if any)
        end_month_last_day = calendar.monthrange(y2, m2)[1]
        end_stub = (end_month_last_day - d2) / end_month_last_day

        return (year_month_frac + (start_stub - end_stub) / 12) * flipped


####################
# Iterator helper functions
def merge_series(*series: Generator[date, None, None]):
    """
    Merges generator arguments that yield sorted values into a single sorted series without duplicates.

    >>> merged = merge_series((i for i in [1, 3]), (i for i in range(5)))
    >>> list(merged)
    [0, 1, 2, 3, 4]
    """
    min_heap = heapq.merge(*series)
    last_yielded = None

    for next_value in min_heap:
        if next_value != last_yielded:
            yield next_value
            last_yielded = next_value


def sumproduct(from_dt: date, to_dt: date, *series: FixedIntervalSeries):
    """Sum product of series from `from_dt` to `to_dt`."""
    # merge all event dates
    merged_dates = merge_series(*[s.periods() for s in series], (from_dt, to_dt))

    # filter out dates prior to from_dt and after to_dt
    periods = pairwise(
        dropwhile(
            lambda dt: dt < from_dt, takewhile(lambda dt: dt <= to_dt, merged_dates)
        )
    )

    # calculate sumproduct
    return sum(math.prod(s(dt1, dt2) for s in series) for dt1, dt2 in periods)


####################
# Printing functions
def field_values(series: BaseModel, periods: list[tuple[date, date]]):
    """Recursively get values of all FixedIntervalSeries fields on a depth first basis."""
    values = {}
    try:
        for field in series.model_fields:
            try:
                values[field] = field_values(getattr(series, field), periods)
            except TypeError:
                pass
    except AttributeError:
        pass
    values.update({"": [series(*period) for period in periods]})
    return values


def _flatten_gen(d: dict, parent_key=None):
    for key, value in d.items():
        new_key = (parent_key or '') + '.' + key if key != '' else parent_key or '.'
        if isinstance(value, dict):
            yield from _flatten_gen(value, new_key)
        else:
            yield new_key, value


def flatten(d: dict):
    """Flatten a nested dictionary"""
    return dict(_flatten_gen(d))
