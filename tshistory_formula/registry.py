from warnings import warn
import inspect

from tshistory_formula.decorator import decorate
import pandas as pd


FUNCS = {}
HISTORY = {}
IDATES = {}
METAS = {}
FINDERS = {}
AUTO = {}


def _ensure_options(obj):
    if isinstance(obj, pd.Series):
        if not getattr(obj, 'options', None):
            obj.options = {}
    return obj


def func(name, auto=False):
    # work around the circular import
    from tshistory_formula.helper import assert_typed
    from tshistory_formula.interpreter import Interpreter

    def decorator(func):
        assert_typed(func)

        def _ensure_series_options(func, *a, **kw):
            if name in HISTORY:
                # Autotrophic operator with an history:
                # we redirect from a get call without even evaluating the func
                # because we already have the histories ...
                # (the .histories predicate below indicates we got through
                # the @history protocol just before)
                # To return the right historical pieces we will forge a name
                # made from func signature and actual args.
                if a and isinstance(a[0], Interpreter) and a[0].histories:
                    return _ensure_options(
                        a[0].history_item(name, func, a, kw)
                    )

            res = func(*a, **kw)
            return _ensure_options(
                res
            )

        dec = decorate(func, _ensure_series_options)

        FUNCS[name] = dec
        if auto:
            AUTO[name] = func
        return dec

    return decorator


def history(name):

    def decorator(func):
        assert name in AUTO, f'operator {name} is not declared as "auto"'
        HISTORY[name] = func
        return func

    return decorator


def insertion_dates(name):

    def decorator(func):
        assert name in AUTO, f'operator {name} is not declared as "auto"'
        IDATES[name] = func
        return func

    return decorator



_KEYS = set([
    'index_dtype',
    'index_type',
    'tzaware',
    'value_dtype',
    'value_type'
])


def metadata(name):

    def decorator(func):
        def _ensure_meta_keys(func, *a, **kw):
            res = func(*a, **kw)
            for name, meta in res.items():
                if meta is None:
                    # underlying series is void, must be
                    # register_formula(..., reject_unknown=False)
                    continue
                missing = _KEYS - set(meta.keys())
                if len(missing):
                    warn(
                        f'{name} has missing metadata keys ({missing})'
                    )
            return res

        dec = decorate(func, _ensure_meta_keys)
        METAS[name] = dec
        return dec

    return decorator


def finder(name):

    def decorator(func):
        FINDERS[name] = func
        return func

    return decorator

