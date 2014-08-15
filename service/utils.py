import datetime
import functools

from memoize import Memoizer

store = {}
memo = Memoizer(store)


def next_month(year, month):
    """
    Return the year and month of the next month
    NOTE: month is 1 based
    """
    if month == 12:
        return year+1, 1
    return year, month+1


def record_runtime(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        start = datetime.datetime.now()
        ret = func(*args, **kwargs)
        diff = datetime.datetime.now() - start
        ret['runtime'] = diff.total_seconds()
        return ret
    return inner
