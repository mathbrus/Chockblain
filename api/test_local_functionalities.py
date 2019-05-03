from api import classes, crypto, database, exceptions, handling, validation
import hashlib
import pickle
import unittest


class SeedGenTests(unittest.TestCase):
    """Seed generation tests."""

    def setUp(self):
        self.seed = crypto.new_seed()
        self.address = crypto.get_address(self.seed)
        self.verifying_key_string = crypto._get_verifying_key_string(self.seed)

    def test_verify_address(self):
        self.assertTrue(crypto.verify_address(self.address, self.verifying_key_string))


class DataBaseTests(unittest.TestCase):
    """Database usage tests."""

    def setUp(self):
        self.db_path = 'database/db_test'
        database.init_database(self.db_path)

    def test_database_path(self):
        self.assertEqual(database._db_file_path, self.db_path)

    @unittest.expectedFailure
    def test_database_writing(self):
        with self.assertRaises(OSError):
            database.write_to_db(["test"])

    @unittest.expectedFailure
    def test_database_reading(self):
        with self.assertRaises(OSError):
            database.read_from_db()

    def tearDown(self):
        # We reset the database to the initial (empty) value.
        database.reinit_database()


class GenesisBlockTests(unittest.TestCase):
    """Genesis block tests."""

    def setUp(self):
        # Seed&Address
        self.seed = crypto.new_seed()
        self.address = crypto.get_address(self.seed)
        self.verifying_key_string = crypto._get_verifying_key_string(self.seed)

        # Db
        self.db_path = 'database/db_test'
        database.init_database(self.db_path)

    def test_genesis_block_creation(self):
        genesis_block = classes.GenesisBlock(self.address)
        handling.add_genesis_block(genesis_block)

        read_genesis_block = handling.get_last_block()
        list_of_blocks = handling.get_list_of_blocks()

        self.assertEqual(1, len(list_of_blocks), msg="Length of chain after genesis block is not equal to 1.")
        self.assertEqual(genesis_block, read_genesis_block, msg="Chain does not contain correct genesis block.")

    def tearDown(self):
        # We reset the database to the initial (empty) value.
        database.reinit_database()


class TransactionTests(unittest.TestCase):
    """Transaction creation tests."""

    def setUp(self):
        # Seed&Address (2 pairs)
        self.seed = crypto.new_seed()
        self.address = crypto.get_address(self.seed)
        self.verifying_key_string = crypto._get_verifying_key_string(self.seed)

        self.seed2 = crypto.new_seed()
        self.address2 = crypto.get_address(self.seed2)
        self.verifying_key_string2 = crypto._get_verifying_key_string(self.seed2)

        # Db
        self.db_path = 'database/db_test'
        database.init_database(self.db_path)

        # GenBlock
        self.genesis_block = classes.GenesisBlock(self.address)
        handling.add_genesis_block(self.genesis_block)

        # Input and output dicts, that spend the genesis tx to address2.
        self.dict_of_inputs = {self.genesis_block.block_content[0].txhash: 0}
        self.dict_of_outputs = {self.address2: 100}

    def test_transaction_signing(self):
        first_tx = classes.Transaction(self.dict_of_inputs, self.dict_of_outputs)
        first_tx.sign(self.seed)
        self.assertTrue(crypto.verify_signing(first_tx.txhash, first_tx.signature, first_tx.verifying_key))

    def tearDown(self):
        # We reset the database to the initial (empty) value.
        database.reinit_database()


