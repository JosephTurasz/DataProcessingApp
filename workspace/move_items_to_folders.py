import os
import shutil


class MoveItemsToFolders:
    def __init__(self, mw):
        self.mw = mw

    def run(self, checked: bool = False):
        paths = self.mw.ask_open_files(
            title="Select files to move",
            filter="Supported Files (*.csv *.xlsx *.xls *.txt *.f);;All Files (*)",
        )
        if not paths:
            return

        moved, skipped = [], []
        for path in paths:
            stem = os.path.splitext(os.path.basename(path))[0]
            dest_dir = os.path.join(os.path.dirname(path), stem)
            dest_file = os.path.join(dest_dir, os.path.basename(path))
            try:
                os.makedirs(dest_dir, exist_ok=True)
                shutil.move(path, dest_file)
                moved.append(os.path.basename(path))
            except Exception as e:
                skipped.append(f"{os.path.basename(path)} ({e})")

        if moved:
            self.mw.s.logger.log(f"Moved {len(moved)} file(s) into named folders.", "green")
        if skipped:
            for msg in skipped:
                self.mw.s.logger.log(f"[SKIP] {msg}", "yellow")
