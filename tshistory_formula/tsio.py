from collections import defaultdict
import json

import pandas as pd
from psyl.lisp import parse, serialize
from tshistory.tsio import timeseries as basets
from tshistory.util import tx

from tshistory_formula import funcs  # trigger registration
from tshistory_formula import (
    api,  # trigger extension
    interpreter,
    helper
)
from tshistory_formula.registry import (
    FINDERS,
    FUNCS,
    HISTORY
)


class timeseries(basets):
    fast_staircase_operators = set(['+', '*', 'series', 'add', 'priority'])
    metadata_compat_excluded = ()

    def find_series(self, cn, tree):
        op = tree[0]
        finder = FINDERS.get(op)
        seriesmeta = finder(cn, self, tree) if finder else {}
        for item in tree:
            if isinstance(item, list):
                seriesmeta.update(
                    self.find_series(cn, item)
                )
        return seriesmeta

    def find_callsites(self, cn, operator, tree):
        op = tree[0]
        sites = []
        if op == operator:
            sites.append(tree)
        for item in tree:
            if isinstance(item, list):
                sites.extend(
                    self.find_callsites(cn, operator, item)
                )
        return sites

    def find_operators(self, cn, tree):
        ops = {
            tree[0]: FUNCS.get(tree[0])
        }
        for item in tree:
            if isinstance(item, list):
                newops = self.find_operators(cn, item)
                ops.update(newops)
        return ops

    def check_tz_compatibility(self, cn, tree):
        """check that series are timezone-compatible
        """

        def find_meta(tree, tzstatus, path=()):
            op = tree[0]
            path = path + (op,)
            finder = FINDERS.get(op)
            if finder:
                for name, metadata in finder(cn, self, tree).items():
                    tzaware = metadata['tzaware'] if metadata else None
                    if 'naive' in path:
                        tzaware = False
                    tzstatus[(name, path)] = tzaware
            for item in tree:
                if isinstance(item, list):
                    find_meta(item, tzstatus, path)

        metamap = {}
        find_meta(tree, metamap)
        if not metamap:
            return {}

        def tzlabel(status):
            return 'tzaware' if status else 'tznaive'
        first_tzaware = next(iter(metamap.values()))
        for (name, path), tzaware in metamap.items():
            if first_tzaware != tzaware:
                raise ValueError(
                    f'Formula `{name}` has tzaware vs tznaive series:'
                    f'{",".join("`%s:%s`" % (k, tzlabel(v)) for k, v in metamap.items())}'
                )
        return first_tzaware

    @tx
    def register_formula(self, cn, name, formula,
                         reject_unknown=True, update=False):
        if not update:
            assert not self.formula(cn, name), f'`{name}` already exists'
        if self.exists(cn, name) and self.type(cn, name) == 'primary':
            raise TypeError(
                f'primary series `{name}` cannot be overriden by a formula'
            )
        # basic syntax check
        tree = parse(formula)
        formula = serialize(tree)

        # bad operators
        operators = self.find_operators(cn, tree)
        badoperators = [
            op
            for op, func in operators.items()
            if func is None
        ]
        if badoperators:
            raise ValueError(
                f'Formula `{name}` refers to unknown operators '
                f'{", ".join("`%s`" % o for o in badoperators)}'
            )

        # type checking
        i = interpreter.Interpreter(cn, self, {})
        rtype = helper.typecheck(tree, env=i.env)
        if not helper.sametype(rtype, pd.Series):
            raise TypeError(
                f'formula `{name}` must return a `Series`, not `{rtype.__name__}`'
            )

        # build metadata & check compat
        seriesmeta = self.find_series(cn, tree)
        if not all(seriesmeta.values()) and reject_unknown:
            badseries = [k for k, v in seriesmeta.items() if not v]
            raise ValueError(
                f'Formula `{name}` refers to unknown series '
                f'{", ".join("`%s`" % s for s in badseries)}'
            )

        tzaware = self.check_tz_compatibility(cn, tree)
        sql = (f'insert into "{self.namespace}".formula '
               '(name, text) '
               'values (%(name)s, %(text)s) '
               'on conflict (name) do update '
               'set text = %(text)s')
        cn.execute(
            sql,
            name=name,
            text=formula
        )

        # save metadata
        if tzaware is None:
            # bad situation ...
            return
        for meta in seriesmeta.values():
            # crappy heuristics
            meta.pop('expandable', None)
            if meta['tzaware'] != tzaware:
                # we were flipped
                meta = self.default_meta(tzaware)
            self.update_metadata(cn, name, meta, internal=True)
            break

    def default_meta(self, tzaware):
        if tzaware:
            return {
                'tzaware': True,
                'index_type': 'datetime64[ns, UTC]',
                'value_type': 'float64',
                'index_dtype': '|M8[ns]',
                'value_dtype': '<f8'
            }
        return {
            'index_dtype': '<M8[ns]',
            'index_type': 'datetime64[ns]',
            'tzaware': False,
            'value_dtype': '<f8',
            'value_type': 'float64'
        }

    def formula(self, cn, name):
        formula = cn.execute(
            f'select text from "{self.namespace}".formula where name = %(name)s',
            name=name
        ).scalar()
        return formula

    def list_series(self, cn):
        series = super().list_series(cn)
        sql = f'select name from "{self.namespace}".formula'
        series.update({
            name: 'formula'
            for name, in cn.execute(sql)
        })
        return series

    def type(self, cn, name):
        if self.formula(cn, name):
            return 'formula'

        return super().type(cn, name)

    def exists(self, cn, name):
        return super().exists(cn, name) or self.formula(cn, name)

    @tx
    def get(self, cn, name, **kw):
        formula = self.formula(cn, name)
        if formula:
            ts = self.eval_formula(cn, formula, **kw)
            if ts is not None:
                ts.name = name
            return ts

        ts = super().get(cn, name, **kw)
        if ts is None and self.othersources:
            ts = self.othersources.get(
                name, **kw
            )

        return ts

    def eval_formula(self, cn, formula, **kw):
        i = kw.get('__interpreter__') or interpreter.Interpreter(cn, self, kw)
        ts = i.evaluate(formula)
        return ts

    def expanded_formula(self, cn, name):
        formula = self.formula(cn, name)
        tree = parse(formula)

        return serialize(
            helper.expanded(self, cn, tree)
        )

    @tx
    def delete(self, cn, name):
        if self.type(cn, name) != 'formula':
            return super().delete(cn, name)

        cn.execute(
            f'delete from "{self.namespace}".formula '
            'where name = %(name)s',
            name=name
        )

    @tx
    def history(self, cn, name,
                from_insertion_date=None,
                to_insertion_date=None,
                from_value_date=None,
                to_value_date=None,
                diffmode=False,
                _keep_nans=False,
                _tree=None):

        if self.type(cn, name) != 'formula':

            # autotrophic operator ?
            if name is None:
                assert _tree
                i = interpreter.OperatorHistory(
                    cn, self, {
                        'from_value_date': from_value_date,
                        'to_value_date': to_value_date,
                        'from_insertion_date': from_insertion_date,
                        'to_insertion_date': to_insertion_date,
                        'diffmode': diffmode,
                        '_keep_nans': _keep_nans
                    }
                )
                return i.evaluate_history(_tree)

            # normal series ?
            hist = super().history(
                cn, name,
                from_insertion_date,
                to_insertion_date,
                from_value_date,
                to_value_date,
                diffmode,
                _keep_nans
            )

            # alternative source ?
            if hist is None and self.othersources:
                hist = self.othersources.history(
                    name,
                    from_value_date=from_value_date,
                    to_value_date=to_value_date,
                    from_insertion_date=from_insertion_date,
                    to_insertion_date=to_insertion_date,
                    _keep_nans=_keep_nans
                )
            return hist

        assert not diffmode

        formula = self.formula(cn, name)
        tree = parse(formula)
        series = self.find_series(cn, tree)

        # normal history
        histmap = {
            name: self.history(
                cn, name,
                from_insertion_date,
                to_insertion_date,
                from_value_date,
                to_value_date,
                diffmode
            ) or {}
            for name in series
        }

        # prepare work for autotrophic operator history
        callsites = []
        for sname in HISTORY:
            for call in self.find_callsites(cn, sname, tree):
                callsites.append(call)

        # autotrophic history
        histmap.update({
            name: self.history(
                cn,
                None, # just mark that we won't work "by name" there
                from_insertion_date,
                to_insertion_date,
                from_value_date,
                to_value_date,
                diffmode,
                _tree=callsite
            ) or {}
            for callsite in callsites
        })

        i = interpreter.HistoryInterpreter(
            cn, self, {
                'from_value_date': from_value_date,
                'to_value_date': to_value_date
            },
            histories=histmap
        )
        idates = {
            idate
            for hist in histmap.values()
            for idate in hist
        }

        return {
            idate: i.evaluate(formula, idate, name)
            for idate in sorted(idates)
        }

    @tx
    def insertion_dates(self, cn, name,
                        fromdate=None, todate=None):
        if self.type(cn, name) != 'formula':
            return super().insertion_dates(
                cn, name,
                fromdate=fromdate,
                todate=todate
            )

        formula = self.formula(cn, name)
        series = self.find_series(cn, parse(formula))
        allrevs = []
        for name in series:
            allrevs += self._revisions(
                cn, name,
                from_insertion_date=fromdate,
                to_insertion_date=todate
            )
        return sorted(set(allrevs))

    @tx
    def staircase(self, cn, name, delta,
                  from_value_date=None,
                  to_value_date=None):
        formula = self.formula(cn, name)
        if formula:
            if interpreter.has_compatible_operators(
                    cn, self,
                    parse(formula),
                    self.fast_staircase_operators):
                # go fast
                return self.get(
                    cn, name,
                    from_value_date=from_value_date,
                    to_value_date=to_value_date,
                    __interpreter__=interpreter.FastStaircaseInterpreter(
                        cn, self,
                        {'from_value_date': from_value_date,
                         'to_value_date': to_value_date},
                        delta
                    )
                )

        return super().staircase(
            cn, name, delta,
            from_value_date,
            to_value_date
        )

    @tx
    def metadata(self, cn, name):
        """Return metadata dict of timeserie."""
        if self.type(cn, name) != 'formula':
            return super().metadata(cn, name)

        sql = (f'select metadata from "{self.namespace}".formula '
               'where name = %(name)s')
        meta = cn.execute(sql, name=name).scalar()
        return meta

    @tx
    def update_metadata(self, cn, name, metadata, internal=False):
        if self.type(cn, name) != 'formula':
            return super().update_metadata(cn, name, metadata, internal)

        assert isinstance(metadata, dict)
        meta = self.metadata(cn, name) or {}
        meta.update(metadata)
        sql = (f'update "{self.namespace}".formula '
               'set metadata = %(metadata)s '
               'where name = %(name)s')
        cn.execute(
            sql,
            metadata=json.dumps(meta),
            name=name
        )

    @tx
    def rename(self, cn, oldname, newname):
        # read all formulas and parse them ...
        formulas = cn.execute(
            f'select name, text from "{self.namespace}".formula'
        ).fetchall()
        errors = []

        def edit(tree, oldname, newname):
            newtree = []
            series = False
            for node in tree:
                if isinstance(node, list):
                    newtree.append(edit(node, oldname, newname))
                    continue
                if node == 'series':
                    series = True
                    newtree.append(node)
                    continue
                elif node == oldname and series:
                    node = newname
                newtree.append(node)
                series = False
            return newtree

        for fname, text in formulas:
            tree = parse(text)
            seriesmeta = self.find_series(
                cn,
                tree
            )
            if newname in seriesmeta:
                errors.append(fname)
            if oldname not in seriesmeta or errors:
                continue

            newtree = edit(tree, oldname, newname)
            newtext = serialize(newtree)
            sql = (f'update "{self.namespace}".formula '
                   'set text = %(text)s '
                   'where name = %(name)s')
            cn.execute(
                sql,
                text=newtext,
                name=fname
            )

        if errors:
            raise ValueError(
                f'new name is already referenced by `{",".join(errors)}`'
            )

        if self.type(cn, oldname) == 'formula':
            cn.execute(
                f'update "{self.namespace}".formula '
                'set name = %(newname)s '
                'where name = %(oldname)s',
                oldname=oldname,
                newname=newname
            )
        else:
            super().rename(cn, oldname, newname)
