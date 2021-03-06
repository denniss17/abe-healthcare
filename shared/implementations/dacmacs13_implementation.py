import inspect
import logging
from typing import Any, Dict

from authority.attribute_authority import AttributeAuthority
from charm.schemes.abenc.abenc_dacmacs_yj14 import DACMACS
from charm.toolbox.pairinggroup import G1, PairingGroup
from service.central_authority import CentralAuthority
from shared.connection.user_attribute_authority_connection import UserAttributeAuthorityConnection
from shared.exception.policy_not_satisfied_exception import PolicyNotSatisfiedException
from shared.implementations.base_implementation import BaseImplementation, SecretKeyStore, AbeEncryption
from shared.implementations.serializer.base_serializer import BaseSerializer
from shared.model.global_parameters import GlobalParameters
from shared.utils.attribute_util import add_time_period_to_attribute, add_time_periods_to_policy


class DACMACS13Implementation(BaseImplementation):
    """
    The implementation according to
    "DAC-MACS: Effective Data Access Control for Multi-Authority Cloud Storage Systems "

    :paper:     DAC-MACS: Effective Data Access Control for Multi-Authority Cloud Storage Systems
    :authors:   Kan Yang, Xiaohua Jia
    :year:      2013
    """

    decryption_keys_required = True

    def __init__(self, group: PairingGroup = None) -> None:
        super().__init__(group)
        self._serializer = None  # type: BaseSerializer

    def get_name(self):
        return "DAC-MACS"

    def create_attribute_authority(self, name: str, storage_path: str = None) -> AttributeAuthority:
        return DACMACS13AttributeAuthority(name, self.serializer, storage_path=storage_path)

    def create_central_authority(self, storage_path: str = None) -> CentralAuthority:
        return DACMACS13CentralAuthority(self.group, self.serializer, storage_path=storage_path)

    @property
    def serializer(self) -> BaseSerializer:
        if self._serializer is None:
            self._serializer = DACMACS13Serializer(self.group, self.public_key_scheme)
        return self._serializer

    def abe_encrypt(self, global_parameters: GlobalParameters, public_keys: Dict[str, Any], message: bytes,
                    policy: str, time_period: int) -> AbeEncryption:
        dacmacs = DACMACS(self.group)
        policy = add_time_periods_to_policy(policy, time_period, self.group)
        return dacmacs.encrypt(global_parameters.scheme_parameters, public_keys, message, policy)

    def decryption_keys(self, global_parameters: GlobalParameters,
                        authorities: Dict[str, UserAttributeAuthorityConnection],
                        secret_keys: SecretKeyStore,
                        registration_data: Any, ciphertext: AbeEncryption, time_period: int):
        dacmacs = DACMACS(self.group)
        try:
            # This token generation is done internally at the client, so no network traffic is happening
            # This can only be the case when decryption is outsourced, in this case this token generation is performed
            # in the cloud.
            return dacmacs.generate_token(global_parameters.scheme_parameters, ciphertext, registration_data['public'],
                                          secret_keys)
        except Exception:
            raise PolicyNotSatisfiedException()

    def abe_decrypt(self, global_parameters: GlobalParameters, secret_keys: SecretKeyStore, gid: str,
                    ciphertext: AbeEncryption, registration_data) -> bytes:
        dacmacs = DACMACS(self.group)

        try:
            return dacmacs.decrypt(ciphertext, secret_keys, registration_data['private'])
        except Exception:
            raise PolicyNotSatisfiedException()


class DACMACS13CentralAuthority(CentralAuthority):
    def __init__(self, group, serializer: BaseSerializer, storage_path: str = None) -> None:
        super().__init__(group, serializer, storage_path=storage_path)
        self.master_key = None  # type: Any

    def register_user(self, gid: str) -> dict:
        dacmacs = DACMACS(self.global_parameters.group)
        public, private = dacmacs.register_user(self.global_parameters.scheme_parameters)
        cert = private['cert']
        del private['cert']
        return {'public': public, 'private': private, 'cert': cert}

    def central_setup(self):
        dacmacs = DACMACS(self.global_parameters.group)
        public_key, master_key = dacmacs.setup()
        self.master_key = master_key
        self.global_parameters.scheme_parameters = public_key
        return self.global_parameters


