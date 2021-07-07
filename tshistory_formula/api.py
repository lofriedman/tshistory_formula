from typing import Optional, Dict

from psyl.lisp import parse
from tshistory.util import extend
from tshistory.api import (
    altsources,
    dbtimeseries
)


NONETYPE = type(None)


@extend(dbtimeseries)
def register_formula(self,
                     name: str,
                     formula: str,
                     reject_unknown: bool=True,
                     update: bool=False) -> NONETYPE:
    """Define a series as a named formula.

    e.g. `register_formula('sales.eu', '(add (series "sales.fr") (series "sales.be"))')`

    """

    self.tsh.register_formula(
        self.engine,
        name,
        formula,
        reject_unknown=reject_unknown,
        update=update
    )


@extend(dbtimeseries)
def formula(self,
            name: str,
            expanded: bool=False) -> Optional[str]:
    """Get the formula associated with a name.

    """
    form = self.tsh.formula(self.engine, name)
    if form and expanded:
        form = self.tsh.expanded_formula(self.engine, name)
    if form is None:
        form = self.othersources.formula(name, expanded=expanded)
    return form


@extend(altsources)
def formula(self,
            name: str,
            expanded: bool=False) -> Optional[str]:
    source = self._findsourcefor(name)
    if source is None:
        return
    return source.tsa.formula(name, expanded=expanded)


@extend(dbtimeseries)
def formula_components(self,
                       name: str,
                       expanded: bool=False) -> Optional[Dict[str, str]]:
    """Compute a mapping from series name (defined as formulas) to the
    names of the component series.

    If `expanded` is true, it will expand the formula before computing
    the components. Hence only "ground" series (stored or autotrophic
    formulas) will show up in the leaves.


    >>> formula_components('my-series')
    {'show-components': ['component-a', 'component-b']}

    >>> formula_components('my-series-2', expanded=True)
    {'my-series-2': [{'sub-component-1': ['component-a', 'component-b']}, 'component-b']}

    """
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
def formula_components(self,
                       name: str,
                       expanded: bool=False) -> Optional[Dict[str, str]]:
    source = self._findsourcefor(name)
    if source is None:
        return {}
    return source.tsa.formula_components(name, expanded=expanded)
