import pandas as pd
from tools import classes, crypto, database, exceptions, validation


def init_lightnode_api():
    global stack_of_used_inputs
    global last_block_height

    # When importing the lightnode_api, we keep the local state of the ledger after the last block.
    stack_of_used_inputs = []  # An UTXO is an output of a tx that is not yet used as input in another tx.
    last_block_height = database.read_from_db()[-1].metadata["id"]


def get_database():
    """Returns the whole blockchain as a list of blocks, and updates the local state in case of a new block."""
    global stack_of_used_inputs
    global last_block_height

    db = database.read_from_db()

    if last_block_height < db[-1].metadata["id"]:  # A new block has been added
        last_block_height = db[-1].metadata["id"]
        stack_of_used_inputs = []  # We empty it since everything now appears in the blockchain

    return db


def get_transaction_by_txhash(tx_hash):
    """Returns the transaction using its hash, raises a APIError otherwise."""

    db = get_database()

    # We loop through the blocks
    for b in db:
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
    db = get_database()

    # To construct a balance, we need the total output that point to it minus the inputs that come from it
    balance_in = 0
    balance_out = 0

    # We loop through the blocks.
    for b in db:
        # For each block
        for t in b.block_content:

            # For each transaction
            position_of_output = 0
            stack_of_used_inputs_for_address = []
            for addr in t.internals["dict_of_outputs"].keys():
                if addr == address:
                    balance_in += t.internals["dict_of_outputs"][addr]  # The amount in
                    stack_of_used_inputs_for_address.append((t.txhash, position_of_output))
                    position_of_output += 1

            for tx_hash, pos in t.internals["dict_of_inputs"].items():
                if (tx_hash, pos) in stack_of_used_inputs\
                        and (tx_hash, pos) in stack_of_used_inputs_for_address:  # One of the inputs is not valid anymore
                    balance_out += get_amount_from_input(tx_hash, pos)

            if crypto.verify_address(address, t.verifying_key):
                # The transaction has been signed with the key corresponding to the address : it is an output
                for output_element in t.internals["dict_of_outputs"].values():
                    balance_out += output_element

    return balance_in-balance_out


def get_valid_inputs_from_address(address):
    """Returns the list of valid inputs that can be used by an address in a transaction"""
    db = get_database()

    # We want a list of the transaction outputs that are still valid, in input form
    all_inputs = []
    used_inputs = []

    # We loop through the blocks.
    for b in db:
        # For each block
        for t in b.block_content:

            # For each transaction
            output_pos = 0
            for addr_to_compare in t.internals["dict_of_outputs"].keys():
                # If an output points to our address, we keep record of it
                if addr_to_compare == address:
                    all_inputs.append((t.txhash, output_pos))
                output_pos += 1

            if crypto.verify_address(address, t.verifying_key):
                # The transaction has been signed with the key corresponding to the address : we are burning inputs
                # We keep record of all the inputs (all of them come from our address)
                for tx_hash, pos in t.internals["dict_of_inputs"].items():
                    used_inputs.append((tx_hash, pos))

    # We now have both lists completely, we just need the difference = the valid inputs
    # We also make sure the stack of previously used inputs is taken into account
    valid_inputs_list = list(set(all_inputs) - set(used_inputs) - set(stack_of_used_inputs))

    return valid_inputs_list


def create_transaction(from_address, to_address, amount=0):
    """Creates an unsigned transaction. If amount=0, it spends everything.
    If not everything is spend, returns the remainder to the sender."""
    global stack_of_used_inputs
    valid_inputs_list = get_valid_inputs_from_address(from_address)
    balance = get_balance_from_address(from_address)

    dict_of_inputs = {}
    dict_of_outputs = {}

    if amount == 0:  # We spend everything
        for inpt in valid_inputs_list:
            dict_of_inputs[inpt[0]] = inpt[1]
        dict_of_outputs[to_address] = amount

    if balance == amount:  # We spend everything
        for inpt in valid_inputs_list:
            dict_of_inputs[inpt[0]] = inpt[1]
        dict_of_outputs[to_address] = amount

    if balance > amount:  # We return part of the amount to the sender
        for inpt in valid_inputs_list:
            dict_of_inputs[inpt[0]] = inpt[1]  # Even when not spending all the balance, we burn all the inputs
        dict_of_outputs[to_address] = amount
        dict_of_outputs[from_address] = balance - amount

    if balance < amount:
        raise exceptions.APIError("Balance of address not sufficient to create transaction")

    for txhash, pos in dict_of_inputs.items():  # We update the local state of the ledger to include the new tx.
        stack_of_used_inputs.append((txhash, pos))

    if not dict_of_inputs:
        raise exceptions.APIError("Trying to create a transaction with no inputs.")

    return classes.Transaction(dict_of_inputs, dict_of_outputs)


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