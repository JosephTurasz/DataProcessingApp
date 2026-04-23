import os, sys, csv, faulthandler, traceback, signal

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QIcon
from gui.window import MainWindow

def _qt_message_handler(mode, context, message):
    if "shared QObject was deleted directly" in message:
        print("\n=== QT WARNING ===")
        print(message)
        try:
            print(f"Qt context: {context.file}:{context.line} in {context.function}")
        except Exception:
            pass
        print("Python stack (at emission):")
        traceback.print_stack(limit=25)
        print("=== /QT WARNING ===\n")

qInstallMessageHandler(_qt_message_handler)

def _install_crash_logging():
    log_path = os.path.join(os.path.dirname(sys.argv[0]), "crash.log")
    try:
        f = open(log_path, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=f, all_threads=True)
        faulthandler.register(signal.SIGABRT, file=f, all_threads=True) if hasattr(sys, "getwindowsversion") else None
    except Exception:
        pass

    def excepthook(exc_type, exc, tb):
        try:
            with open(log_path, "a", encoding="utf-8") as f2:
                f2.write("\n=== Unhandled exception ===\n")
                traceback.print_exception(exc_type, exc, tb, file=f2)
        finally:
            sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = excepthook

_install_crash_logging()

max_int = sys.maxsize
while True:
    try:
        csv.field_size_limit(max_int)
        break
    except OverflowError:
        max_int = int(max_int / 10)

def main():
    app = QApplication(sys.argv)
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    icon_path = os.path.join(base_path, "tdg_app_icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()