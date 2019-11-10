from decorator import decorate
import pandas as pd



FUNCS = {}
FINDERS = {}
EDITORINFOS = {}


def func(name):
    # work around the circular import
    from tshistory_formula.helper import assert_typed

    def decorator(func):
        assert_typed(func)
        def _ensure_series_options(func, *a, **kw):
            res = func(*a, **kw)
            if isinstance(res, pd.Series):
                if not getattr(res, 'options', None):
                    res.options = {}
            return res

        dec = decorate(func, _ensure_series_options)

        FUNCS[name] = dec
        return dec

    return decorator


def finder(name):

    def decorator(func):
        def _ensure_finder_keys(func, *a, **kw):
            res = func(*a, **kw)
            for name, meta in res.items():
                if meta is None:
                    # underlying series is void, must be
                    # register_formula(..., reject_unknown=False)
                    continue
                assert sorted(meta.keys()) == [
                    'index_dtype', 'index_type', 'tzaware',
                    'value_dtype', 'value_type'
                ], f'{name} has missing metadata keys'
            return res

        dec = decorate(func, _ensure_finder_keys)
        FINDERS[name] = dec
        return dec

    return decorator


def editor_info(name):

    def decorator(func):
        EDITORINFOS[name] = func
        return func

    return decorator
