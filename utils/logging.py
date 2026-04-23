def color(text, c):
    if c == "red":
        return f'<span style="color:#cc0000;"><b>{text}</b></span>'
    if c == "yellow":
        return f'<span style="color:#c9a100;"><b>{text}</b></span>'
    if c == "green":
        return f'<span style="color:#0a8900;"><b>{text}</b></span>'
    return text

class Logger:
    def __init__(self, sink=None):
        self._sink = sink or (lambda m, c=None: None)

    def log(self, msg, colour=None):
        try:
            if colour:
                self._sink(color(msg, colour), None)
            else:
                self._sink(msg, None)
        except TypeError:
            self._sink(msg, colour)
