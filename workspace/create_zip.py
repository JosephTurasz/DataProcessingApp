from __future__ import annotations

import os
import shutil
import tempfile

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog

from workspace.base import BaseWorkflow
from gui.dialogs.zip_dialog import ZipDialog

class CreateZip(BaseWorkflow):
    def run(self, checked: bool = False):
        dlg = ZipDialog(self.mw)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        res = dlg.get_result()
        paths: list[str] = res.get("paths") or []
        if not paths:
            return
        
        first_path = paths[0]
        
        if os.path.isdir(first_path):
            self.mw.update_last_input_dir(os.path.dirname(first_path))
        else:
            self.mw.update_last_input_dir(first_path)

        mode = res.get("password_mode")

        if mode == "random":
            password = self.mw.s.packager.generate_password()
        elif mode == "enter":
            password = (res.get("password") or "").strip()
            if not password:
                self.warn("Missing password", "Please enter a password.")
                return
        else:
            password = ""

        first_path = paths[0].rstrip("\\/")

        parent_dir = os.path.dirname(first_path)

        folder_name = os.path.basename(parent_dir)
        
        default_zip_name = f"{folder_name}_SORTED_DATA.zip"

        zipfile = self.mw.ask_save_csv(
            "Save encrypted ZIP as",
            "ZIP Files (*.zip);;All Files (*)",
            defaultName=default_zip_name)
        if not zipfile:
            return

        pw_txt_path: str | None = None
        if password:
            zip_stem = os.path.splitext(os.path.basename(zipfile))[0]
            if zip_stem.endswith("_SORTED_DATA"):
                zip_stem = zip_stem[: -len("_SORTED_DATA")]
            pw_txt_path = os.path.join(os.path.dirname(zipfile), f"{zip_stem} password.txt")

        def job_zip():
            def norm(p: str) -> str:
                return p.rstrip("\\/")

            norm_paths = [norm(p) for p in paths]

            pw_warning = None

            try:
                # Attempt to find a common root so the zip stores nice relative paths
                common_root = os.path.commonpath(norm_paths)

                # If the common path is a file, use its directory
                if not os.path.isdir(common_root):
                    common_root = os.path.dirname(common_root)

                rel_items = [os.path.relpath(p, common_root) for p in norm_paths]

                self.mw.s.packager.create_zip(
                    common_root,
                    zipfile,
                    password,
                    paths=rel_items
                )

            except Exception:
                # Happens if files are on different drives or commonpath fails
                # Fall back to absolute paths
                self.mw.s.packager.create_zip(
                    "",
                    zipfile,
                    password,
                    paths=norm_paths
                )

            if password and pw_txt_path:
                try:
                    with open(pw_txt_path, "w", encoding="utf-8") as f:
                        f.write(password)
                except Exception as e:
                    pw_warning = f"Could not save password to {pw_txt_path}:\n{e}"

            return {"password": password, "pw_warning": pw_warning}
        
        def on_zipped(res_out: dict):
            if res_out.get("pw_warning"):
                self.warn("Warning", res_out["pw_warning"])

            if res_out.get("password"):
                QGuiApplication.clipboard().setText(res_out["password"])
                self.info(f"Zip file saved successfully. Password: {res_out['password']} (copied to clipboard)", "green")
            else:
                self.info("Zip file saved successfully.", "green")

        self.run_busy("Create ZIP","Creating ZIP…",job_zip,on_done=on_zipped,on_err=lambda e: self.fail("Create ZIP failed", e))