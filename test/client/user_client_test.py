import pickle
import unittest

from client.user_client import UserClient
from service.insurance_service import InsuranceService
from shared.exception.policy_not_satisfied_exception import PolicyNotSatisfiedException
from shared.implementations.base_implementation import BaseImplementation
from shared.implementations.dacmacs13_implementation import DACMACS13Implementation
from shared.implementations.rd13_implementation import RD13Implementation
from shared.implementations.rw15_implementation import RW15Implementation
from shared.implementations.taac12_implementation import TAAC12Implementation
from shared.model.user import User


class UserClientTestCase(unittest.TestCase):
    access_policy = '(TEST@TEST OR TEST2@TEST) AND (TEST3@TEST OR TEST4@TEST)'

    def setUpWithImplementation(self, implementation: BaseImplementation):
        central_authority = implementation.create_central_authority()
        central_authority.central_setup()
        attributes = ['TEST@TEST', 'TEST2@TEST', 'TEST3@TEST', 'TEST4@TEST']
        user_attributes = ['TEST@TEST', 'TEST3@TEST', 'TEST4@TEST']
        attribute_authority = implementation.create_attribute_authority('TEST')
        attribute_authority.setup(central_authority, attributes, 1)
        for attribute in user_attributes:
            attribute_authority.revoke_attribute_indirect('bob', attribute, 2)
        insurance_service = InsuranceService(implementation.serializer, central_authority,
                                             implementation.public_key_scheme)
        insurance_service.add_authority(attribute_authority)
        user = User('bob', implementation)

        self.subject = UserClient(user, implementation)
        self.subject.register(insurance_service)
        self.subject.request_secret_keys(attribute_authority.name, user_attributes, 1)

    def test_create_record_dacmacs13(self):
        self._test_create_record(DACMACS13Implementation())

    def test_create_record_rd13(self):
        self._test_create_record(RD13Implementation())

    def test_create_record_rw15(self):
        self._test_create_record(RW15Implementation())

    def test_create_record_taac12(self):
        self._test_create_record(TAAC12Implementation())

    def _test_create_record(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record = self.subject.create_record(self.access_policy, self.access_policy, b'Hello world',
                                                   {'test': 'info'}, 1)
        self.assertIsNotNone(create_record.info)
        self.assertIsNotNone(create_record.write_policy)
        self.assertIsNotNone(create_record.read_policy)
        self.assertIsNotNone(create_record.write_public_key)
        self.assertIsNotNone(create_record.owner_public_key)
        self.assertIsNotNone(create_record.encryption_key_read)
        self.assertIsNotNone(create_record.encryption_key_owner)
        self.assertIsNotNone(create_record.write_private_key)
        self.assertIsNotNone(create_record.time_period)
        self.assertIsNotNone(create_record.data)
        self.assertNotEqual(create_record.data, b'Hello world')

        # Attempt to decrypt
        info, message = self.subject.decrypt_record(create_record)
        self.assertEqual(message, b'Hello world')
        self.assertEqual(info, {'test': 'info'})

    def test_update_record_dacmacs13(self):
        self._test_update_record(DACMACS13Implementation())

    def test_update_record_rd13(self):
        self._test_update_record(RD13Implementation())

    def test_update_record_rw15(self):
        self._test_update_record(RW15Implementation())

    def test_update_record_taac12(self):
        self._test_update_record(TAAC12Implementation())

    def _test_update_record(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record = self.subject.create_record(self.access_policy, self.access_policy, b'Hello world',
                                                   {'test': 'info'}, 1)
        update_record = self.subject.update_record(create_record, b'Goodbye world')
        self.assertIsNotNone(update_record.data)
        self.assertIsNotNone(update_record.signature)
        pke = self.subject.implementation.public_key_scheme
        self.assertTrue(pke.verify(create_record.write_public_key, update_record.signature,
                                   update_record.data))

        # Update the original record
        create_record.update(update_record)

        # Attempt to decrypt
        info, message = self.subject.decrypt_record(create_record)
        self.assertEqual(message, b'Goodbye world')

    def test_update_policy_dacmacs13(self):
        self._test_update_policy(DACMACS13Implementation())

    def test_update_policy_rd13(self):
        self._test_update_policy(RD13Implementation())

    def test_update_policy_rw15(self):
        self._test_update_policy(RW15Implementation())

    def test_update_policy_taac12(self):
        self._test_update_policy(TAAC12Implementation())

    def _test_update_policy(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record = self.subject.create_record(self.access_policy, self.access_policy, b'Hello world',
                                                   {'test': 'info'}, 1)
        update_record = self.subject.update_policy(create_record, 'TEST3@TEST', 'TEST4@TEST', 1)

        self.assertIsNotNone(update_record.info)
        self.assertIsNotNone(update_record.write_policy)
        self.assertIsNotNone(update_record.read_policy)
        self.assertIsNotNone(update_record.write_public_key)
        self.assertIsNotNone(update_record.encryption_key_read)
        self.assertIsNotNone(update_record.encryption_key_owner)
        self.assertIsNotNone(update_record.write_private_key)
        self.assertIsNotNone(update_record.time_period)
        self.assertIsNotNone(update_record.data)
        self.assertIsNotNone(update_record.signature)
        pke = self.subject.implementation.public_key_scheme
        self.assertTrue(pke.verify(create_record.owner_public_key, update_record.signature,
                                   pickle.dumps((update_record.read_policy,
                                                 update_record.write_policy,
                                                 update_record.time_period))))

        # Update the original record
        create_record.update_policy(update_record)

        self.assertEqual('TEST3@TEST', create_record.read_policy)
        self.assertEqual('TEST4@TEST', create_record.write_policy)

        # Update the owner key, so the subject has to use attribute keys to decrypt
        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        self.assertNotEqual(create_record.owner_public_key, self.subject.user.owner_key_pair.publickey())

        # Attempt to decrypt
        info, message = self.subject.decrypt_record(create_record)
        self.assertEqual(message, b'Hello world')

    def test_update_policy_to_insufficient_policy_dacmacs13(self):
        self._test_update_policy_to_insufficient_policy(DACMACS13Implementation())

    def test_update_policy_to_insufficient_policy_rd13(self):
        self._test_update_policy_to_insufficient_policy(RD13Implementation())

    def test_update_policy_to_insufficient_policy_rw15(self):
        self._test_update_policy_to_insufficient_policy(RW15Implementation())

    def test_update_policy_to_insufficient_policy_taac12(self):
        self._test_update_policy_to_insufficient_policy(TAAC12Implementation())

    def _test_update_policy_to_insufficient_policy(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record = self.subject.create_record(self.access_policy, self.access_policy, b'Hello world',
                                                   {'test': 'info'}, 1)

        # Now update to policies which the user can not satisfy
        update_record = self.subject.update_policy(create_record, 'TEST2@TEST', 'TEST2@TEST', 1)

        # Update the original record
        create_record.update_policy(update_record)

        self.assertEqual('TEST2@TEST', create_record.read_policy)
        self.assertEqual('TEST2@TEST', create_record.write_policy)

        # Update the owner key, so the subject has to use attribute keys to decrypt
        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        self.assertNotEqual(create_record.owner_public_key, self.subject.user.owner_key_pair.publickey())

        # Attempt to decrypt
        try:
            self.subject.decrypt_record(create_record)
            self.fail('PolicyNotSatisfiedException expected')
        except PolicyNotSatisfiedException:
            pass

    def test_update_policy_to_invalid_time_period_dacmacs13(self):
        self._test_update_policy_to_invalid_time_period(DACMACS13Implementation())

    def test_update_policy_to_invalid_time_period_rd13(self):
        self._test_update_policy_to_invalid_time_period(RD13Implementation())

    def test_update_policy_to_invalid_time_period_rw15(self):
        self._test_update_policy_to_invalid_time_period(RW15Implementation())

    def test_update_policy_to_invalid_time_period_taac12(self):
        self._test_update_policy_to_invalid_time_period(TAAC12Implementation())

    def _test_update_policy_to_invalid_time_period(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record = self.subject.create_record(self.access_policy, self.access_policy, b'Hello world',
                                                   {'test': 'info'}, 1)

        # Now update to policies which the user can not satisfy
        update_record = self.subject.update_policy(create_record, create_record.read_policy, create_record.write_policy,
                                                   2)

        # Update the original record
        create_record.update_policy(update_record)

        self.assertEqual(self.access_policy, create_record.read_policy)
        self.assertEqual(self.access_policy, create_record.write_policy)

        # Update the owner key, so the subject has to use attribute keys to decrypt
        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        self.assertNotEqual(create_record.owner_public_key, self.subject.user.owner_key_pair.publickey())

        # Attempt to decrypt
        try:
            self.subject.decrypt_record(create_record)
            self.fail('PolicyNotSatisfiedException expected')
        except PolicyNotSatisfiedException:
            pass

    def test_decrypt_record_dacmacs13(self):
        self._test_decrypt_record(DACMACS13Implementation())

    def test_decrypt_record_rd13(self):
        self._test_decrypt_record(RD13Implementation())

    def test_decrypt_record_rw15(self):
        self._test_decrypt_record(RW15Implementation())

    def test_decrypt_record_taac12(self):
        self._test_decrypt_record(TAAC12Implementation())

    def _test_decrypt_record(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record_valid = self.subject.create_record(self.access_policy, self.access_policy, b'Hello world',
                                                         {'test': 'info'}, 1)
        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        self.assertNotEqual(create_record_valid.owner_public_key, self.subject.user.owner_key_pair.publickey())

        # Attempt to decrypt
        info, message = self.subject.decrypt_record(create_record_valid)
        self.assertEqual(message, b'Hello world')
        self.assertEqual(info, {'test': 'info'})

    def test_decrypt_record_with_owner_key_dacmacs13(self):
        self._test_decrypt_record_with_owner_key(DACMACS13Implementation())

    def test_decrypt_record_with_owner_key_rd13(self):
        self._test_decrypt_record_with_owner_key(RD13Implementation())

    def test_decrypt_record_with_owner_key_rw15(self):
        self._test_decrypt_record_with_owner_key(RW15Implementation())

    def test_decrypt_record_with_owner_key_taac12(self):
        self._test_decrypt_record_with_owner_key(TAAC12Implementation())

    def _test_decrypt_record_with_owner_key(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        # We use a policy the subject does not have enough attributes for
        create_record_valid = self.subject.create_record('TEST2@TEST', self.access_policy, b'Hello world',
                                                         {'test': 'info'}, 1)
        self.assertEqual(create_record_valid.owner_public_key, self.subject.user.owner_key_pair.publickey())

        # Attempt to decrypt
        info, message = self.subject.decrypt_record(create_record_valid)
        self.assertEqual(message, b'Hello world')
        self.assertEqual(info, {'test': 'info'})

    def test_decrypt_record_with_insufficient_attributes_dacmacs13(self):
        self._test_decrypt_record_with_insufficient_attributes(DACMACS13Implementation())

    def test_decrypt_record_with_insufficient_attributes_rd13(self):
        self._test_decrypt_record_with_insufficient_attributes(RD13Implementation())

    def test_decrypt_record_with_insufficient_attributes_rw15(self):
        self._test_decrypt_record_with_insufficient_attributes(RW15Implementation())

    def test_decrypt_record_with_insufficient_attributes_taac12(self):
        self._test_decrypt_record_with_insufficient_attributes(TAAC12Implementation())

    def _test_decrypt_record_with_insufficient_attributes(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record_invalid = self.subject.create_record('TEST2@TEST', self.access_policy, b'Hello world',
                                                           {'test': 'info'}, 1)
        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        self.assertNotEqual(create_record_invalid.owner_public_key, self.subject.user.owner_key_pair.publickey())

        # Attempt to decrypt
        try:
            self.subject.decrypt_record(create_record_invalid)
            self.fail("PolicyNotSatisfiedException expected")
        except PolicyNotSatisfiedException:
            pass

    def test_decrypt_record_invalid_with_time_period_dacmacs13(self):
        self._test_decrypt_record_with_invalid_time_period(DACMACS13Implementation())

    def test_decrypt_record_invalid_with_time_period_rd13(self):
        self._test_decrypt_record_with_invalid_time_period(RD13Implementation())

    def test_decrypt_record_invalid_with_time_period_rw15(self):
        self._test_decrypt_record_with_invalid_time_period(RW15Implementation())

    def test_decrypt_record_invalid_with_time_period_taac12(self):
        self._test_decrypt_record_with_invalid_time_period(TAAC12Implementation())

    def _test_decrypt_record_with_invalid_time_period(self, implementation):
        self.setUpWithImplementation(implementation)

        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        create_record_invalid = self.subject.create_record(self.access_policy, self.access_policy, b'Hello world',
                                                           {'test': 'info'}, 2)
        self.subject.user.owner_key_pair = self.subject.create_owner_key()
        self.assertNotEqual(create_record_invalid.owner_public_key, self.subject.user.owner_key_pair.publickey())

        # Attempt to decrypt
        try:
            self.subject.decrypt_record(create_record_invalid)
            self.fail("PolicyNotSatisfiedException expected")
        except PolicyNotSatisfiedException:
            pass


if __name__ == '__main__':
    unittest.main()
