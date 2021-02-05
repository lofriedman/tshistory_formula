import json
import click

import pandas as pd
from sqlalchemy import create_engine
from psyl.lisp import parse, serialize, Symbol, Keyword
from tshistory.util import find_dburi

from tshistory_formula.schema import formula_schema
from tshistory_formula.tsio import timeseries
from tshistory_formula.helper import (
    typecheck
)
from tshistory_formula.interpreter import Interpreter


@click.command(name='update-formula-metadata')
@click.argument('dburi')
@click.option('--reset', is_flag=True, default=False)
@click.option('--seriesname')
@click.option('--namespace', default='tsh')
def update_metadata(dburi, reset=False, seriesname=None, namespace='tsh'):
    engine = create_engine(find_dburi(dburi))
    tsh = timeseries(namespace)

    if seriesname:
        series = [seriesname]
    else:
        series = [
            name for name, kind in tsh.list_series(engine).items()
            if kind == 'formula'
        ]

    if reset:
        for name in series:
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
        for name in series:
            tree = parse(tsh.formula(engine, name))
            try:
                tz = tsh.check_tz_compatibility(engine, tree)
                print(name, tz)
                meta = tsh.default_meta(tz)
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
    print('FAIL', len(errors))
    from pprint import pprint
    pprint(dict(errors))


@click.command(name='migrate-0.6-to-0.7')
@click.argument('dburi')
@click.option('--doit', default=False, is_flag=True)
@click.option('--namespace', default='tsh')
def migrate(dburi, doit=False, namespace='tsh'):
    """ fix bad metadata on formula which happened
    between 0.6 and 0.7
    """
    engine = create_engine(find_dburi(dburi))
    tsh = timeseries(namespace)

    for name, kind in tsh.list_series(engine).items():
        if kind != 'formula':
            continue

        meta = tsh.metadata(engine, name)
        if 'supervision_status' in meta:
            print(name, meta['supervision_status'])
            if doit:
                meta.pop('supervision_status', None)
                tsh.update_metadata(engine, name, meta)


@click.command(name='ingest-formulas')
@click.argument('dburi')
@click.argument('formula-file', type=click.Path(exists=True))
@click.option('--strict', is_flag=True, default=False)
@click.option('--namespace', default='tsh')
def ingest_formulas(dburi, formula_file, strict=False, namespace='tsh'):
    """ingest a csv file of formulas

    Must be a two-columns file with a header "name,text"
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
                row.text,
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


@click.command(name='formula-init-db')
@click.argument('db-uri')
@click.option('--namespace', default='tsh')
def init_db(db_uri, namespace):
    "initialize the formula part of a timeseries history schema"
    engine = create_engine(find_dburi(db_uri))
    formula_schema(namespace).create(engine)


@click.command(name='shell')
@click.argument('db-uri')
@click.option('--namespace', default='tsh')
def shell(db_uri, namespace='tsh'):
    from tshistory.api import timeseries as tsapi
    tsa = tsapi(find_dburi(db_uri), namespace, timeseries)
    import pdb; pdb.set_trace()
