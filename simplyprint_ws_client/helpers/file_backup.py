import datetime
import shutil
from pathlib import Path
from typing import Optional


class FileBackup:
    """ Small wrapper for count based file backups, used for configs """

    @staticmethod
    def backup_file(file: Path, max_count: int = 5, max_age: Optional[datetime.timedelta] = None):
        """Backup a file with a count based system

        Use the following format

        file.ext.bak.count

        """

        if not file.exists():
            return

        # Remove old backups by first sorting them by age and then removing the oldest ones
        # then adjust the count of the remaining ones
        backups = sorted(file.parent.glob(f"{file.name}.bak.*"), reverse=True)

        if max_age:
            for backup in backups:
                date_changed = datetime.datetime.fromtimestamp(backup.stat().st_mtime)

                if datetime.datetime.now() - date_changed > max_age:
                    backup.unlink()
                    backups.remove(backup)

        for j, backup in enumerate(backups):
            i = len(backups) - j - 1

            if i + 1 >= max_count:
                backup.unlink()
            else:
                backup.rename(file.parent / f"{file.name}.bak.{i + 1}")

        # Now create the new backup by copying the original file
        shutil.copy(file, file.parent / f"{file.name}.bak.0")
