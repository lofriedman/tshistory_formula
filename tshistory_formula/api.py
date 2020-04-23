from psyl.lisp import parse
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
def formula(self, name, expanded=False):
    form = self.tsh.formula(self.engine, name)
    if form and expanded:
        form = self.tsh.expanded_formula(self.engine, name)
    if form is None:
        form = self.othersources.formula(name, expanded=expanded)
    return form


@extend(altsources)
def formula(self, name, expanded=False):
    source = self._findsourcefor(name)
    if source is None:
        return
    return source.tsa.formula(name, expanded=expanded)



@extend(dbtimeseries)
def formula_components(self, name, expanded=False):
    form = self.formula(name, expanded=expanded)
    if form is None:
        return {}
    parsed = parse(form)
    return self.tsh.find_series(self.engine, parsed)

