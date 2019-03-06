import copy
import hashlib
import pandas as pd
import pickle
import random
import classes

def create_genesis_block():
    genesis_block = classes.GenesisBlock()
    db_file = open('database/db', 'wb')
    db = [genesis_block]
    pickle.dump(db, db_file)
    db_file.close()
    return genesis_block


def add_block_to_db(block):
    last_block = get_last_block()

    block.metadata["id"] = last_block.metadata["id"]+1
    block.metadata["prev_block_hash"] = get_block_hash(last_block)

    db_file = open('database/db', 'rb')
    db = pickle.load(db_file)
    db_file.close()
    db.append(block)
    db_file = open('database/db', 'wb')
    pickle.dump(db, db_file)
    db_file.close()


def mine_block(block):
    mined_block = copy.copy(block)
    last_block = get_last_block()

    mined_block.metadata["id"] = last_block.metadata["id"]+1
    mined_block.metadata["prev_block_hash"] = get_block_hash(last_block)

    hash = "1"

    while not hash.startswith("0"):
        nonce = random.randint(0, 100000)
        mined_block.metadata["nonce"] = nonce
        serialized_mined_block = pickle.dumps(block.metadata)
        hash = hashlib.sha256(serialized_mined_block).hexdigest()

    return mined_block


def spend_UTXO(input_element, new_address):
    # This function changes changes the associated_address of an element -> ~= spending
    output_element = copy.copy(input_element)
    output_element.associated_address = new_address
    return output_element


def get_block_hash(block):
    # With this function we can obtain the SHA256 hash of the block metadata
    # This is a bit a misnomer, since it does not hash the entire block
    serialized_block_metadata = pickle.dumps(block.metadata)
    block_hash = hashlib.sha256(serialized_block_metadata).hexdigest()
    return block_hash


def get_last_block():
    db_file = open('database/db', 'rb')
    db = pickle.load(db_file)
    db_file.close()
    last_block = db[-1]
    return last_block


def get_list_of_blocks():
    db_file = open('database/db', 'rb')
    db = pickle.load(db_file)
    db_file.close()
    return db

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

