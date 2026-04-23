class GeneratePassword:
    def __init__(self, mw):
        self.mw = mw

    def run(self, checked: bool = False):
        password = self.mw.s.packager.generate_password()
        self.mw.s.logger.log(f"Generated random password: {password}", "green")
