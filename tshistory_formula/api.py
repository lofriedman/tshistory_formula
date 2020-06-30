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
    form = self.formula(name)

    if form is None:
        if not self.tsh.exists(self.engine, name):
            return self.othersources.formula_components(
                name,
                expanded=expanded
            )
        return

    parsed = parse(form)
    names = list(
        self.tsh.find_series(self.engine, parsed)
    )

    # compute expansion of the remotely defined formula
    remotes = [
        name for name in names
        if not self.tsh.exists(self.engine, name)
        and self.formula(name)
    ]
    if remotes:
        # remote names will be replaced with their expansion
        rnames = []
        for rname in names:
            if rname in remotes:
                rnames.append(
                    self.othersources.formula_components(rname, expanded)
                )
            else:
                rnames.append(rname)
        names = rnames

    if expanded:
        # pass through some formula walls
        # where expansion > formula expansion
        subnames = []
        for cname in names:
            if not isinstance(cname, str) or not self.formula(cname):
                subnames.append(cname)
                continue
            subnames.append(
                self.formula_components(cname, expanded)
            )
        names = subnames

    return {name: names}


@extend(altsources)
def formula_components(self, name, expanded=False):
    source = self._findsourcefor(name)
    if source is None:
        return {}
    return source.tsa.formula_components(name, expanded=expanded)
