from tshistory.api import dbtimeseries


def monkeypatch(klass):

    def decorator(func):
        setattr(klass, func.__name__, func)
        return func

    return decorator


@monkeypatch(dbtimeseries)
def register_formula(self, name, formula,
                     reject_unknown=True, update=False):

    self.tsh.register_formula(
        self.engine,
        name,
        formula,
        reject_unknown=reject_unknown,
        update=update
    )
