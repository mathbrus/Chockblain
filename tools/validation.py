from tools import crypto, api, exceptions
import hashlib
import pickle


def _is_spendable(tx_hash, position):
    """Controls whether the input can be spent. The tx_hash corresponds to the previous transaction
    from which we want to spend the output."""
    # Returns true if we can spend the input, raises corresponding exceptions otherwise
    # We test two things : Does the input exist, and is the reference to it unique ?

    # Does the input exist as output of another transaction ? To do that we try to find the amount of the input/output

    output = api.get_amount_from_input(tx_hash, position)  # See corresponding exceptions

    # Is the reference unique ?
    nb_of_matches = 0

    list_of_blocks = api.get_database()
    for b in list_of_blocks[1:]:
        for t in b.block_content:
            for current_tx_hash, current_position in t.internals["dict_of_inputs"].items():
                if (current_tx_hash, current_position) == (tx_hash, position):
                    nb_of_matches += 1

    # TODO : implement double-spend check within same block

    if nb_of_matches > 0:
        raise exceptions.ValidationError("Reference to an already spend output !")

    return True


def _has_valid_signature(tx):
    """Controls whether the signature of the block is valid. Wrapper function that allows for passing only
    the transaction as arguments, as opposed to the crypto.verify_signing"""
    # Returns true if the signature is valid, raises ValidationError otherwise.

    if crypto.verify_signing(tx.txhash, tx.signature, tx.verifying_key):
        return True
    else:
        raise exceptions.ValidationError("Invalid Signature detected in transaction with hash {}.".format(tx.txhash))


def _is_owned(tx_hash, position, verifying_key):
    """Controls whether the signature of the block proves ownership of the inputs. The tx_hash corresponds
    to the previous transaction from which we want to spend the output."""
    # Returns true if the signature corresponds, raises corresponding exceptions otherwise.

    previous_tx = api.get_transaction_by_txhash(tx_hash)  # See corresponding exceptions

    try:
        address_of_output = list(previous_tx.internals["dict_of_outputs"].keys())[position]
    except IndexError:
        raise exceptions.ValidationError("Incorrect position of output when verifying ownership of transaction "
                                         "with hash {}.".format(tx_hash))

    return crypto.verify_address(address_of_output, verifying_key)


def _has_correct_hash(tx):
    """Checks if the txhash has not been tampered with."""
    if tx.txhash == get_tx_hash(tx):
        return True
    raise exceptions.ValidationError("Invalid transaction hash : {} does not correspond to true hash."
                                     .format(tx.txhash))


def _validate_transactions_of_block(block):
    """Validates the transactions in the given block, using 4 checking mechanisms."""

    # The first block is by definition always valid.
    if block.metadata["id"] == 1:
        print("First block is always true.")
        return True

    # There are 5 sources in invalidity for a tx :
    # [1] The hash has been modified and does not correspond anymore
    # [2] The signature of the block does not correspond to its verifying key
    # [3] The outputs we are trying to spend are not spendable
    # [4] The verifying key does not correspond to the addresses that we are trying to spend from
    # [5] The amounts do not match

    block_tx_no = 0

    for t in block.block_content:

        # We control the tx_hash: [check 1]
        _has_correct_hash(t)

        # We control the signature [check 2]
        _has_valid_signature(t)

        # For each transaction in the block, we keep record of the input and output amounts
        input_amount = 0
        output_amount = 0

        # Remember : inputs of a transaction are of format (hash of tx where we find the spendable output, its position)
        tx_input_no = 0
        for tx_hash, position in t.internals["dict_of_inputs"].items():

            # For each input element of a given tx, we check if it is spendable [check 3]
            _is_spendable(tx_hash, position)

            input_amount += api.get_amount_from_input(tx_hash, position)
            tx_input_no += 1

            # We control the ownership [check 4]. We can trust the verifying key since we are after [2] and the
            # existence of tx and input since we are after [3]
            _is_owned(tx_hash, position, t.verifying_key)

        # Outputs of a transaction are of format (destination address, amount)
        for amount in t.internals["dict_of_outputs"].values():
            output_amount += amount

        # Last thing to check : does the input total match the output total ? [check 5]
        if input_amount != output_amount:
            raise exceptions.ValidationError("Unbalanced input and output amounts in transaction with hash {} "
                                             "detected. Inputs : {}, Outputs : {}."
                                             .format(t.txhash, input_amount, output_amount))

        block_tx_no += 1

    # Now we are sure the block is valid
    return True


def get_block_hash(block):
    """Returns the "hash of a block", which is in fact the hash of the metadata of the block."""
    # With this function we can obtain the SHA256 hash
    serialized_block_metadata = pickle.dumps(block.metadata)
    block_hash = hashlib.sha256(serialized_block_metadata).hexdigest()
    return block_hash


def get_tx_hash(tx):
    """Returns the "hash of a transaction", which is in fact the hash of the internals of the block."""
    # With this function we can obtain the SHA256 hash
    serialized_tx_internals = pickle.dumps(tx.internals)
    tx_hash = hashlib.sha256(serialized_tx_internals).hexdigest()
    return tx_hash


def validate_block(block):
    """This functions can be used to validate a block. In addition to the transactions verification, it also
    checks that the block has the correct structure."""
    # TODO : implementation
    return _validate_transactions_of_block(block)
