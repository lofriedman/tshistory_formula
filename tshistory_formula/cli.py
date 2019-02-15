import click
from sqlalchemy import create_engine
from tshistory.util import find_dburi

from tshistory_formula.tsio import TimeSerie


@click.command(name='convert-aliases')
@click.argument('dburi')
@click.option('--namespace', default='tsh')
def convert_aliases(dburi, namespace='tsh'):
    engine = create_engine(find_dburi(dburi))
    tsh = TimeSerie(namespace)
    with engine.begin() as cn:
        tsh.convert_aliases(cn)

