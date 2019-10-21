import json
import click
import pandas as pd
from dateutil.relativedelta import relativedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlhelp import sqlfile
from psyl.lisp import parse, serialize, Symbol, Keyword
from tshistory.util import find_dburi

from tshistory_formula.tsio import timeseries
from tshistory_formula.helper import typecheck
from tshistory_formula.interpreter import Interpreter


@click.command(name='update-formula-metadata')
@click.argument('dburi')
@click.option('--reset', is_flag=True, default=False)
@click.option('--namespace', default='tsh')
def update_metadata(dburi, reset=False, namespace='tsh'):
    engine = create_engine(find_dburi(dburi))
    tsh = timeseries(namespace)

    if reset:
        for name, kind in tsh.list_series(engine).items():
            if kind != 'formula':
                continue
            # reset
            meta = tsh.metadata(engine, name)
            if meta:
                meta = {
                    k: v for k, v in meta.items()
                    if k not in tsh.metakeys
                }
            else:
                meta = {}
            sql = (f'update "{namespace}".formula '
                   'set metadata = %(metadata)s '
                   'where name = %(name)s')
            print('reset', name, 'to', meta)
            with engine.begin() as cn:
                cn.execute(
                    sql,
                    metadata=json.dumps(meta),
                    name=name
                )

    todo = []
    errors = []

    def justdoit():
        for name, kind in tsh.list_series(engine).items():
            if kind != 'formula':
                continue
            print(name)

            tree = parse(tsh.formula(engine, name))
            smap = tsh.find_series(engine, tree)
            try:
                meta = tsh.filter_metadata(smap)
            except ValueError as err:
                errors.append((name, err))
                continue
            if not meta or 'index_dtype' not in meta:
                todo.append(name)
                print(' -> todo')
                continue
            tsh.update_metadata(engine, name, meta)

    justdoit()

    print('TODO', todo)
    print('FAIL', errors)



@click.command(name='ingest-formulas')
@click.argument('dburi')
@click.argument('formula-file', type=click.Path(exists=True))
@click.option('--strict', is_flag=True, default=False)
@click.option('--namespace', default='tsh')
def ingest_formulas(dburi, formula_file, strict=False, namespace='tsh'):
    """ingest a csv file of formulas

    Must be a two-columns file with a header "name,formula"
    """
    engine = create_engine(find_dburi(dburi))
    df = pd.read_csv(formula_file)
    tsh = timeseries(namespace)
    with engine.begin() as cn:
        for row in df.itertuples():
            print('ingesting', row.name)
            tsh.register_formula(
                cn,
                row.name,
                row.formula,
                strict
            )


@click.command(name='typecheck-formula')
@click.argument('db-uri')
@click.option('--pdbshell', is_flag=True, default=False)
@click.option('--namespace', default='tsh')
def typecheck_formula(db_uri, pdbshell=False, namespace='tsh'):
    engine = create_engine(find_dburi(db_uri))
    tsh = timeseries(namespace)

    i = Interpreter(engine, tsh, {})
    for name, kind in tsh.list_series(engine).items():
        if kind != 'formula':
            continue

        formula = tsh.formula(engine, name)
        parsed = parse(formula)
        print(name, f'`{parsed[0]}`')
        typecheck(parsed, env=i.env)


@click.command(name='test-formula')
@click.argument('db-uri')
@click.argument('formula')
@click.option('--pdbshell', is_flag=True, default=False)
@click.option('--namespace', default='tsh')
def test_formula(db_uri, formula, pdbshell=False, namespace='tsh'):
    engine = create_engine(find_dburi(db_uri))
    tsh = timeseries(namespace)

    ts = tsh.eval_formula(engine, formula)
    print(ts)
    if pdbshell:
        import ipdb; ipdb.set_trace()


def rewrite(tree, clipinfo):
    # top-level/base case, we consider only "series"
    rewritten = []
    op = tree[0]
    if op == 'clip':
        return tree  # already rewritten
    if op == 'series':
        sid = tree[1]
        if sid in clipinfo:
            rewritten = [Symbol('clip'), tree]
            min, max = clipinfo[sid]
            if not pd.isnull(min):
                rewritten += [Keyword('min'), min]
            if not pd.isnull(max):
                rewritten += [Keyword('max'), max]
            return rewritten

    for node in tree:
        if isinstance(node, list):
            rewritten.append(
                rewrite(node, clipinfo)
            )
        else:
            rewritten.append(node)
    return rewritten


@click.command(name='drop-alias-tables')
@click.argument('db-uri')
@click.option('--drop', is_flag=True, default=False)
@click.option('--namespace', default='tsh')
def drop_alias_tables(db_uri, drop=False, namespace='tsh'):
    engine = create_engine(find_dburi(db_uri))

    # convert outliers to clip operator

    elts = {
        k: (min, max)
        for k, min, max in engine.execute(
                'select serie, min, max from tsh.outliers'
        ).fetchall()
    }
    tsh = timeseries(namespace)
    rewriteme = []
    for name, kind in tsh.list_series(engine).items():
        if kind != 'formula':
            continue
        tree = parse(tsh.formula(engine, name))
        smap = tsh.find_series(engine, tree)
        for sname in smap:
            if sname in elts:
                rewriteme.append((name, tree))
                break

    for name, tree in rewriteme:
        tree2 = rewrite(tree, elts)
        print(name)
        print(serialize(tree))
        print('->')
        print(serialize(tree2))
        print()
        tsh.register_formula(
            engine,
            name,
            serialize(tree2),
            update=True
        )

    if not drop:
        print('DID NOT DROP the tables')
        print('pass --drop to really drop them')
        return

    with engine.begin() as cn:
        cn.execute(
            f'drop table if exists "{namespace}".arithmetic'
        )
        cn.execute(
            f'drop table if exists "{namespace}".priority'
        )
        cn.execute(
            f'drop table if exists "{namespace}".outliers'
        )


@click.command(name='shell')
@click.argument('db-uri')
@click.option('--namespace', default='tsh')
def shell(db_uri, namespace='tsh'):
    e = create_engine(find_dburi(db_uri))

    tsh = timeseries(namespace)
    import pdb; pdb.set_trace()
