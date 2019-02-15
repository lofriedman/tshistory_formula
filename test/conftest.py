from pathlib import Path
import pytest

from sqlalchemy import create_engine, MetaData

from pytest_sa_pg import db
from click.testing import CliRunner

from tshistory import command
from tshistory_alias.schema import init, reset
from tshistory_formula.schema import init as ainit, reset as areset
from tshistory_formula.tsio import TimeSerie


DATADIR = Path(__file__).parent / 'data'


@pytest.fixture(scope='session')
def engine(request):
    port = 5433
    db.setup_local_pg_cluster(request, DATADIR, port)
    uri = 'postgresql://localhost:{}/postgres'.format(port)
    e = create_engine(uri)
    meta = MetaData()
    areset(e)
    reset(e)
    ainit(e, meta)
    init(e, meta)
    yield e


@pytest.fixture(scope='session')
def tsh(request, engine):
    tsh = TimeSerie()
    tsh._testing = True
    return tsh



@pytest.fixture
def cli():
    def runner(*args, **kw):
        args = [str(a) for a in args]
        for k, v in kw.items():
            args.append('--{}'.format(k))
            args.append(str(v))
        return CliRunner().invoke(command.tsh, args)
    return runner
