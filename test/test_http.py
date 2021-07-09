from datetime import datetime as dt
import json

import pandas as pd
import webtest

from tshistory import util
from tshistory.testutil import (
    assert_df,
    gengroup,
    genserie,
    utcdt
)


def test_series_formula(client, engine):
    series = genserie(utcdt(2020, 1, 1), 'D', 3)
    res = client.patch('/series/state', params={
        'name': 'test-formula',
        'series': util.tojson(series),
        'author': 'Babar',
        'insertion_date': utcdt(2020, 1, 1, 10),
        'tzaware': util.tzaware_serie(series)
    })

    assert res.status_code == 201

    res = client.patch('/series/formula', params={
        'name': 'new-formula',
        'text': '(+ 3'
    })
    assert res.status_code == 400
    assert res.json['message'] == '`new-formula` has a syntax error in it'

    res = client.patch('/series/formula', params={
        'name': 'new-formula',
        'text': '(+ 3 (series "lol"))'
    })
    assert res.status_code == 409
    assert res.json['message'] == 'Formula `new-formula` refers to unknown series `lol`'

    res = client.patch('/series/formula', params={
        'name': 'new-formula',
        'text': '(+ 3 (series "lol"))',
        'reject_unknown': False
    })
    assert res.status_code == 201

    # update ?
    res = client.patch('/series/formula', params={
        'name': 'new-formula',
        'text': '(+ 3 (series "test-formula"))'
    })
    assert res.status_code == 409
    assert res.json['message'] == '`new-formula` already exists'

    # update !
    res = client.patch('/series/formula', params={
        'name': 'new-formula',
        'text': '(+ 3 (series "test-formula"))',
        'force_update': True
    })
    assert res.status_code == 200

    res = client.get('/series/state?name=new-formula')
    series = util.fromjson(res.body, 'test', True)
    assert_df("""
2020-01-01 00:00:00+00:00    3.0
2020-01-02 00:00:00+00:00    4.0
2020-01-03 00:00:00+00:00    5.0
""", series)

    res = client.get('/series/formula?name=new-formula')
    assert res.json == '(+ 3 (series "test-formula"))'

    # expansion

    res = client.patch('/series/formula', params={
        'name': '2-levels-formula',
        'text': '(+ 5 (series "new-formula"))'
    })
    res = client.get('/series/formula?name=2-levels-formula&expanded=1')
    assert res.json == '(+ 5 (+ 3 (series "test-formula")))'

    res = client.get('/series/insertion_dates', params={
        'name': 'new-formula'
    })
    idates = [
        pd.Timestamp(t, tz='UTC')
        for t in res.json['insertion_dates']
    ]
    assert idates == [
        pd.Timestamp('2020-01-01 10:00:00', tz='UTC')
    ]

    res = client.get('/series/formula_components?name=new-formula')
    assert res.json == {'new-formula': ['test-formula']}


def test_group_formula(client, engine):
    df = gengroup(
        n_scenarios=3,
        from_date=dt(2021, 1, 1),
        length=5,
        freq='D',
        seed=2.
    )
    df.columns = ['a', 'b', 'c']

    bgroup = util.pack_group(df)
    res = client.patch('/group/state', {
        'name': 'test_group',
        'author': 'Babar',
        'format': 'tshpack',
        'replace': json.dumps(True),
        'bgroup': webtest.Upload('bgroup', bgroup)
    })
    assert res.status_code == 201

    res = client.put('/group/formula', {
        'name': 'group_formula',
        'author': 'Babar',
        'text': '(group-add (group "test_group") (group "test_group"))'
    })

    assert res.status_code == 201

    res = client.get('/group/formula', {
        'name': 'group_formula'
    })
    assert res.json == '(group-add (group "test_group") (group "test_group"))'

    res = client.get('/group/state', {'name': 'group_formula'})
    df2 = util.unpack_group(res.body)

    assert df2.equals(df * 2)


def test_bound_formula(client, engine):
    ts = genserie(pd.Timestamp('2021-1-1'), 'H', 3)
    res = client.patch('/series/state', {
        'name': 'a-series',
        'series': util.tojson(ts),
        'author': 'Babar',
        'insertion_date': utcdt(2021, 1, 1, 10),
        'tzaware': util.tzaware_serie(ts)
    })
    res = client.patch('/series/state', {
        'name': 'another-series',
        'series': util.tojson(ts),
        'author': 'Babar',
        'insertion_date': utcdt(2021, 1, 1, 10),
        'tzaware': util.tzaware_serie(ts)
    })

    assert res.status_code == 201

    # prepare a formula
    res = client.patch('/series/formula', {
        'name': 'hijack-me',
        'text': '(add (series "a-series") (series "another-series"))'
    })
    assert res.status_code == 201

    # prepare a group
    df = gengroup(
        n_scenarios=3,
        from_date=dt(2021, 1, 1),
        length=5,
        freq='D',
        seed=2.
    )
    df.columns = ['a', 'b', 'c']

    bgroup = util.pack_group(df)
    res = client.patch('/group/state', {
        'name': 'a-group',
        'author': 'Babar',
        'format': 'tshpack',
        'replace': json.dumps(True),
        'bgroup': webtest.Upload('bgroup', bgroup)
    })
    assert res.status_code == 201

    bindings = pd.DataFrame(
        [
            ['a-series', 'a-group', 'topic'],
        ],
        columns=('series', 'group', 'family')
    )

    res = client.put('/group/boundformula', {
        'name': 'bfgroup',
        'formulaname': 'hijack-me',
        'bindings': bindings.to_json(orient='records')
    })
    assert res.status_code == 200

    res = client.get('/group/boundformula', {'name': 'bfgroup'})
    assert res.json == [
        'hijack-me', [{
            'group': 'a-group',
            'family': 'topic',
            'series': 'a-series'
        }]
    ]

    res = client.get('/group/state', {
        'name': 'bfgroup'
    })
    df2 = util.unpack_group(res.body)

    assert_df("""
              a    b    c
2021-01-01  2.0  3.0  4.0
""", df2)
