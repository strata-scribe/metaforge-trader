import asyncio
import logging
import os
import sqlite3
import gzip
import shutil
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, db_path: str, backup_dir: str, retention_days: int = 7):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.retention_days = retention_days
        self.task = None

        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self):
        """Creates a compressed backup of the SQLite database."""
        if not os.path.exists(self.db_path):
            logger.error(f"Database file {self.db_path} does not exist.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db.gz"
        backup_filepath = os.path.join(self.backup_dir, backup_filename)

        # We first backup to a temporary uncompressed file to ensure a clean read
        temp_db_path = os.path.join(self.backup_dir, f"temp_{timestamp}.db")

        try:
            # Use SQLite backup API for a safe copy
            source = sqlite3.connect(self.db_path)
            dest = sqlite3.connect(temp_db_path)
            with source:
                source.backup(dest)
            dest.close()
            source.close()

            # Compress the temporary file
            with open(temp_db_path, 'rb') as f_in:
                with gzip.open(backup_filepath, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            logger.info(f"Backup created successfully: {backup_filepath}")
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            if os.path.exists(backup_filepath):
                os.remove(backup_filepath)
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def rotate_backups(self):
        """Removes backups older than the retention period."""
        if not os.path.exists(self.backup_dir):
            return

        now = datetime.now()
        for filename in os.listdir(self.backup_dir):
            if not filename.startswith("backup_") or not filename.endswith(".db.gz"):
                continue

            filepath = os.path.join(self.backup_dir, filename)

            # Extract timestamp from filename
            try:
                # filename format: backup_YYYYMMDD_HHMMSS.db.gz
                date_str = filename[len("backup_"):-len(".db.gz")]
                backup_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            except ValueError:
                logger.warning(f"Could not parse date from backup filename: {filename}")
                continue

            if now - backup_date > timedelta(days=self.retention_days):
                try:
                    os.remove(filepath)
                    logger.info(f"Deleted old backup: {filepath}")
                except OSError as e:
                    logger.error(f"Error deleting old backup {filepath}: {e}")

    async def backup_routine(self):
        """Runs the scheduled daily backup and rotation."""
        try:
            while True:
                self.create_backup()
                self.rotate_backups()
                # Wait for 24 hours (86400 seconds)
                await asyncio.sleep(86400)
        except asyncio.CancelledError:
            logger.info("Backup routine cancelled.")

    def start(self):
        """Starts the backup background task."""
        if not self.task:
            self.task = asyncio.create_task(self.backup_routine())

    async def stop(self):
        """Stops the backup background task."""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
