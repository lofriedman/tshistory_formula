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
    if expanded:
        form = self.tsh.expanded_formula(
            self.engine,
            name
        )
    else:
        form = self.tsh.formula(
            self.engine,
            name
        )

    if form is None:
        return self.othersources.formula_components(
            name,
            expanded=expanded
        )

    parsed = parse(form)
    components = self.tsh.find_series(self.engine, parsed)

    # compute expansion of the remotely defined formula
    remotes = [
        name for name in components
        if not self.tsh.exists(self.engine, name)
    ]
    if remotes:
        # remote names will be replaced with their expansion
        for remote in remotes:
            components.pop(remote)
        for remote in remotes:
            components.update(
                self.othersources.formula_components(remote, expanded)
            )

    # NOTE: we want to run formula_components against those again
    # because some series formula components > what shows the formula expansion
    return components


@extend(altsources)
def formula_components(self, name, expanded=False):
    source = self._findsourcefor(name)
    if source is None:
        return {}
    return source.tsa.formula_components(name, expanded=expanded)
