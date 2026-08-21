"""Isolated database settings for local and CI test runs.

SQLite is the zero-dependency default. Set ``LUMENGG_TEST_DATABASE=mariadb``
to verify behavior against the disposable service in ``compose.test.yml``.
"""

import os

from .settings import *  # noqa: F403


TEST_DATABASE = os.environ.get('LUMENGG_TEST_DATABASE', 'sqlite').lower()

if TEST_DATABASE == 'sqlite':
    sqlite_name = os.environ.get('LUMENGG_TEST_SQLITE_PATH', ':memory:')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_name,
            'TEST': {'NAME': ':memory:'},
        },
    }
elif TEST_DATABASE in {'mariadb', 'mysql'}:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('LUMENGG_TEST_DB_NAME', 'lumengg_test_source'),
            'USER': os.environ.get('LUMENGG_TEST_DB_USER', 'root'),
            'PASSWORD': os.environ.get('LUMENGG_TEST_DB_PASSWORD', 'lumengg-test-root'),
            'HOST': os.environ.get('LUMENGG_TEST_DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('LUMENGG_TEST_DB_PORT', '33078'),
            'OPTIONS': {'charset': 'utf8mb4'},
            'TEST': {
                'NAME': os.environ.get('LUMENGG_TEST_DB_TEST_NAME', 'test_lumengg_isolated'),
                'CHARSET': 'utf8mb4',
                'COLLATION': 'utf8mb4_unicode_ci',
            },
        },
    }
else:
    raise ValueError(
        'LUMENGG_TEST_DATABASE must be one of: sqlite, mariadb, mysql'
    )

CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}
USE_IN_MEMORY_CHANNEL_LAYER = True
CHANNEL_REDIS_URL = ''
BATTLELOG_REDIS_URL = ''

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