class DACMACS13AttributeAuthority(AttributeAuthority):
    def __init__(self, name: str, serializer: BaseSerializer, storage_path: str = None) -> None:
        super().__init__(name, serializer, storage_path=storage_path)
        self._public_keys = dict()
        self._secret_keys = dict()

    def setup(self, central_authority, attributes, time_period):
        self.global_parameters = central_authority.global_parameters
        self.attributes = attributes
        dacmacs = DACMACS(self.global_parameters.group)
        # These are the main keys, these keys will be reused for keys of the timed attributes
        self._public_keys['main'], self._secret_keys['main'] = dacmacs.authsetup(
            central_authority.global_parameters.scheme_parameters,
            self.attributes)
        del self._public_keys['main']['attr']
        del self._secret_keys['main']['attr']
        self.generate_keys_for_time_period(time_period)

    def public_keys(self, time_period: int) -> Any:
        if time_period not in self._public_keys:
            logging.error("UGH, this should not happen in an experiment as it messes the timings up.")
            logging.error(
                "DAC-MACS generating authority (%s) public keys for time period %d" % (self.name, time_period))
            curframe = inspect.currentframe()
            calframe = inspect.getouterframes(curframe, 2)
            logging.error('caller name: %s', calframe[1][3])
            self.generate_keys_for_time_period(time_period)
        return {
            'e(g,g)^alpha': self._public_keys['main']['e(g,g)^alpha'],
            'g^(1/beta)': self._public_keys['main']['g^(1/beta)'],
            'g^(gamma/beta)': self._public_keys['main']['g^(gamma/beta)'],
            'attr': self._public_keys[time_period]
        }

    def secret_keys(self, time_period: int) -> Any:
        if time_period not in self._secret_keys:
            logging.error("UGH, this should not happen in an experiment as it messes the timings up.")
            logging.error(
                "DAC-MACS generating authority (%s) public keys for time period %d" % (self.name, time_period))
            curframe = inspect.currentframe()
            calframe = inspect.getouterframes(curframe, 2)
            logging.error('caller name: %s', calframe[1][3])
            self.generate_keys_for_time_period(time_period)
        return {
            'alpha': self._secret_keys['main']['alpha'],
            'beta': self._secret_keys['main']['beta'],
            'gamma': self._secret_keys['main']['gamma'],
            'attr': self._secret_keys[time_period]
        }

    def generate_keys_for_time_period(self, time_period):
        """
        Generate the public and secret keys for the given time period.
        :param time_period: The time period
        """
        attributes = list(map(lambda x: add_time_period_to_attribute(x, time_period), self.attributes))

        dabe = DACMACS(self.global_parameters.group)
        public_keys = dict(self._public_keys['main'])
        secret_keys = dict(self._secret_keys['main'])
        public_keys['attr'] = dict()
        secret_keys['attr'] = dict()
        pk, sk = dabe.authsetup(self.global_parameters.scheme_parameters, attributes, secret_keys=secret_keys,
                                public_keys=public_keys)

        self._public_keys[time_period] = pk['attr']
        self._secret_keys[time_period] = sk['attr']

    def _keygen(self, gid, registration_data, attributes, time_period):
        dacmacs = DACMACS(self.global_parameters.group)
        attributes = map(lambda x: add_time_period_to_attribute(x, time_period), attributes)
        return {self.name: dacmacs.keygen(self.global_parameters.scheme_parameters,
                                          self.secret_keys(time_period),
                                          self.public_keys(time_period), attributes,
                                          registration_data['cert'])}


class DACMACS13Serializer(BaseSerializer):
    def serialize_global_scheme_parameters(self, scheme_parameters):
        # GPP = {'g': g, 'g^a': g_a, 'H': H}
        return {
            'g': self.group.serialize(scheme_parameters['g']),
            'g^a': self.group.serialize(scheme_parameters['g^a'])
        }

    def deserialize_global_scheme_parameters(self, data):
        # GPP = {'g': g, 'g^a': g_a, 'H': H}
        return {
            'g': self.group.deserialize(data['g']),
            'g^a': self.group.deserialize(data['g^a']),
            'H': lambda x: self.group.hash(x, G1),
        }

    def serialize_abe_ciphertext(self, ciphertext: AbeEncryption) -> Any:
        # {'policy': policy_str, 'C0': C0, 'C1': C1, 'C2': C2, 'C3': C3, 'C4': C4}
        # C0 = message * (gp['egg'] ** s)
        # C1[i] = gp['egg'] ** secret_shares[i] * pks[auth]['egga'] ** tx
        # C2[i] = gp['g1'] ** (-tx)
        # C3[i] = pks[auth]['gy'] ** tx * gp['g1'] ** zero_shares[i]
        # C4[i] = gp['F'](attr) ** tx
        dictionary = dict()  # type: dict
        return {
            'p': ciphertext['policy'],
            'C': self.group.serialize(ciphertext['C']),
            'C1': self.group.serialize(ciphertext['C1']),
            'C2': {self.replace_attributes(dictionary, k): self.group.serialize(v) for k, v in
                   ciphertext['C2'].items()},
            'Ci': {self.replace_attributes(dictionary, k): self.group.serialize(v) for k, v in
                   ciphertext['Ci'].items()},
            'D1': {self.replace_attributes(dictionary, k): self.group.serialize(v) for k, v in
                   ciphertext['D1'].items()},
            'D2': {self.replace_attributes(dictionary, k): self.group.serialize(v) for k, v in
                   ciphertext['D2'].items()},
            'd': dictionary
        }

    def deserialize_abe_ciphertext(self, dictionary: Any) -> AbeEncryption:
        return {
            'policy': dictionary['p'],
            'C': self.group.deserialize(dictionary['C']),
            'C1': self.group.deserialize(dictionary['C1']),
            'C2': {self.undo_attribute_replacement(dictionary['d'], k): self.group.deserialize(v) for k, v in
                   dictionary['C2'].items()},
            'Ci': {self.undo_attribute_replacement(dictionary['d'], k): self.group.deserialize(v) for k, v in
                   dictionary['Ci'].items()},
            'D1': {self.undo_attribute_replacement(dictionary['d'], k): self.group.deserialize(v) for k, v in
                   dictionary['D1'].items()},
            'D2': {self.undo_attribute_replacement(dictionary['d'], k): self.group.deserialize(v) for k, v in
                   dictionary['D2'].items()}
        }
