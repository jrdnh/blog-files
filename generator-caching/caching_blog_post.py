from functools import lru_cache
import gc

class Foo:
    @lru_cache
    def bar(self):
        print('bar called')
        return 'bar'

    def __del__(self):
        print(f'deleting Foo instance {self}')

foo = Foo()
foo.bar()

# delete foo
del foo

gc.collect()

# weak ref cache
import functools
import weakref

def weak_cache(func):
    cache = {}

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Use weakref for 'self' to avoid memory leaks
        weak_self = weakref.ref(self)
        key = (weak_self, args, tuple(sorted(kwargs.items())))

        if key in cache:
            return cache[key]
        
        result = func(self, *args, **kwargs)
        cache[key] = result
        return result

    return wrapper


class Foo:
    @weak_cache
    def bar(self):
        print('bar called')
        return 'bar'
    
    def __del__(self):
        print(f'deleting Foo instance {self}')

foo = Foo()
foo.bar()

del foo

# set in initializer
import gc
from functools import lru_cache
import weakref

class Foo:
    def __init__(self) -> None:
        self.bar = lru_cache()(self._bar)
    
    def _bar(self):
        return 'bar'
    
    def __del__(self):
        print(f'deleting Foo instance {self}')

foo = Foo()
foo.__dict__
foo.bar()
foo = None
gc.collect()


# cache as property
from functools import wraps

def caching_decorator(func):
    cachename = f"_cached_{func.__qualname__}_"

    @wraps(func)
    def wrapper(self, *args):
        # try to get the cache from the object
        cachedict = getattr(self, cachename, None)
        # if the object doen't have a cache, try to create and add one
        if cachedict is None:
            cachedict = {}
            setattr(self, cachename, cachedict)
        # try to return a cached value,
        # or if it doesn't exist, create it, cache it, and return it
        try:
            return cachedict[args]
        except KeyError:
            pass
        value = func(self, *args)
        cachedict[args] = value
        return value

    return wrapper

class Foo:
    @caching_decorator
    def bar(self, num: int):
        print(f'bar called with {num}')
        return 'bar'
    
    def __del__(self):
        print(f'deleting Foo instance {self}')

foo = Foo()
foo.bar(1)
foo.bar(1)  # cached result is returned
foo.__dict__

foo = None

# generator caching
from itertools import tee
from types import GeneratorType

Tee = tee([], 1)[0].__class__

def memoized(f):
    cache={}
    def ret(*args):
        if args not in cache:
            cache[args]=f(*args)
        if isinstance(cache[args], (GeneratorType, Tee)):
            # the original can't be used any more,
            # so we need to change the cache as well
            cache[args], r = tee(cache[args])
            return r
        return cache[args]
    return ret

# example usage
@memoized
def fibonator():
    a, b = 0, 1
    while True:
        print(f'yielding {a}')
        yield a
        a, b = b, a + b

fib1 = fibonator()
next(fib1)  # will print "yielding"
fib2 = fibonator()
next(fib2)  # will not print "yielding", uses cached value


#######
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

@dataclass
class Operations:
    start_date: date
    freq: relativedelta
    initial_rev: float
    growth_rate: float

    def periods(self):
        """Revenue growth periods"""
        curr = (self.start_date, self.start_date + self.freq)
        while True:
            yield curr
            curr = (curr[1], curr[1] + self.freq)
    
    def amount(self, period_end: date):
        """Revenue for period"""
        revenue = self.initial_rev
        for start, end in self.periods():
            if period_end <= start:
                return revenue
            revenue *= (1 + self.growth_rate * (end - start).days / 360)

rev = Operations(start_date=date(2020, 1, 1), 
                 freq=relativedelta(months=1), 
                 initial_rev=1000.0, 
                 growth_rate=0.1)
rev.amount(date(2021, 1, 1))

from timeit import timeit

def revenue_series():
    return [rev.amount(dt) for dt in (date(2020,1,1) + relativedelta(months=i) for i in range(120))]


count = 100
time = timeit(revenue_series, number=count)
print(f'{time / count * 1000:.2f} ms per iteration')


## generator caching
from itertools import tee
from types import GeneratorType
from functools import wraps

Tee = tee([], 1)[0].__class__

def cached_generator(func):
    cachename = f"_cached_{func.__qualname__}_"

    @wraps(func)
    def wrapper(self, *args):
        # try to get the cache from the object, or create if doesn't exist
        cache = getattr(self, cachename, None)
        if cache is None:
            cache = {}
            setattr(self, cachename, cache)
        # return tee'd generator
        if args not in cache:
            cache[args]=func(self, *args)
        if isinstance(cache[args], (GeneratorType, Tee)):
            cache[args], r = tee(cache[args])
            return r
        return cache[args]

    return wrapper


# example usage
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

@dataclass
class Operations:
    start_date: date
    freq: relativedelta
    initial_rev: float
    growth_rate: float

    @cached_generator
    def periods(self):
        """Revenue growth periods"""
        curr = (self.start_date, self.start_date + self.freq)
        while True:
            yield curr
            curr = (curr[1], curr[1] + self.freq)
    
    def amount(self, period_end: date):
        """Revenue for period"""
        revenue = self.initial_rev
        for start, end in self.periods():
            if period_end <= start:
                return revenue
            revenue *= (1 + self.growth_rate * (end - start).days / 360)


rev = Operations(start_date=date(2020, 1, 1), 
                 freq=relativedelta(months=1), 
                 initial_rev=1000.0, 
                 growth_rate=0.1)

def revenue_series():
    return [rev.amount(dt) for dt in (date(2020,1,1) + relativedelta(months=i) for i in range(120))]

from timeit import timeit

count = 100
time = timeit(revenue_series, number=count)
print(f'{time / count * 1000:.2f} ms per iteration')