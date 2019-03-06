import funcs
import hashlib
import pickle

class Block:
    # This class is used to create a block, regardless of the validity of its content or hash
    # When initiating a block, the block id and prev_block_hash are set to -1,
    # meaning it is not yet defined. It will be when it is added to the chain.

    # Since we hash only the block metadata (aka header), there is no nested reference

    def __init__(self, block_content=0):
        self.block_content = block_content
        serialized_block_content = pickle.dumps(self.block_content)
        block_content_hash = hashlib.sha256(serialized_block_content).hexdigest()
        self.metadata = {
            "id": -1,
            "prev_block_hash": -1,
            "nonce": 0,
            "block_content_hash": block_content_hash
        }


class GenesisBlock:
    # This class is used to create the genesis_block.
    def __init__(self):
        self.block_content = 0
        serialized_block_content = pickle.dumps(self.block_content)
        block_content_hash = hashlib.sha256(serialized_block_content).hexdigest()
        self.metadata = {
            "id": 0,
            "prev_block_hash": 0,
            "nonce": 0,
            "block_content_hash": block_content_hash
        }

class Transaction:
    # This class is used to create a transaction, which spends and UTXO
    # We need and UTXO (input) in order to create a new UTXO (output)

    # Here we currently have nested references, hence we need serialized elements in the internals

    def __init__(self, input_element, destination_address, amount = 0):
        serialized_input_element = pickle.dumps(input_element)
        serialized_output_element = pickle.dumps(funcs.spend_UTXO(input_element, destination_address))
        self.internals = {
            "input": serialized_input_element,
            "output": serialized_output_element,
            "amount": amount
        }
        serialized_transaction_internals = pickle.dumps(self.internals)
        self.txhash = hashlib.sha256(serialized_transaction_internals).hexdigest()

class Element:

    # An element is the smallest unit in the program, it is either an input or an output
    # If there is a destination_address, then the element is spent

    def __init__(self, amount, associated_address):
        self.amount = amount
        self.associated_address = associated_address
