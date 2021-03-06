from collections import defaultdict
from datetime import timedelta
import itertools
import json

import pandas as pd
from psyl.lisp import parse, serialize
from tshistory.tsio import timeseries as basets
from tshistory.util import (
    diff,
    tx
)

from tshistory_formula import funcs, gfuncs  # trigger registration
from tshistory_formula import (
    api,  # trigger extension
    interpreter,
    helper
)
from tshistory_formula.registry import (
    FINDERS,
    FUNCS,
    HISTORY,
    IDATES,
    METAS
)


class timeseries(basets):
    fast_staircase_operators = set(['+', '*', 'series', 'add', 'priority'])
    metadata_compat_excluded = ()

    def find_series(self, cn, tree):
        op = tree[0]
        finder = FINDERS.get(op)
        seriestree = finder(cn, self, tree) if finder else {}
        for item in tree:
            if isinstance(item, list):
                seriestree.update(
                    self.find_series(cn, item)
                )
        return seriestree

    def find_metas(self, cn, tree):
        op = tree[0]
        metas = METAS.get(op)
        seriesmeta = metas(cn, self, tree) if metas else {}
        for item in tree:
            if isinstance(item, list):
                seriesmeta.update(
                    self.find_metas(cn, item)
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
            metas = METAS.get(op)
            if metas:
                for name, metadata in metas(cn, self, tree).items():
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
            if status is None: return 'unknown'
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
        update = self.exists(cn, name)
        if update and self.type(cn, name) == 'primary':
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
        seriesmeta = self.find_metas(cn, tree)
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

        coremeta = self.default_meta(tzaware)
        meta = self.metadata(cn, name) or {}
        meta = dict(meta, **coremeta)
        self.update_metadata(cn, name, meta, internal=True)

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
        return super().exists(cn, name) or bool(self.formula(cn, name))

    def update(self, cn, updatets, name, author, **k):
        if self.type(cn, name) == 'formula':
            raise ValueError(f'`{name}` is a formula, it cannot be updated')

        return super().update(cn, updatets, name, author, **k)

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
        ts = i.evaluate(
            self._expanded_formula(cn, formula)
        )
        return ts

    def _expanded_formula(self, cn, formula, stopnames=()):
        return helper.expanded(
            self, cn, parse(formula), stopnames=stopnames
        )

    def expanded_formula(self, cn, name, stopnames=()):
        formula = self.formula(cn, name)
        if formula is None:
            return

        tree = self._expanded_formula(cn, formula, stopnames)
        if tree is None:
            return

        return serialize(tree)

    @tx
    def delete(self, cn, name):
        if self.type(cn, name) != 'formula':
            return super().delete(cn, name)

        cn.execute(
            f'delete from "{self.namespace}".formula '
            'where name = %(name)s',
            name=name
        )

    def _custom_history_sites(self, cn, tree):
        return [
            call
            for sname in HISTORY
            for call in self.find_callsites(cn, sname, tree)
        ]

    def _custom_idates_sites(self, cn, tree):
        return [
            call
            for sname in IDATES
            for call in self.find_callsites(cn, sname, tree)
        ]


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

        formula = self.formula(cn, name)
        tree = self._expanded_formula(cn, formula)
        series = self.find_series(cn, tree)

        # normal history
        histmap = {
            name: self.history(
                cn, name,
                from_insertion_date,
                to_insertion_date,
                from_value_date,
                to_value_date
            ) or {}
            for name in series
        }

        # complete the history with a value for the first idate
        # (we might be missing this because of the query from_insertion_date)
        if histmap:
            mins = [
                min(hist.keys())
                for hist in histmap.values()
                if len(hist)
            ]
            if len(mins):
                mindate = min(mins)
                for name, hist in histmap.items():
                    if mindate not in hist:
                        ts_mindate = self.get(
                            cn,
                            name,
                            revision_date=mindate,
                            from_value_date=from_value_date,
                            to_value_date=to_value_date,
                        )
                        if ts_mindate is not None and len(ts_mindate):
                            # the history must be ordered by key
                            base = {mindate: ts_mindate}
                            base.update(hist)
                            histmap[name] = base

        i = interpreter.HistoryInterpreter(
            name, cn, self, {
                'from_value_date': from_value_date,
                'to_value_date': to_value_date
            },
            histories=histmap
        )

        # prepare work for autotrophic operator history
        callsites = self._custom_history_sites(cn, tree)

        if callsites:
            # autotrophic history
            for idx, callsite in enumerate(callsites):
                chist = self.history(
                    cn,
                    None, # just mark that we won't work "by name" there
                    from_insertion_date,
                    to_insertion_date,
                    from_value_date,
                    to_value_date,
                    _tree=callsite
                ) or {}
                cname = helper.name_of_expr(callsite)
                i.namecache[serialize(callsite)] = cname
                i.histories.update({
                    cname: chist
                })

        idates = sorted({
            idate
            for hist in histmap.values()
            for idate in hist
        })
        h = {
            idate: i.evaluate(tree, idate, name)
            for idate in idates
        }

        if diffmode and idates:
            iteridates = iter(idates)
            firstidate = next(iteridates)
            basets = self.get(
                cn,
                name,
                from_value_date=from_value_date,
                to_value_date=to_value_date,
                revision_date=firstidate - timedelta(seconds=1)
            )
            newh = {}
            for idate in idates:
                newts = diff(basets, h[idate])
                newh[idate] = newts
                basets = h[idate]

            h = newh

        return h

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
        tree = parse(formula)
        series = self.find_series(cn, tree)
        allrevs = []
        for name in series:
            if not self.exists(cn, name):
                if self.othersources:
                    allrevs += self.othersources.insertion_dates(
                        name,
                        fromdate,
                        todate
                    )
                continue
            if self.formula(cn, name):
                allrevs += self.insertion_dates(
                    cn, name,
                    fromdate,
                    todate
                )
            else:
                allrevs += [
                    idate
                    for _id, idate in self._revisions(
                            cn, name,
                            from_insertion_date=fromdate,
                            to_insertion_date=todate
                    )]

        # autotrophic operators
        isites = self._custom_idates_sites(cn, tree)
        for site in isites:
            fname = site[0]
            idates_func = IDATES[fname]
            revs = idates_func(cn, self, site, fromdate, todate)
            if revs:
                allrevs += revs

        # last resort: get the idates from a full history
        # not great wrt performance ...
        for site in self._custom_history_sites(cn, tree):
            if site in isites:
                continue  # we're already good
            hist = self.history(
                cn,
                None, # just mark that we won't work "by name" there
                fromdate,
                todate,
                _tree=site
            )
            if hist:
                allrevs += list(hist.keys())

        # /auto

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
        newmeta = {
            key: meta[key]
            for key in self.metakeys
            if meta.get(key) is not None
            and key not in self.metadata_compat_excluded
        }
        newmeta.update(metadata)
        sql = (f'update "{self.namespace}".formula '
               'set metadata = %(metadata)s '
               'where name = %(name)s')
        cn.execute(
            sql,
            metadata=json.dumps(newmeta),
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
            series = self.find_series(
                cn,
                tree
            )
            if newname in series:
                errors.append(fname)
            if oldname not in series or errors:
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

    # groups

    @tx
    def group_type(self, cn, name):
        if self.group_formula(cn, name) is not None:
            return 'formula'
        if self.bindings_for(cn, name):
            return 'bound'
        return super().group_type(cn, name)

    @tx
    def group_exists(self, cn, name):
        kind = self.group_type(cn, name)
        if kind == 'primary':
            return super().group_exists(cn, name)
        assert kind in ('formula', 'bound')
        return True

    @tx
    def group_metadata(self, cn, name):
        kind = self.group_type(cn, name)
        if kind == 'primary':
            return super().group_metadata(cn, name)

        if kind == 'formula':
            table, col = 'group_formula', 'name'
        else:
            assert kind == 'bound'
            table, col = 'group_binding', 'groupname'

        return cn.execute(
            f'select metadata from "{self.namespace}".{table} '
            f'where {col} = %(name)s',
            name=name
        ).scalar() or {}

    @tx
    def update_group_metadata(self, cn, name, meta):
        kind = self.group_type(cn, name)
        if kind == 'primary':
            return super().update_group_metadata(cn, name, meta)

        if kind == 'formula':
            table, col = 'group_formula', 'name'
        else:
            assert kind == 'bound'
            table, col = 'group_binding', 'groupname'

        sql = (
            f'update "{self.namespace}".{table} '
            'set metadata = %(metadata)s '
            f'where {col} = %(name)s'
        )
        cn.execute(
            sql,
            metadata=json.dumps(meta),
            name=name
        )

    @tx
    def register_group_formula(self, cn,
                               name, formula):
        if self.group_exists(cn, name) and self.group_type(cn, name) != 'formula':
            raise TypeError(
                f'cannot register formula `{name}`: already a `{self.group_type(cn, name)}`'
            )
        # basic syntax check
        tree = parse(formula)
        formula = serialize(tree)

        # type checking
        i = interpreter.GroupInterpreter(cn, self, {})
        rtype = helper.typecheck(tree, env=i.env)
        if not helper.sametype(rtype, pd.DataFrame):
            raise TypeError(
                f'formula `{name}` must return a `DataFrame`, not `{rtype.__name__}`'
            )

        sql = (
            f'insert into "{self.namespace}".group_formula (name, text) '
            'values (%(name)s, %(text)s) '
            'on conflict (name) do update '
            'set text = %(text)s'
        )
        cn.execute(
            sql,
            name=name,
            text=formula
        )

    @tx
    def group_formula(self, cn, groupname):
        res = cn.execute(
            f'select text from "{self.namespace}".group_formula '
            'where name = %(name)s',
            name=groupname
        )
        return res.scalar()

    @tx
    def list_groups(self, cn):
        cat = super().list_groups(cn)
        cat.update({
            name: 'formula'
            for name, in cn.execute(
                    f'select name from "{self.namespace}".group_formula'
            ).fetchall()
        })
        cat.update({
            name: 'bound'
            for name, in cn.execute(
                    f'select groupname from "{self.namespace}".group_binding'
            ).fetchall()
        })
        return cat

    @tx
    def group_delete(self, cn, name):
        kind = self.group_type(cn, name)
        if kind == 'primary':
            return super().group_delete(cn, name)

        if kind == 'formula':
            sql = (
                f'delete from "{self.namespace}".group_formula '
                'where name = %(name)s'
            )
        else:
            assert kind == 'bound'
            sql = (
                f'delete from "{self.namespace}".group_binding '
                'where groupname = %(name)s'
            )
        cn.execute(sql, name=name)

    @tx
    def group_get(self, cn, groupname,
                  revision_date=None,
                  from_value_date=None,
                  to_value_date=None):
        # case of formula
        formula = self.group_formula(cn, groupname)
        if formula:
            interp = interpreter.GroupInterpreter(
                cn, self,
                dict(
                    revision_date=revision_date,
                    from_value_date=from_value_date,
                    to_value_date=to_value_date
                )
            )
            df = self.eval_formula(
                cn, formula,
                revision_date=revision_date,
                from_value_date=from_value_date,
                to_value_date=to_value_date,
                __interpreter__=interp
            )
            if df.index.dtype != 'object':
                df.columns = [str(col) for col in df.columns]
            if df.index.name:
                df.index.name = None
            return df

        bindinfo = self.bindings_for(
            cn, groupname
        )
        if bindinfo:
            return self._hijacked_formula(
                cn,
                bindinfo[0],
                bindinfo[1],
                revision_date=revision_date,
                from_value_date=from_value_date,
                to_value_date=to_value_date
            )

        return super().group_get(
            cn,
            groupname,
            revision_date=revision_date,
            from_value_date=from_value_date,
            to_value_date=to_value_date
        )

    # group formula binding

    @tx
    def register_formula_bindings(self, cn, groupname, formulaname, binding):
        if set(binding.columns) != {'series', 'group', 'family'}:
            raise ValueError(
                'bindings must have `series` `groups` and `family` columns'
            )

        if not len(binding):
            raise ValueError(f'formula `{formulaname}` has an empty binding')

        if self.type(cn, formulaname) != 'formula':
            raise ValueError(f'`{formulaname}` is not a formula')

        gtype = self.group_type(cn, groupname)
        if self.group_exists(cn, groupname) and gtype != 'bound':
            raise ValueError(f'cannot bind `{groupname}`: already a {gtype}')

        cn.execute(
            f'insert into "{self.namespace}"."group_binding" (groupname, seriesname, binding) '
            'values (%(gname)s, %(sname)s, %(binding)s) '
            'on conflict (groupname) do update '
            'set seriesname = %(sname)s, '
            '    binding = %(binding)s',
            gname=groupname,
            sname=formulaname,
            binding=binding.to_json(orient='records')
        )

    @tx
    def bindings_for(self, cn, groupname):
        res = cn.execute(
            'select seriesname, binding '
            f'from "{self.namespace}".group_binding '
            'where groupname = %(gname)s',
            gname=groupname
        )
        sname_binding = res.fetchone()
        if sname_binding is None:
            return
        binding = pd.DataFrame(sname_binding[1])
        return sname_binding[0], binding

    @tx
    def get_bound_group(self, cn, name, binding,
                        from_value_date=None,
                        to_value_date=None,
                        revision_date=None):
        m = binding['series'] == name
        if sum(m) == 0:
            # unbound series
            return None, None

        assert sum(m) == 1
        groupname = binding.loc[m, 'group'].iloc[0]
        family = binding.loc[m, 'family'].iloc[0]
        return (
            self.group_get(
                cn,
                groupname,
                from_value_date=None,
                to_value_date=None,
                revision_date=None
            ),
            family
        )

    @tx
    def _hijacked_formula(self, cn, name, binding,
                          from_value_date=None,
                          to_value_date=None,
                          revision_date=None):
        # find all the series in the formula that are referenced in
        # the binding since the series can be anywhere in the
        # dependencies - we use exanded_formula using (stopnames) to
        # limit the expansion - this semi-expanded formula will be
        # used later in the interpretor
        groupmap = defaultdict(dict)
        formula = self.expanded_formula(
            cn, name,
            stopnames = binding['series'].values
        )
        tree = parse(formula)
        series = self.find_series(cn, tree)

        for sname in series:
            df, family = self.get_bound_group(
                cn,
                sname,
                binding,
                from_value_date,
                to_value_date,
                revision_date
            )
            if family is not None:
                assert df is not None
                groupmap[family][sname] = df

        assert groupmap

        bi = interpreter.BridgeInterpreter(
            cn, self, {
                'from_value_date': from_value_date,
                'to_value_date': to_value_date,
                'revision_date': revision_date
            },
            groups=groupmap,
            binding=binding,
        )

        # build scenarios combinations
        possible_values = []
        families = []
        for ens_name, sub in groupmap.items():
            # we may have several groups there
            # but they all have the same column names
            # and this is what we want
            df = sub[list(sub.keys())[0]]
            possible_values.append(df.columns.to_list())
            families.append(ens_name)

        # combination is a list of dict tha contain a unqiue scenario...
        # [{ens0 = 'scenario0', ens1 = 'scenario4'}, ... ]
        combinations = []
        for comb in itertools.product(*possible_values):
            combination = {}
            for idx, values in enumerate(comb):
                combination.update({families[idx]: values})
            combinations.append(combination)

        columns = []
        for combination in combinations:
            columns.append(bi.g_evaluate(formula, combination))

        return pd.concat(columns, axis=1)
