import asyncio
import gzip
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backup import BackupManager


@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        backup_dir = os.path.join(temp_dir, "backups")

        # Create a dummy database
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test (name) VALUES ('hello')")
        conn.commit()
        conn.close()

        yield db_path, backup_dir


def test_create_backup(temp_env):
    db_path, backup_dir = temp_env
    manager = BackupManager(db_path, backup_dir, retention_days=7)
    manager.create_backup()

    assert os.path.exists(backup_dir)
    files = os.listdir(backup_dir)
    assert len(files) == 1

    backup_file = files[0]
    assert backup_file.startswith("backup_")
    assert backup_file.endswith(".db.gz")

    # Verify the compressed backup is valid
    backup_filepath = os.path.join(backup_dir, backup_file)
    with gzip.open(backup_filepath, 'rb') as f:
        content = f.read()
        assert b"SQLite format 3" in content


def test_rotate_backups(temp_env):
    db_path, backup_dir = temp_env
    manager = BackupManager(db_path, backup_dir, retention_days=7)
    os.makedirs(backup_dir, exist_ok=True)

    now = datetime.now()

    # Create an old backup file (8 days old)
    old_date = now - timedelta(days=8)
    old_filename = f"backup_{old_date.strftime('%Y%m%d_%H%M%S')}.db.gz"
    old_filepath = os.path.join(backup_dir, old_filename)
    with open(old_filepath, "w") as f:
        f.write("old")

    # Create a recent backup file (2 days old)
    recent_date = now - timedelta(days=2)
    recent_filename = f"backup_{recent_date.strftime('%Y%m%d_%H%M%S')}.db.gz"
    recent_filepath = os.path.join(backup_dir, recent_filename)
    with open(recent_filepath, "w") as f:
        f.write("recent")

    # Also add a file with invalid format, should be ignored
    invalid_filepath = os.path.join(backup_dir, "backup_invalid.db.gz")
    with open(invalid_filepath, "w") as f:
        f.write("invalid")

    manager.rotate_backups()

    files = os.listdir(backup_dir)
    assert len(files) == 2
    assert recent_filename in files
    assert "backup_invalid.db.gz" in files
    assert old_filename not in files


@pytest.mark.asyncio
async def test_backup_routine_calls(temp_env):
    db_path, backup_dir = temp_env
    manager = BackupManager(db_path, backup_dir, retention_days=7)

    # We will patch asyncio.sleep to raise a CancelledError after calling create_backup and rotate_backups
    # This prevents the infinite loop while testing the routine
    call_count = 0

    async def mock_sleep(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise asyncio.CancelledError()

    with patch.object(manager, 'create_backup') as mock_create, \
         patch.object(manager, 'rotate_backups') as mock_rotate, \
         patch('asyncio.sleep', new=mock_sleep):

        # This will exit immediately due to the CancelledError
        await manager.backup_routine()

        mock_create.assert_called_once()
        mock_rotate.assert_called_once()
        assert call_count == 1
