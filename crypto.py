from ecdsa import SigningKey, VerifyingKey, NIST384p, BadSignatureError
from ecdsa.util import randrange_from_seed__trytryagain
import hashlib
import random
import string
import pickle


def new_seed():
    """This function creates the secret seed, using the safe random.SystemRandom function. The length of the seed
    is defined by baselen of NIST384p, as recommended by the doc of the ECDSA library."""
    seed = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase +
                                                string.digits) for _ in range(NIST384p.baselen))
    return seed


def _get_signing_key(seed):
    # Transforming the seed in int (secret_exponent) of correct range and then returning a SigningKey aka private key
    # Opens the door for HD address generation
    secret_exponent = randrange_from_seed__trytryagain(seed, NIST384p.order)
    return SigningKey.from_secret_exponent(secret_exponent, curve=NIST384p)


def get_address(seed):
    """Returns the address from the seed. It is the hexdigest of the sha256 hash of the verifying key."""
    signing_key = _get_signing_key(seed)  # aka private key
    verifying_key = signing_key.get_verifying_key()  # aka public key
    verifying_key_string = verifying_key.to_string()
    address = hashlib.sha256(pickle.dumps(verifying_key_string)).hexdigest()
    return address


def sign_transaction(seed, transaction_hash):
    """This function returns the signature of a transaction hash, signed using a SigningKey generated
    using the seed, as well as the corresponding string-VerifyingKey."""
    signing_key = _get_signing_key(seed)  # aka private key
    verifying_key = signing_key.get_verifying_key()  # aka public key
    signature = signing_key.sign(bytes(transaction_hash, encoding="ascii"))
    return signature, verifying_key.to_string()


def verify_address(address, verifying_key_string):
    """Returns True if the address corresponds to the verifying key."""
    if address == hashlib.sha256(pickle.dumps(verifying_key_string)).hexdigest():
        return True
    return False


def verify_signing(transaction_hash, signature, verifying_key_string):
    """Returns True if the transaction has been signed with the verifying key, False otherwise."""
    verifying_key = VerifyingKey.from_string(verifying_key_string, curve=NIST384p)

    try:
        verifying_key.verify(signature, bytes(transaction_hash, encoding="ascii"))
        return True
    except BadSignatureError:
        return False
