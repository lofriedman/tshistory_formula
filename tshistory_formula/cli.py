import json
import click
import pandas as pd
from dateutil.relativedelta import relativedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlhelp import sqlfile
from psyl.lisp import parse
from tshistory.util import find_dburi

from tshistory_formula.tsio import timeseries


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


@click.command(name='drop-alias-tables')
@click.argument('db-uri')
@click.option('--namespace', default='tsh')
def drop_alias_tables(db_uri, namespace='tsh'):
    engine = create_engine(find_dburi(db_uri))

    with engine.begin() as cn:
        cn.execute(
            f'drop table "{namespace}".arithmetic'
        )
        cn.execute(
            f'drop table "{namespace}".priority'
        )
        cn.execute(
            f'drop table "{namespace}".outliers'
        )


@click.command(name='shell')
@click.argument('db-uri')
@click.option('--namespace', default='tsh')
def shell(db_uri, namespace='tsh'):
    e = create_engine(find_dburi(db_uri))

    tsh = timeseries(namespace)
    import pdb; pdb.set_trace()
