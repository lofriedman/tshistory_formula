import pandas as pd

from tshistory import util
from tshistory.testutil import (
    assert_df,
    genserie,
    utcdt
)


def test_formula(client, engine):
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