class BlockTests(unittest.TestCase):
    """Block mining and chaining tests."""

    def setUp(self):
        # Seed&Address (2 pairs)
        self.seed = crypto.new_seed()
        self.address = crypto.get_address(self.seed)
        self.verifying_key_string = crypto._get_verifying_key_string(self.seed)

        self.seed2 = crypto.new_seed()
        self.address2 = crypto.get_address(self.seed2)
        self.verifying_key_string2 = crypto._get_verifying_key_string(self.seed2)

        self.address3 = self.address2 # For testing purposes only

        # Db
        self.db_path = 'database/db_test'
        database.init_database(self.db_path)

        # GenBlock
        self.genesis_block = classes.GenesisBlock(self.address)
        handling.add_genesis_block(self.genesis_block)

        # Tx1
        self.dict_of_inputs = {self.genesis_block.block_content[0].txhash: 0}
        self.dict_of_outputs = {self.address2: 100}
        self.first_tx = classes.Transaction(self.dict_of_inputs, self.dict_of_outputs)
        self.first_tx.sign(self.seed)

        # Block1
        self.first_block = classes.Block([self.first_tx])
        self.first_mined_block = handling.mine_block(self.first_block)

        handling.add_block_to_db(self.first_mined_block)

        # Tx2
        self.dict_of_inputs2 = {self.first_mined_block.block_content[0].txhash: 0}
        self.dict_of_outputs2 = {self.address3: 100}
        self.second_tx = classes.Transaction(self.dict_of_inputs2, self.dict_of_outputs2)
        self.second_tx.sign(self.seed2)

        # Block2
        self.second_block = classes.Block([self.second_tx])
        self.second_mined_block = handling.mine_block(self.second_block)

        handling.add_block_to_db(self.second_mined_block)

    def test_pow(self):
        # Testing the number of leading 0
        serialized_mined_block = pickle.dumps(self.first_mined_block.metadata)
        block_hash = hashlib.sha256(serialized_mined_block).hexdigest()

        self.assertTrue(block_hash.startswith("0000"))

        serialized_mined_block = pickle.dumps(self.second_mined_block.metadata)
        block_hash = hashlib.sha256(serialized_mined_block).hexdigest()

        self.assertTrue(block_hash.startswith("0000"))

    def test_prev_block_hash(self):
        # Checking if hash of block one correspond to prev_block_hash of block two
        serialized_mined_block = pickle.dumps(self.first_mined_block.metadata)
        first_block_hash = hashlib.sha256(serialized_mined_block).hexdigest()

        last_block = handling.get_last_block()
        prev_block_hash = last_block.metadata["prev_block_hash"]
        self.assertEqual(first_block_hash, prev_block_hash)

    def tearDown(self):
        # We reset the database to the initial (empty) value.
        database.reinit_database()


