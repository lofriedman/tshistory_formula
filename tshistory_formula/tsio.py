from collections import defaultdict
import json

from psyl.lisp import parse, serialize
from tshistory.util import tx
from tshistory_alias.tsio import timeseries as basets

from tshistory_formula import interpreter
from tshistory_formula.registry import (
    FINDERS,
    FUNCS
)
from tshistory_formula.finder import find_series


class timeseries(basets):
    fast_staircase_operators = set(['+', '*', 'series', 'add', 'priority'])
    internal_metakeys = set(['tzaware', 'index_type', 'value_type'])


    def find_series(self, cn, tree):
        op = tree[0]
        smap = FINDERS.get(op, find_series)(cn, self, tree) or {}
        for item in tree:
            if isinstance(item, list):
                smap.update(
                    self.find_series(cn, item)
                )
        return smap

    def find_operators(self, cn, tree):
        ops = {
            tree[0]: FUNCS.get(tree[0])
        }
        for item in tree:
            if isinstance(item, list):
                newops = self.find_operators(cn, item)
                ops.update(newops)
        return ops

    def filter_metadata(self, series):
        " collect series metadata and make sure they are compatible "
        metamap = {}
        for name, meta in series.items():
            if not meta:
                continue
            metamap[name] = {
                k: v
                for k, v in meta.items()
                if k in self.internal_metakeys
            }
        if not metamap:
            return {}
        first = next(iter(metamap.items()))
        for m in metamap.items():
            if not m[1] == first[1]:
                raise ValueError(
                    f'Formula `{name}`: mismatching metadata:'
                    f'{", ".join("`%s:%s`" % (k, v) for k, v in metamap.items())}'
                )
        return first[1]

    @tx
    def register_formula(self, cn, name, formula,
                         reject_unknown=True, update=False):
        if not update:
            assert not self.formula(cn, name), f'`{name}` already exists'
        # basic syntax check
        tree = parse(formula)
        smap = self.find_series(cn, tree)
        if not all(smap.values()) and reject_unknown:
            badseries = [k for k, v in smap.items() if not v]
            raise ValueError(
                f'Formula `{name}` refers to unknown series '
                f'{", ".join("`%s`" % s for s in badseries)}'
            )
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
        meta = self.filter_metadata(smap)
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
        if meta:
            self.update_metadata(cn, name, meta, internal=True)

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
            i = kw.get('__interpreter__') or interpreter.Interpreter(cn, self, kw)
            ts = i.evaluate(formula)
            if ts is not None:
                ts.name = name
            return ts

        return super().get(cn, name, **kw)

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
                _keep_nans=False):
        if self.type(cn, name) != 'formula':
            return super().history(
                cn, name,
                from_insertion_date,
                to_insertion_date,
                from_value_date,
                to_value_date,
                diffmode,
                _keep_nans
            )

        assert not diffmode

        formula = self.formula(cn, name)
        series = self.find_series(cn, parse(formula))
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
            return super().metadata(cn, name)

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
            smap = self.find_series(
                cn,
                tree
            )
            if newname in smap:
                errors.append(fname)
            if oldname not in smap or errors:
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

    @tx
    def convert_aliases(self, cn):
        sqla = f'select * from "{self.namespace}".arithmetic'
        sqlp = f'select * from "{self.namespace}".priority'

        arith = defaultdict(list)
        for row in cn.execute(sqla).fetchall():
            arith[row.alias].append(row)

        for alias, series in arith.items():
            form = ['(add']
            for idx, row in enumerate(series):
                if row.coefficient != 1:
                    form.append(f' (* {row.coefficient}')

                form.append(f' (series "{row.serie}"')
                if row.fillopt:
                    opt = row.fillopt
                    if opt.startswith('fill='):
                        value = int(opt[opt.index('=') + 1:])
                        form.append(f' #:fill {value}')
                    else:
                        form.append(f' #:fill "{opt}"')
                form.append(')')

                if row.coefficient != 1:
                    form.append(')')
            form.append(')')

            if idx == 0:
                # not really adding there, that was just a
                # coefficient
                form = form[1:-1]

            text = ''.join(form).strip()
            print(alias, '->', text)
            self.register_formula(
                cn,
                alias, text,
                False, True
            )

        prio = defaultdict(list)
        for row in cn.execute(sqlp).fetchall():
            prio[row.alias].append(row)

        for alias, series in prio.items():
            series.sort(key=lambda row: row.priority)
            form = ['(priority']
            for idx, row in enumerate(series):
                if row.coefficient != 1:
                    form.append(f' (* {row.coefficient}')

                form.append(f' (series "{row.serie}"')
                if row.prune:
                    form.append(f' #:prune {row.prune}')
                form.append(')')

                if row.coefficient != 1:
                    form.append(')')
            form.append(')')

            if idx == 0:
                # not a real priority there, that was just a
                # coefficient
                form = form[1:-1]

            text = ''.join(form).strip()
            print(alias, '->', text)
            self.register_formula(
                cn,
                alias, text,
                False, True
            )
