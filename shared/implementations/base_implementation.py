from typing import Any, Dict, Tuple

from authority.attribute_authority import AttributeAuthority
from charm.core.math.pairing import GT
from charm.toolbox.pairinggroup import PairingGroup
from service.central_authority import CentralAuthority
from shared.connection.user_attribute_authority_connection import UserAttributeAuthorityConnection
from shared.implementations.public_key.base_public_key import BasePublicKey
from shared.implementations.public_key.rsa_public_key import RSAPublicKey
from shared.implementations.serializer.base_serializer import BaseSerializer
from shared.implementations.symmetric_key.aes_symmetric_key import AESSymmetricKey
from shared.implementations.symmetric_key.base_symmetric_key import BaseSymmetricKey
from shared.model.global_parameters import GlobalParameters
from shared.model.types import SecretKeyStore, SecretKeys, AbeEncryption, RegistrationData, DecryptionKeys, \
    AuthorityPublicKeysStore
from shared.utils.key_utils import extract_key_from_group_element


class BaseImplementation(object):
    """
    The base implementation provider for different ABE implementations. Acts as an abstract factory for
    implementation specific subclasses of various scheme classes.
    """

    def __init__(self, group: PairingGroup = None) -> None:
        self.group = PairingGroup('SS512') if group is None else group
        self._public_key_scheme = None  # type:BasePublicKey
        self._symmetric_key_scheme = None  # type:BaseSymmetricKey

    def get_name(self):
        return self.__class__.__name__

    def create_central_authority(self, storage_path: str = None) -> CentralAuthority:
        """
        Create a new central authority.
        :return: The central authority of this implementation.
        """
        raise NotImplementedError()

    def create_attribute_authority(self, name: str, storage_path: str = None) -> AttributeAuthority:
        """
        Create a new attribute authority.
        :param storage_path: The path to the directory to use as storage for the authority.
        :param name: The name of the authority.
        :return: An attribute authority of this implementation
        """
        raise NotImplementedError()

    @property
    def serializer(self) -> BaseSerializer:
        """
        Create a new serializer.
        :return:  A new BaseSerializer
        """
        raise NotImplementedError()

    @property
    def public_key_scheme(self) -> BasePublicKey:
        """
        Create a new public key scheme
        :return: A BasePublicKey
        """
        if self._public_key_scheme is None:
            self._public_key_scheme = RSAPublicKey()
        return self._public_key_scheme

    @property
    def symmetric_key_scheme(self) -> BaseSymmetricKey:
        """
        Create a new public key scheme
        :return: A BasePublicKey
        """
        if self._symmetric_key_scheme is None:
            self._symmetric_key_scheme = AESSymmetricKey()
        return self._symmetric_key_scheme

    def setup_secret_keys(self, gid: str) -> SecretKeyStore:
        """
        Setup the secret key store for the given user.
        :param gid: The gid of the user
        :return: The key store for the given user.
        """
        return {}

    def update_secret_keys(self, base_keys: SecretKeyStore, secret_keys: SecretKeys) -> None:
        """
        Add new keys to the secret keys of a user.
        :param base_keys:
        :param secret_keys:
        """
        base_keys.update(secret_keys)

    def merge_public_keys(self, public_keys: Dict[str, AuthorityPublicKeysStore]) -> Dict[str, Any]:
        """
        Merge the public keys of the attribute authorities to a single entity containing all
        public keys.
        :param public_keys: A dict from authority name to public keys of the authority
        :return: A dict containing the public keys of the authorities.

        >>> from authority.attribute_authority import AttributeAuthority
        >>> a1 = AttributeAuthority('A1', None)
        >>> a2 = AttributeAuthority('A2', None)
        >>> a1._public_keys = {'foo': 'bar'}
        >>> a2._public_keys = {'a': 'b'}
        >>> base_implementation = BaseImplementation()
        >>> public_keys = base_implementation.merge_public_keys({a1.name: a1._public_keys, a2.name: a2._public_keys})
        >>> public_keys == {'A1': {'foo': 'bar'}, 'A2': {'a': 'b'}}
        True
        """
        return public_keys

    def generate_abe_key(self, global_parameters: GlobalParameters) -> Tuple[Any, bytes]:
        """
        Generate a random key and the extracted symmetric key to be used in attribute based encryption.
        The first key can be encrypted using attribute based encryption, while the second can be applied in symmetric encryption.
        :param global_parameters: The global parameters
        :return: The key (element of group) and the extracted symmetric key
        """
        key = global_parameters.group.random(GT)
        ske = self.symmetric_key_scheme
        symmetric_key = extract_key_from_group_element(global_parameters.group, key,
                                                       ske.ske_key_size())
        return key, symmetric_key

    def abe_encrypt(self, global_parameters: GlobalParameters, public_keys: Dict[str, Any], message: bytes,
                    policy: str, time_period: int) -> AbeEncryption:
        """
        Encrypt the message using attribute based encryption. This only works if message can be encrypted
        by the underlying implementation (in practice: element of a group).
        :param time_period: The time period for which to encrypt.
        :param global_parameters: The global parameters.
        :param public_keys: The public keys of the authorities
        :param message: The message to encrypt.
        :param policy: The policy to encrypt under.
        :return: The encrypted message.
        """
        raise NotImplementedError()

    def abe_encrypt_wrapped(self, global_parameters: GlobalParameters, public_keys: Dict[str, Any], message: bytes,
                            policy: str, time_period: int) -> Tuple[AbeEncryption, bytes]:
        """
        Encrypt the message using attribute based encryption, by encrypting the message with symmetric encryption and
        the key with attribute based encryption.
        :param time_period: The time period for which to encrypt.
        :param global_parameters: The global parameters.
        :param public_keys: The public keys of the authorities
        :param message: The message to encrypt.
        :param policy: The policy to encrypt under.
        :return: The encrypted key and the encrypted message.
        """
        ske = self.symmetric_key_scheme
        key, symmetric_key = self.generate_abe_key(global_parameters)
        ciphertext = ske.ske_encrypt(message, symmetric_key)
        encrypted_key = self.abe_encrypt(global_parameters, public_keys, key, policy, time_period)
        return encrypted_key, ciphertext

    def decryption_keys(self, global_parameters: GlobalParameters,
                        authorities: Dict[str, UserAttributeAuthorityConnection],
                        secret_keys: SecretKeyStore,
                        registration_data: Any, ciphertext: AbeEncryption, time_period: int):
        """
        Calculate decryption keys for a user for the given attribute authority.
        :param global_parameters: The global parameters.
        :param authorities: The attribute authorities to fetch update keys of.
        :param secret_keys: The secret keys of the user.
        :param registration_data: The registration data of the user
        :param ciphertext: The ciphertext to create decryption keys for.
        :param time_period: The time period to calculate the decryption keys for.
        :return: The decryption keys for the attributes of the authority the user possesses at the given time period.
        """
        return secret_keys

    def abe_decrypt(self, global_parameters: GlobalParameters, decryption_keys: DecryptionKeys, gid: str,
                    ciphertext: AbeEncryption, registration_data: RegistrationData) -> bytes:
        """
        Decrypt some ciphertext resulting from an attribute based encryption to the plaintext.
        :param global_parameters: The global parameters.
        :param decryption_keys: The secret keys of the user.
        :param gid: The global identifier of the user
        :param ciphertext: The ciphertext to decrypt.
        :param registration_data: The registration data of the user.
        :raise exception.policy_not_satisfied_exception.PolicyNotSatisfiedException: raised when the secret keys do not satisfy the access policy
        :return: The plaintext
        """
        raise NotImplementedError()

    def abe_decrypt_wrapped(self, global_parameters: GlobalParameters, decryption_keys: DecryptionKeys,
                            gid: str,
                            ciphertext_tuple: Tuple[AbeEncryption, bytes], registration_data: RegistrationData):
        """
        Decrypt some ciphertext resulting from a wrapped attribute based encryption
        (encrypted with symmetric key encryption and attribute based encryption) to the plaintext.
        :param global_parameters: The global parameters.
        :type global_parameters: records.global_parameters.GlobalParameters
        :param decryption_keys: The decryption keys keys of the user.
        :param gid: The global identifier of the user
        :param ciphertext_tuple: The ciphertext to decrypt. This is a tuple containing the encrypted key and the ciphertext
        encrypted using symmetric key encryption.
        :param registration_data: The registration data of the user.
        :raise Exception: raised when the secret keys do not satisfy the access policy
        :return: The plaintext
        """
        ske = self.symmetric_key_scheme
        encrypted_key, ciphertext = ciphertext_tuple
        key = self.abe_decrypt(global_parameters, decryption_keys, gid, encrypted_key, registration_data)
        symmetric_key = extract_key_from_group_element(global_parameters.group, key,
                                                       ske.ske_key_size())
        return ske.ske_decrypt(ciphertext, symmetric_key)


class MockImplementation(BaseImplementation):
    """
    Mock implementation for testing purposes
    """

    @property
    def serializer(self) -> BaseSerializer:
        return None

    def abe_decrypt(self, global_parameters: GlobalParameters, decryption_keys: DecryptionKeys, gid: str,
                    ciphertext: AbeEncryption, registration_data: RegistrationData) -> bytes:
        pass

    def abe_encrypt(self, global_parameters: GlobalParameters, public_keys: Dict[str, Any], message: bytes, policy: str,
                    time_period: int) -> AbeEncryption:
        pass

    def create_central_authority(self, storage_path: str = None) -> CentralAuthority:
        pass

    def create_attribute_authority(self, name: str, storage_path: str = None) -> AttributeAuthority:
        pass

    def update_secret_keys(self, base: SecretKeyStore, secret_keys: SecretKeys) -> None:
        base.update(secret_keys)

    def setup_secret_keys(self, gid: str) -> SecretKeyStore:
        return {}
