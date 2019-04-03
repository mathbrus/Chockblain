import classes
import copy
import database
import hashlib
import pandas as pd
import pickle
import random


def create_genesis_block(output_address):
    """(Re)sets the blockchain and adds the first block."""
    if len(get_list_of_blocks()) > 0:
        prompt = input("Database is not empty, creating a new genesis block will erase it. Type [s] to stop. Press "
                       "any other key to continue.")
        if prompt == "s":
            raise KeyboardInterrupt

    genesis_block = classes.GenesisBlock(output_address)
    database.write_to_db([genesis_block])
    return genesis_block


def add_block_to_db(block):
    """Adds the block passed as parameter to the blockchain, with corresponding block id and prov_block_hash."""
    last_block = get_last_block()

    block.metadata["id"] = last_block.metadata["id"]+1
    block.metadata["prev_block_hash"] = get_block_hash(last_block)

    db = database.read_from_db()
    db.append(block)
    database.write_to_db(db)


def mine_block(block):
    """Returns a mined copy of the block, meaning the nonce is set so that the hash of the block is valid."""
    mined_block = copy.copy(block)
    last_block = get_last_block()

    mined_block.metadata["id"] = last_block.metadata["id"]+1
    mined_block.metadata["prev_block_hash"] = get_block_hash(last_block)

    hash_candidate = "1"

    while not hash_candidate.startswith("0000"):
        nonce = random.randint(0, 1000000)
        mined_block.metadata["nonce"] = nonce
        serialized_mined_block = pickle.dumps(block.metadata)
        hash_candidate = hashlib.sha256(serialized_mined_block).hexdigest()

    return mined_block


def get_block_hash(block):
    """Returns the "hash of a block", which is in fact the hash of the metadata of the block."""
    # With this function we can obtain the SHA256 hash of the block metadata
    # This is a bit a misnomer, since it does not hash the entire block
    serialized_block_metadata = pickle.dumps(block.metadata)
    block_hash = hashlib.sha256(serialized_block_metadata).hexdigest()
    return block_hash


def get_last_block():
    """Returns last block of the chain."""
    db = database.read_from_db()
    last_block = db[-1]
    return last_block


def get_list_of_blocks():
    """Returns the whole blockchain as a list of blocks."""
    db = database.read_from_db()
    return db


def get_transaction_by_txhash(tx_hash):
    """Returns the transaction using its hash, False otherwise."""

    db = database.read_from_db()

    # We loop through the blocks by skipping the genesis block
    for b in db[1:]:
        # For each block
        for t in b.block_content:
            # For each transaction
            if t.txhash == tx_hash:
                return t
    print("TransactionFinder : Unable to find a transaction.")
    return False


def get_amount_from_input(tx_hash, position):
    """Returns either the amount or False if not found."""

    # Does the input exist as output of another transaction ?
    tx = get_transaction_by_txhash(tx_hash)
    if tx is not False:
        # We have found the transaction
        try:
            list(tx.internals["dict_of_outputs"].items())[position]
        except IndexError:
            print("Reference to an unexisting output.")
            return False

        # We return the amount. Note that the items() methods returns tuples
        return list(tx.internals["dict_of_outputs"].items())[position][1]


def show_blockchain_summary():
    list_of_blocks = get_list_of_blocks()
    block_heights = []
    block_hashes = []
    prev_block_hashes = []
    for b in list_of_blocks:
        block_heights.append(b.metadata["id"])
        block_hashes.append(get_block_hash(b))
        prev_block_hashes.append(b.metadata["prev_block_hash"])

    table = pd.DataFrame()
    table["Block Height"] = block_heights
    table["Block Hash"] = block_hashes
    table["Previous Block Hash"] = prev_block_hashes
    table.set_index("Block Height", inplace=True)
    print("###########################################")
    print(table)
    print("###########################################")
