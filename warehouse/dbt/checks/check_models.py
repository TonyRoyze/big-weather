"""Offline semantic smoke tests. Transpilation is not Snowflake execution validation."""
import datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb
import jinja2
import sqlglot
import yaml

ROOT = Path(__file__).resolve().parents[1]
connection = duckdb.connect()
variables = {'coverage_start': '2024-02-28', 'coverage_end': '2024-03-01'}
environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
environment.globals.update(
    ref=lambda name: name,
    source=lambda _, name: 'RAW.' + name,
    config=lambda **_: '', var=lambda name, default=None: variables.get(name, default),
    modules=SimpleNamespace(datetime=datetime),
    exceptions=SimpleNamespace(raise_compiler_error=lambda message: (_ for _ in ()).throw(ValueError(message))),
)


def execute(sql):
    for statement in sqlglot.transpile(sql, read='snowflake', write='duckdb'):
        connection.execute(statement)


execute((ROOT / 'setup/raw_tables.sql').read_text())
connection.execute("insert into RAW.LOCATIONS values ('a','Coast','LK','Asia',7,80,10), ('b','Hill','LK','Asia',7.5,80.5,1200)")
connection.execute(f"create table weather_metrics as select * from read_csv_auto('{ROOT / 'seeds/weather_metrics.csv'}')")
connection.execute("create table int_dates as select cast(d as date) observation_date from generate_series(date '2024-02-28',date '2024-03-01',interval 1 day) t(d)")


def load_day(location, day, hours, temperature, file, loaded):
    for hour in range(hours):
        connection.execute('''insert into RAW.WEATHER_HOURLY
          (location_id,observed_at,temperature_2m,precipitation,loaded_at,source_file,source_row_number,source_checksum)
          values (?,?,?,?,?,?,?,?)''', [location, f'{day} {hour:02d}:00:00', temperature, 2,
                                       loaded, file, hour, file + '-checksum'])


order = ['stg_locations', 'stg_weather_hourly', 'int_weather_values', 'int_daily_observations',
         'dim_locations', 'fct_daily_weather', 'coverage_daily', 'coverage_locations',
         'weather_rolling_30d', 'weather_yearly', 'weather_seasonal', 'elevation_temperature']
paths = {p.stem:p for p in (ROOT/'models').rglob('*.sql')}
# Parse every SQL model in the Snowflake dialect, including the native calendar generator.
for path in paths.values():
    sqlglot.parse(environment.from_string(path.read_text()).render(), read='snowflake')


def build():
    for name in order:
        sql = environment.from_string(paths[name].read_text()).render()
        execute('create or replace table ' + name + ' as ' + sql)


load_day('a','2024-02-29',24,20,'first','2024-03-02')
load_day('b','2024-02-29',23,10,'partial','2024-03-02')
build()
assert connection.execute("select daily_value from fct_daily_weather where location_id='a' and observation_date='2024-02-29' and metric='precipitation'").fetchone() == (48.0,)
assert connection.execute("select daily_value from fct_daily_weather where location_id='b' and observation_date='2024-02-29' and metric='temperature_2m'").fetchone() == (None,)
assert connection.execute("select coverage_status, missing_hours from coverage_daily where location_id='a' and observation_date='2024-02-28' and metric='temperature_2m'").fetchone() == ('missing',24)
assert connection.execute('select count(*) from fct_daily_weather').fetchone() == (72,)
assert connection.execute('select distinct calendar_days, is_complete_year from weather_yearly').fetchone() == (366,False)
assert connection.execute("select distinct calendar_days from weather_seasonal where season='DJF'").fetchone() == (91,)
assert connection.execute('select count(*) from weather_rolling_30d where complete_30d_mean is not null').fetchone() == (0,)
# A late historical day and a later correction must both propagate on the next build.
load_day('a','2024-02-28',24,18,'backfill','2024-03-03')
load_day('a','2024-02-29',24,22,'correction','2024-03-04')
build()
assert connection.execute("select daily_value from fct_daily_weather where location_id='a' and observation_date='2024-02-28' and metric='temperature_2m'").fetchone() == (18.0,)
assert connection.execute("select daily_value from fct_daily_weather where location_id='a' and observation_date='2024-02-29' and metric='temperature_2m'").fetchone() == (22.0,)
assert connection.execute("select complete_days, available_day_mean from weather_rolling_30d where location_id='a' and observation_date='2024-03-01' and metric='temperature_2m'").fetchone() == (2,20.0)
for path in (ROOT/'tests').glob('*.sql'):
    if path.stem == 'full_release_coverage':
        continue
    sql = environment.from_string(path.read_text()).render()
    translated = sqlglot.transpile(sql, read='snowflake', write='duckdb')[0]
    assert connection.execute(translated).fetchall() == [], path.name
# All declared model grain assertions are checked too.
for model in yaml.safe_load((ROOT/'models/schema.yml').read_text())['models']:
    columns=model['data_tests'][0]['unique_grain']['arguments']['columns']
    keys=','.join(columns)
    assert not connection.execute(f"select {keys} from {model['name']} group by {keys} having count(*)>1").fetchall()
print('PASS: model SQL parsing, daily completeness, leap periods, coverage grid, backfill/corrections, rolling refresh, data tests and unique grains.')
