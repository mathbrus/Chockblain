import pickle

db_file_path = 0


def init_database(path):
    global db_file_path
    if db_file_path == 0:
        db_file_path = path
    else:
        raise RuntimeError("Database path has already been set !")


def read_from_db():
    try:
        db_file = open(db_file_path, 'rb')
        db = pickle.load(db_file)
        db_file.close()
        return db
    except ValueError:
        print("Database not defined.")


def write_to_db(db):
    try:
        db_file = open(db_file_path, 'wb')
        pickle.dump(db, db_file)
        db_file.close()
    except ValueError:
        print("Database not defined.")
