import classes
import copy
import hashlib
import pandas as pd
import pickle
import random


db_file_path = None


def init_database(path):
    global db_file_path
    if db_file_path is None:
        db_file_path = path
    else:
        raise RuntimeError("Database path has already been set !")


def create_genesis_block():
    genesis_block = classes.GenesisBlock()
    db_file = open(db_file_path, 'wb')
    db = [genesis_block]
    pickle.dump(db, db_file)
    db_file.close()
    return genesis_block


def add_block_to_db(block):
    last_block = get_last_block()

    block.metadata["id"] = last_block.metadata["id"]+1
    block.metadata["prev_block_hash"] = get_block_hash(last_block)

    db_file = open(db_file_path, 'rb')
    db = pickle.load(db_file)
    db_file.close()
    db.append(block)
    db_file = open(db_file_path, 'wb')
    pickle.dump(db, db_file)
    db_file.close()


def mine_block(block):
    mined_block = copy.copy(block)
    last_block = get_last_block()

    mined_block.metadata["id"] = last_block.metadata["id"]+1
    mined_block.metadata["prev_block_hash"] = get_block_hash(last_block)

    hash_candidate = "1"

    while not hash_candidate.startswith("0"):
        nonce = random.randint(0, 100000)
        mined_block.metadata["nonce"] = nonce
        serialized_mined_block = pickle.dumps(block.metadata)
        hash_candidate = hashlib.sha256(serialized_mined_block).hexdigest()

    return mined_block


def get_block_hash(block):
    # With this function we can obtain the SHA256 hash of the block metadata
    # This is a bit a misnomer, since it does not hash the entire block
    serialized_block_metadata = pickle.dumps(block.metadata)
    block_hash = hashlib.sha256(serialized_block_metadata).hexdigest()
    return block_hash


def get_last_block():
    # Returns last block of the chain
    db_file = open(db_file_path, 'rb')
    db = pickle.load(db_file)
    db_file.close()
    last_block = db[-1]
    return last_block


def get_list_of_blocks():
    # Returns the whole blockchain as a list of blocks
    db_file = open(db_file_path, 'rb')
    db = pickle.load(db_file)
    db_file.close()
    return db


def get_transaction_by_txhash(tx_hash):
    # Returns the transaction with the hash = tx_hash, False otherwise
    db_file = open(db_file_path, 'rb')
    db = pickle.load(db_file)
    db_file.close()

    # We loop through the blocks by skipping the genesis block
    for b in db[1:]:
        # For each block
        for t in b.block_content:
            # For each transaction
            if t.txhash == tx_hash:
                return t
    return False


def is_spendable(tx_hash, position):
    # Returns true if we can spend the input, false otherwise
    # We test two things : Does the input exist, and is the reference to it unique ?

    # Does the input exist as output of another transaction ?
    tx = get_transaction_by_txhash(tx_hash)
    if tx is not False:
        # We have found the transaction
        try:
            list(tx.internals["dict_of_outputs"].items())[position]
        except IndexError:
            print("Reference to an unexisting output.")
            return False

    # Is the reference unique ?
    nb_of_matches = 0

    list_of_blocks = get_list_of_blocks()
    for b in list_of_blocks[1:]:
        for t in b.block_content:
            for current_tx_hash, current_position in t.internals["dict_of_inputs"].items():
                if (current_tx_hash, current_position) == (tx_hash, position):
                    nb_of_matches += 1

    if nb_of_matches > 0:
        return False

    return True


def get_amount_from_input(tx_hash, position):
    # Returns either the amount or False if not found

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


def validate_transactions_of_block(block):
    # Validates the transactions in the block given

    # There are two sources in invalidity for a tx : inputs are not spendable, or the amount is not correct

    block_tx_no = 0

    for t in block.block_content:

        # For each transaction in the block, we keep record of the input and output amounts
        input_amount = 0
        output_amount = 0

        # Remember : inputs of a transaction are of format (hash of tx where we find the spendable output, its position)
        tx_input_no = 0
        for tx_hash, position in t.internals["dict_of_inputs"].items():

            # For each input element of a given tx, we check if is_spendable returns True.
            if is_spendable(tx_hash, position):
                input_amount += get_amount_from_input(tx_hash, position)
                tx_input_no += 1
            else:
                print("Inconsistency in input no. {} of transaction no. {} detected.".format(tx_input_no, block_tx_no))
                return False

        # Outputs of a transaction are of format (destination address, amount)
        for amount in t.internals["dict_of_outputs"].values():
            output_amount += amount

        # Last thing to check : does the input total match the output total ?
        if input_amount != output_amount:
            print("Unbalanced input and output amounts in transaction no. {} detected. Inputs : {}, Outputs : {}."
                  .format(block_tx_no, input_amount, output_amount))
            return False

        block_tx_no += 1

    # Now we are sure the block is valid
    print("Valid block !")
    return True


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

