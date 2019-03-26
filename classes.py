import funcs
import hashlib
import pickle


class Block:
    # This class is used to create a block, regardless of the validity of its content or hash
    # When initiating a block, the block id and prev_block_hash are set to -1,
    # meaning it is not yet defined. It will be when it is added to the chain.
    # We add the content as a list of transactions

    # Since we hash only the block metadata (aka header), there is no nested reference

    def __init__(self, block_content):
        self.block_content = block_content
        serialized_block_content = pickle.dumps(self.block_content)
        block_content_hash = hashlib.sha256(serialized_block_content).hexdigest()
        self.metadata = {
            "id": -1,
            "prev_block_hash": -1,
            "nonce": 0,
            "block_content_hash": block_content_hash
        }


class GenesisBlock(Block):
    # This subclass is used to create the genesis_block.
    # It sends 100 to Cerisiers 4
    def __init__(self):
        super().__init__(Transaction({}, {"Cerisiers 4": 100}))
        self.metadata["id"] = 0
        self.metadata["prev_block_hash"] = 0


class Transaction:

    # A dict of inputs is built of pairs of (txhash, id_of_output) -> order of dicts is guaranteed since Python 3.7
    # Outputs are in the form of a dict as well, but with pairs of (destination_address, amount)
    def __init__(self, dict_of_inputs, dict_of_outputs):

        self.internals = {
            "dict_of_inputs": dict_of_inputs,
            "dict_of_outputs": dict_of_outputs
        }

        serialized_transaction_internals = pickle.dumps(self.internals)
        self.txhash = hashlib.sha256(serialized_transaction_internals).hexdigest()


