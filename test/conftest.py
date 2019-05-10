from pathlib import Path
import pytest

from sqlalchemy import create_engine

from pytest_sa_pg import db
from click.testing import CliRunner

from tshistory import cli as command
from tshistory.schema import (
    init_schemas,
    reset_schemas,
    tsschema
)
from tshistory_alias.schema import alias_schema
from tshistory_formula.schema import formula_schema
from tshistory_formula.tsio import timeseries


DATADIR = Path(__file__).parent / 'data'


@pytest.fixture(scope='session')
def engine(request):
    port = 5433
    db.setup_local_pg_cluster(request, DATADIR, port)
    uri = 'postgresql://localhost:{}/postgres'.format(port)
    e = create_engine(uri)
    tsschema()
    alias_schema()
    formula_schema()
    reset_schemas(e)
    init_schemas(e)
    return e


@pytest.fixture(scope='session')
def tsh(request, engine):
    return timeseries()


@pytest.fixture
def cli():
    def runner(*args, **kw):
        args = [str(a) for a in args]
        for k, v in kw.items():
            if isinstance(v, bool):
                if v:
                    args.append('--{}'.format(k))
            else:
                args.append('--{}'.format(k))
                args.append(str(v))
        return CliRunner().invoke(command.tsh, args)
    return runner


@pytest.fixture(scope='session')
def datadir():
    return DATADIR