class ValidationTests(unittest.TestCase):
    """Block Validation tests."""

    def setUp(self):
        # Seed&Address (2 pairs)
        self.seed = crypto.new_seed()
        self.address = crypto.get_address(self.seed)
        self.verifying_key_string = crypto._get_verifying_key_string(self.seed)

        self.seed2 = crypto.new_seed()
        self.address2 = crypto.get_address(self.seed2)
        self.verifying_key_string2 = crypto._get_verifying_key_string(self.seed2)

        self.address3 = self.address2 # For testing purposes only

        # Db
        self.db_path = 'database/db_test'
        database.init_database(self.db_path)

    def test_double_spend(self):
        # (Re)Starting from GenBlock
        genesis_block = classes.GenesisBlock(self.address)
        handling.add_genesis_block(genesis_block)

        # Tx1
        dict_of_inputs = {genesis_block.block_content[0].txhash: 0}
        dict_of_outputs = {self.address2: 100}
        first_tx = classes.Transaction(dict_of_inputs, dict_of_outputs)
        first_tx.sign(self.seed)

        # Block1
        first_block = classes.Block([first_tx])
        first_mined_block = handling.mine_block(first_block)

        handling.add_block_to_db(first_mined_block)

        # Tx2
        dict_of_inputs2 = {first_mined_block.block_content[0].txhash: 0}
        dict_of_outputs2 = {self.address3: 100}
        second_tx = classes.Transaction(dict_of_inputs2, dict_of_outputs2)
        second_tx.sign(self.seed2)

        # Block2
        second_block = classes.Block([second_tx])
        second_mined_block = handling.mine_block(second_block)

        handling.add_block_to_db(second_mined_block)

        # Tx3 -> We try to double spend the same input as we spent in the previous block
        dict_of_inputs3 = {first_mined_block.block_content[0].txhash: 0}
        dict_of_outputs3 = {self.address3: 100}
        third_tx = classes.Transaction(dict_of_inputs3, dict_of_outputs3)
        third_tx.sign(self.seed2)

        third_block = classes.Block([third_tx])
        third_mined_block = handling.mine_block(third_block)

        with self.assertRaises(exceptions.ValidationError):
            validation.validate_block(third_mined_block)

    def test_incorrect_amounts(self):
        # Trying to spend more than what we have in the inputs
        # (Re)Starting from GenBlock
        genesis_block = classes.GenesisBlock(self.address)
        handling.add_genesis_block(genesis_block)

        # Tx1
        dict_of_inputs = {genesis_block.block_content[0].txhash: 0}
        dict_of_outputs = {self.address2: 100}
        first_tx = classes.Transaction(dict_of_inputs, dict_of_outputs)
        first_tx.sign(self.seed)

        # Block1
        first_block = classes.Block([first_tx])
        first_mined_block = handling.mine_block(first_block)

        handling.add_block_to_db(first_mined_block)

        # Tx2 -> We try to put 101 as output amount
        dict_of_inputs2 = {first_mined_block.block_content[0].txhash: 0}
        dict_of_outputs2 = {self.address3: 101}
        second_tx = classes.Transaction(dict_of_inputs2, dict_of_outputs2)
        second_tx.sign(self.seed2)

        # Block2
        second_block = classes.Block([second_tx])
        second_mined_block = handling.mine_block(second_block)

        handling.add_block_to_db(second_mined_block)

        with self.assertRaises(exceptions.ValidationError):
            validation.validate_block(second_mined_block)

    def test_wrong_input(self):
        # Trying to spend inexistant input
        # (Re)Starting from GenBlock
        genesis_block = classes.GenesisBlock(self.address)
        handling.add_genesis_block(genesis_block)

        # Tx1
        dict_of_inputs = {genesis_block.block_content[0].txhash: 0}
        dict_of_outputs = {self.address2: 100}
        first_tx = classes.Transaction(dict_of_inputs, dict_of_outputs)
        first_tx.sign(self.seed)

        # Block1
        first_block = classes.Block([first_tx])
        first_mined_block = handling.mine_block(first_block)

        handling.add_block_to_db(first_mined_block)

        # Tx2 -> we try to spend an unexisting input
        dict_of_inputs2 = {first_mined_block.block_content[0].txhash: 1}
        dict_of_outputs2 = {self.address3: 100}
        second_tx = classes.Transaction(dict_of_inputs2, dict_of_outputs2)
        second_tx.sign(self.seed2)

        # Block2
        second_block = classes.Block([second_tx])
        second_mined_block = handling.mine_block(second_block)

        handling.add_block_to_db(second_mined_block)

        with self.assertRaises(exceptions.HandlingError):  # Since the exceptions comes from one level deeper.
            validation.validate_block(second_mined_block)

    def test_fake_ownership(self):
        # Trying to spend someone else's output
        # (Re)Starting from GenBlock
        genesis_block = classes.GenesisBlock(self.address)
        handling.add_genesis_block(genesis_block)

        # Tx1 -> We send it to an address belonging to seed
        dict_of_inputs = {genesis_block.block_content[0].txhash: 0}
        dict_of_outputs = {self.address: 100}
        first_tx = classes.Transaction(dict_of_inputs, dict_of_outputs)
        first_tx.sign(self.seed)

        # Block1
        first_block = classes.Block([first_tx])
        first_mined_block = handling.mine_block(first_block)

        handling.add_block_to_db(first_mined_block)

        # Tx2 -> we try to spend someone else's output since we sign with seed2
        dict_of_inputs2 = {first_mined_block.block_content[0].txhash: 0}
        dict_of_outputs2 = {self.address3: 100}
        second_tx = classes.Transaction(dict_of_inputs2, dict_of_outputs2)
        second_tx.sign(self.seed2)

        # Block2
        second_block = classes.Block([second_tx])
        second_mined_block = handling.mine_block(second_block)

        handling.add_block_to_db(second_mined_block)

        with self.assertRaises(exceptions.ValidationError):
            validation.validate_block(second_mined_block)

    def tearDown(self):
        # We reset the database to the initial (empty) value.
        database.reinit_database()


if __name__ == '__main__':
    unittest.main()

