from typing import Any

from shared.model.global_parameters import GlobalParameters


class User(object):
    def __init__(self, gid: str, implementation: Any) -> None:
        """
        Create a new user
        :param gid: The global identifier of this user
        :param implementation:
        """
        self.gid = gid
        self.implementation = implementation
        self.secret_keys = implementation.setup_secret_keys(self.gid)
        self.owner_key_pair = None  # type: Any
        self._registration_data = None  # type: dict
        self._global_parameters = None  # type: GlobalParameters

    @property
    def registration_data(self):
        return self._registration_data

    @registration_data.setter
    def registration_data(self, registration_data):
        self._registration_data = registration_data

    def issue_secret_keys(self, secret_keys: dict):
        """
        Issue new secret keys to this user.
        :param secret_keys:
        :type secret_keys: dict

        >>> from shared.implementations.base_implementation import MockImplementation
        >>> dummyImplementation = MockImplementation()
        >>> user = User("bob", dummyImplementation)
        >>> user.secret_keys
        {}
        >>> user.issue_secret_keys({'a': {'foo': 'bar'}})
        >>> user.secret_keys == {'a': {'foo': 'bar'}}
        True
        >>> user.issue_secret_keys({'b': {'bla': 'bla'}})
        >>> user.secret_keys == {'a': {'foo': 'bar'}, 'b': {'bla': 'bla'}}
        True
        """
        self.implementation.update_secret_keys(self.secret_keys, secret_keys)
