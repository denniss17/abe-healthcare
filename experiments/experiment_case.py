from typing import Dict, Any


class ExperimentCase(object):
    def __init__(self, name: str, arguments: Dict[str, Any]) -> None:
        self.name = name
        self.arguments = arguments

    def __repr__(self):
        return "%s[name=%s, arguments=%s]" % (
            self.__class__.__name__,
            self.name,
            str(self.arguments)
        )
