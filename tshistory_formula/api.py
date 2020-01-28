from tshistory.util import extend
from tshistory.api import (
    altsources,
    dbtimeseries
)


@extend(dbtimeseries)
def register_formula(self, name, formula,
                     reject_unknown=True, update=False):

    self.tsh.register_formula(
        self.engine,
        name,
        formula,
        reject_unknown=reject_unknown,
        update=update
    )


@extend(dbtimeseries)
def formula(self, name):
    form = self.tsh.formula(self.engine, name)
    if form is None:
        form = self.othersources.formula(name)
    return form


@extend(altsources)
def formula(self, name):
    source = self._findsourcefor(name)
    if source is None:
        return
    return source.tsa.formula(name)

