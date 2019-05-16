from collections import defaultdict

from sqlalchemy import select
from psyl.lisp import parse, serialize

from tshistory_alias.tsio import timeseries as basets

from tshistory_formula.schema import formula_schema
from tshistory_formula import interpreter


class timeseries(basets):

    def __init__(self, namespace='tsh'):
        super().__init__(namespace)
        self.formula_schema = formula_schema(namespace)
        self.formula_schema.define()

    def find_series(self, cn, stree):
        smap = {}
        if stree[0] == 'series':
            name = stree[1]
            smap[name] = self.exists(cn, name)
            return smap

        for arg in stree[1:]:
            if isinstance(arg, list):
                smap.update(self.find_series(cn, arg))

        return smap

    def register_formula(self, cn, name, formula,
                         reject_unkown=True, update=False):
        if not update:
            assert not self.formula(cn, name), f'`{name}` already exists'
        # basic syntax check
        smap = self.find_series(
            cn,
            parse(formula)
        )
        if not all(smap.values()) and reject_unkown:
            badseries = [k for k, v in smap.items() if not v]
            raise ValueError(
                f'Formula `{name}` refers to unknown series '
                f'{", ".join("`%s`" % s for s in badseries)}'
            )
        sql = (f'insert into "{self.namespace}-formula".formula '
               '(name, text) '
               'values (%(name)s, %(text)s) '
               'on conflict (name) do update '
               'set text = %(text)s')
        cn.execute(
            sql,
            name=name,
            text=formula
        )

    def formula(self, cn, name):
        table = self.formula_schema.formula
        formula = cn.execute(
            select([table.c.text]).where(
                table.c.name==name
            )
        ).scalar()
        return formula

    def list_series(self, cn):
        series = super().list_series(cn)
        sql = f'select name from "{self.namespace}-formula".formula'
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

    def get(self, cn, name, **kw):
        formula = self.formula(cn, name)
        if formula:
            i = interpreter.Interpreter(cn, self, kw)
            ts = i.evaluate(formula)
            if ts is not None:
                ts.name = name
            return ts

        return super().get(cn, name, **kw)

    def history(self, cn, name,
                from_insertion_date=None,
                to_insertion_date=None,
                from_value_date=None,
                to_value_date=None,
                deltabefore=None,
                deltaafter=None,
                diffmode=False,
                _keep_nans=False):
        if self.type(cn, name) != 'formula':
            return super().history(
                cn, name,
                from_insertion_date,
                to_insertion_date,
                from_value_date,
                to_value_date,
                deltabefore,
                deltaafter,
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
                deltabefore,
                deltaafter,
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

    def rename(self, cn, oldname, newname):
        # read all formulas and parse them ...
        table = self.formula_schema.formula
        formulas = cn.execute(
            select([table.c.name, table.c.text])
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
            sql = table.update().where(
                table.c.name == fname
            ).values(
                text=newtext
            )
            cn.execute(sql)

        if errors:
            raise ValueError(
                f'new name is already referenced by `{",".join(errors)}`'
            )

        super().rename(cn, oldname, newname)

    def convert_aliases(self, cn):
        sqla = f'select * from "{self.namespace}-alias".arithmetic'
        sqlp = f'select * from "{self.namespace}-alias".priority'

        arith = defaultdict(list)
        for row in cn.execute(sqla).fetchall():
            arith[row.alias].append(row)

        for alias, series in arith.items():
            if self.formula(cn, alias):
                print(f'skipping known formula `{alias}`')
                continue
            form = ['(add']
            for idx, row in enumerate(series):
                if row.coefficient != 1:
                    form.append(f' (* {row.coefficient}')
                form.append(f' (series "{row.serie}"')
                if row.fillopt:
                    form.append(f' #:fill "{row.fillopt}"')
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
                False
            )

        prio = defaultdict(list)
        for row in cn.execute(sqlp).fetchall():
            prio[row.alias].append(row)

        for alias, series in prio.items():
            if self.formula(cn, alias):
                print(f'skipping known formula `{alias}`')
                continue
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
                False
            )
