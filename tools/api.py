import copy
import hashlib
import pandas as pd
import pickle
import random
from tools import crypto, database, exceptions, validation


def add_genesis_block(genesis_block):
    """(Re)sets the blockchain and adds the first block."""

    database.write_to_db([genesis_block])
    return genesis_block


def add_block_to_db(block):
    """Adds the block passed as parameter to the blockchain, with corresponding block id and prov_block_hash. Does not
    verify validity."""

    last_block = get_last_block()

    block.metadata["id"] = last_block.metadata["id"]+1
    block.metadata["prev_block_hash"] = validation.get_block_hash(last_block)

    db = get_database()
    db.append(block)
    database.write_to_db(db)


def remove_last_block_from_db(block):
    """Removes the last block from the database. Used by a fullnode when the block is invalid."""

    invalid_db = get_database()
    valid_db = invalid_db.pop()

    database.write_to_db(valid_db)


def mine_block(block):
    """Returns a mined copy of the block, meaning the nonce is set so that the hash of the block is valid."""

    mined_block = copy.copy(block)
    last_block = get_last_block()

    mined_block.metadata["id"] = last_block.metadata["id"]+1
    mined_block.metadata["prev_block_hash"] = validation.get_block_hash(last_block)

    hash_candidate = "1"

    while not hash_candidate.startswith("0000"):
        nonce = random.randint(0, 1000000)
        mined_block.metadata["nonce"] = nonce
        serialized_mined_block = pickle.dumps(block.metadata)
        hash_candidate = hashlib.sha256(serialized_mined_block).hexdigest()

    return mined_block


def get_last_block():
    """Returns last block of the chain."""

    db = database.read_from_db()
    last_block = db[-1]
    return last_block


def get_database():
    """Returns the whole blockchain as a list of blocks."""

    db = database.read_from_db()
    return db


def get_transaction_by_txhash(tx_hash):
    """Returns the transaction using its hash, raises a APIError otherwise."""

    db = database.read_from_db()

    # We loop through the blocks by skipping the genesis block
    for b in db[1:]:
        # For each block
        for t in b.block_content:
            # For each transaction
            if t.txhash == tx_hash:
                return t

    raise exceptions.APIError("Cannot find transaction with txhash {}.".format(tx_hash))


def get_amount_from_input(tx_hash, position):
    """Returns the amount or the nested APIError if not found. If the position is not correct, returns an
    IndexError."""

    tx = get_transaction_by_txhash(tx_hash)

    # We take the amount. Note that the items() methods returns tuples
    try:
        amount = list(tx.internals["dict_of_outputs"].items())[position][1]
    except IndexError:
        raise exceptions.APIError("Incorrect input position for input no. {} of transaction with hash {} when "
                                       "trying to get amount.".format(position, tx_hash))
    return amount


def get_balance_from_address(address):
    """Recovers the balance of an address, given the address."""
    db = database.read_from_db()

    # To construct a balance, we need the total output that point to it minus the inputs that come from it
    balance_in = 0
    balance_out = 0

    # We loop through the blocks by skipping the genesis block.
    for b in db[1:]:
        # For each block
        for t in b.block_content:

            # For each transaction
            for addr in t.internals["dict_of_outputs"].keys():
                if addr == address:
                    balance_in += t.internals["dict_of_outputs"][addr]  # The amount in

            if crypto.verify_address(address, t.verifying_key):
                # The transaction has been signed with the key corresponding to the address : it is an output
                for output_element in t.internals["dict_of_outputs"].values():
                    balance_out += output_element

    return balance_in-balance_out


def spend_address(address, amount=0):
    """Creates a transaction by taking an address as input. If amount=0, it spends everything."""
    pass


def show_blockchain_summary():
    list_of_blocks = get_database()
    block_heights = []
    block_hashes = []
    prev_block_hashes = []
    for b in list_of_blocks:
        block_heights.append(b.metadata["id"])
        block_hashes.append(validation.get_block_hash(b))
        prev_block_hashes.append(b.metadata["prev_block_hash"])

    table = pd.DataFrame()
    table["Block Height"] = block_heights
    table["Block Hash"] = block_hashes
    table["Previous Block Hash"] = prev_block_hashes
    table.set_index("Block Height", inplace=True)
    print("###########################################")
    print(table)
    print("###########################################")
