import os
import time

class LockHeldError(RuntimeError):
    pass


class LockNotHeldError(RuntimeError):
    pass


class Lockfile:
    def __init__(self, path : str):
        self._path = path
        self.lockfile = None

    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.unlock()
        return not exc_type

    def lock(self):
        if self.lockfile:
            return
        while not self.lockfile:
            try:
                self.lockfile = open(self._path, 'x')
            except FileExistsError:
                # The lock exists...let's figure out if it's stale
                try:
                    lockfile = open(self._path, 'r')
                except FileNotFoundError:
                    # The lock was just deleted
                    continue
                lockinfo = None
                for _ in range(3):
                    # There is a slight race condition if the lock has been opened
                    # but the file info hasn't been written yet--let's try a few
                    # times to get that info before giving up
                    lockinfo = lockfile.read()
                    if lockinfo:
                        break
                    time.sleep(0.01)
                lockfile.close()
                if lockinfo and lockinfo.startswith('/proc/'):
                    pathstat = os.stat(self._path)
                    try:
                        lockstat = os.stat(lockinfo.strip())
                        if (lockstat.st_ino, lockstat.st_dev) == (pathstat.st_ino, pathstat.st_dev):
                            # The lock is currently held
                            raise LockHeldError
                    except (FileNotFoundError, PermissionError):
                        pass
                # The lock is stale, clean it up
                self.lockfile = open(self._path, 'w')

        # Store the /proc info on this lock in the file for easy lookup
        self.lockfile.write(f'/proc/{os.getpid()}/fd/{self.lockfile.fileno()}')
        self.lockfile.flush()


    def unlock(self):
        if not self.lockfile:
            raise LockNotHeldError
        # The lock must be deleted before closing to avoid race conditoins
        os.unlink(self._path)
        self.lockfile.close()
        self.lockfile = None
