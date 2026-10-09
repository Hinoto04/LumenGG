"""Read public source data without migrating or writing the source database."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from django.core.management.base import BaseCommand
from django.utils import timezone
from mobile_api.catalog import read_snapshot


class Command(BaseCommand):
    help = 'Export a bundled mobile seed from public catalog data (source DB is read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        rows, relations = read_snapshot()
        path = Path(options['output']).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.unlink(missing_ok=True)
        with closing(sqlite3.connect(temporary)) as db:
            db.executescript('''PRAGMA foreign_keys=ON;
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE entries(kind TEXT,id INTEGER,data TEXT NOT NULL,search TEXT NOT NULL,PRIMARY KEY(kind,id));
                CREATE TABLE relations(source_kind TEXT,source_id INTEGER,target_kind TEXT,target_id INTEGER,
                  FOREIGN KEY(source_kind,source_id) REFERENCES entries(kind,id), FOREIGN KEY(target_kind,target_id) REFERENCES entries(kind,id));
                CREATE INDEX entries_kind ON entries(kind);
                CREATE INDEX relation_target ON relations(target_kind,target_id);''')
            db.executemany('INSERT INTO metadata VALUES (?,?)', [('schema_version','1'),('release_version','seed-'+timezone.now().strftime('%Y%m%d'))])
            db.executemany('INSERT INTO entries VALUES (?,?,?,?)',[(k,i,json.dumps(d,ensure_ascii=False),s) for k,i,d,s in rows])
            db.executemany('INSERT INTO relations VALUES (?,?,?,?)',relations)
            if db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Invalid seed references.')
            db.commit()
        temporary.replace(path)
        self.stdout.write(f'Exported {len(rows)} public records to {path}')
