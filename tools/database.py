import pickle

_db_file_path = 0


def init_database(path):
    """Sets the path to the database file."""
    global _db_file_path
    if _db_file_path == 0:
        _db_file_path = path
    else:
        raise FileExistsError("Database path has already been set !")


def reinit_database():
    """Reinitializes the database."""
    global _db_file_path
    _db_file_path = 0


def read_from_db():
    """Extracts the list contained in the database file."""
    with open(_db_file_path, 'rb') as db_file:
        db = pickle.load(db_file)
    return db


def write_to_db(db):
    """Replaces the block list with a new one in the database file."""
    with open(_db_file_path, 'wb') as db_file:
        pickle.dump(db, db_file)
