import click
import pandas as pd
from dateutil.relativedelta import relativedelta
from pathlib import Path

from sqlalchemy import create_engine
from tshistory.util import find_dburi, sqlfile

from tshistory_formula.tsio import timeseries


# alias vs formula

@click.command(name='convert-aliases')
@click.argument('dburi')
@click.option('--namespace', default='tsh')
def convert_aliases(dburi, namespace='tsh'):
    engine = create_engine(find_dburi(dburi))

    SCHEMA = Path(__file__).parent / 'schema.sql'
    with engine.begin() as cn:
        cn.execute(sqlfile(SCHEMA, ns=namespace))

    tsh = timeseries(namespace)
    with engine.begin() as cn:
        tsh.convert_aliases(cn)


@click.command(name='compare-aliases')
@click.argument('dburi')
@click.option('--staircase', is_flag=True, default=False)
@click.option('--series')
@click.option('--namespace', default='tsh')
def compare_aliases(dburi, staircase=False, series=None, namespace='tsh'):
    from tshistory_alias.tsio import timeseries as TSA
    from time import time
    uri = find_dburi(dburi)
    engine = create_engine(uri)
    if series is None:
        series = [name for name, in engine.execute(
            f'select name from "{namespace}-formula".formula'
        ).fetchall()]
    else:
        series = [series]

    def run(idx, uri, series, fail=False):
        tsha = TSA()
        tshf = timeseries(namespace)
        engine = create_engine(uri)
        if staircase:
            delta = relativedelta(days=1)
            sca = tsha.get
            scf = tshf.get_delta
        else:
            delta = None
            sca = tsha.get
            scf = tshf.get
        for num, name in enumerate(series, 1):
            status = f'[{num}/{len(series)}]'
            try:
                with engine.begin() as cn:
                    t0 = time()
                    tsa = sca(cn, name, delta=delta)
                    t1 = time() - t0
                    if len(tsa) == 0:
                        continue
                    t2 = time()
                    tsf = scf(cn, name, delta=delta)
                    t3 = time() - t2
                assert (tsf == tsa).all()
            except AssertionError:
                print(f'{idx} {name}  discrepancy a/f {len(tsa)} {len(tsf)} {status}')
                if not fail:
                    continue
                raise
            except Exception as err:
                print(f'{idx} {name}  oops: {err} {status}')
                if not fail:
                    continue
                raise
            print(f'{idx} {name} -> f time/a time : {round(t3/t1, 3)} '
                  f'size : {len(tsa)} {status}')

    if len(series) == 1:
        run(0, uri, series, fail=True)
        return

    import random
    import os
    import signal
    processes = 8
    def chunks(l, n):
        for i in range(0, len(l), n):
            yield l[i:i + n]
    # try to distribute the payload randomly as in practice it is definitely
    # *not* evenly dsitributed along the lexical order ...
    random.shuffle(series)
    chunked = list(chunks(series, len(series) // processes))
    print('running with {} processes'.format(len(chunked)))

    pids = []
    for idx, chunk in enumerate(chunked):
        pid = os.fork()
        if not pid:
            # please the eyes
            chunk.sort()
            run(idx, uri, chunk)
            return
        pids.append(pid)

    try:
        for pid in pids:
            print('waiting for', pid)
            os.waitpid(pid, 0)
    except KeyboardInterrupt:
        for pid in pids:
            print('kill', pid)
            os.kill(pid, signal.SIGINT)


# /alias

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


@click.command(name='shell')
@click.argument('db-uri')
@click.option('--namespace', default='tsh')
def shell(db_uri, namespace='tsh'):
    e = create_engine(find_dburi(db_uri))

    tsh = timeseries(namespace)
    import pdb; pdb.set_trace()
