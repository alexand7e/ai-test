from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import asyncio

from prisma import Prisma


@dataclass(frozen=True)
class Migration:
    id: str
    sql_path: Path


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "prisma" / "migrations"


def _collect_migrations() -> list[Migration]:
    base = _migrations_dir()
    if not base.exists():
        return []

    migrations: list[Migration] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        sql_path = entry / "migration.sql"
        if not sql_path.exists():
            continue
        migrations.append(Migration(id=entry.name, sql_path=sql_path))
    migrations.sort(key=lambda m: m.id)
    return migrations


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_sql_comments(sql: str) -> str:
    out_lines: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _split_sql_statements(sql: str) -> list[str]:
    sql = _strip_sql_comments(sql)
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        ch = sql[i]

        if ch == "'" and not in_double:
            if in_single:
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    buf.append("''")
                    i += 2
                    continue
                in_single = False
            else:
                in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            i += 1
            continue

        if ch == ";" and not in_single and not in_double:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _is_ignorable_migration_error(stmt: str, exc: Exception) -> bool:
    s = stmt.strip().lower()
    msg = str(exc).lower()
    if "already exists" not in msg and "duplicate" not in msg:
        return False
    if s.startswith("create type "):
        return True
    if "add constraint" in s:
        return True
    return False


async def apply_migrations(db: Prisma) -> dict:
    migrations = _collect_migrations()
    if not migrations:
        return {"applied": 0, "skipped": 0}

    await db.execute_raw(
        'CREATE TABLE IF NOT EXISTS "AppMigration" ('
        '"id" TEXT PRIMARY KEY, '
        '"checksum" TEXT NOT NULL, '
        '"appliedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()'
        ")"
    )

    applied = 0
    skipped = 0
    lock_key = 803201
    while True:
        locked_rows = await db.query_raw("SELECT pg_try_advisory_lock($1) AS locked", lock_key)
        if locked_rows and locked_rows[0].get("locked"):
            break
        await asyncio.sleep(0.2)
    try:
        for m in migrations:
            sql_text = m.sql_path.read_text(encoding="utf-8")
            checksum = _sha256(sql_text)

            existing = await db.query_raw('SELECT "id", "checksum" FROM "AppMigration" WHERE "id" = $1', m.id)
            if existing:
                skipped += 1
                continue

            for stmt in _split_sql_statements(sql_text):
                try:
                    await db.execute_raw(stmt)
                except Exception as exc:
                    if _is_ignorable_migration_error(stmt, exc):
                        continue
                    raise

            await db.execute_raw(
                'INSERT INTO "AppMigration" ("id", "checksum") VALUES ($1, $2)',
                m.id,
                checksum,
            )
            applied += 1
    finally:
        await db.query_raw("SELECT pg_advisory_unlock($1) AS unlocked", lock_key)

    return {"applied": applied, "skipped": skipped}
