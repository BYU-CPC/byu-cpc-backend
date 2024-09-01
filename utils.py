import hashlib


def get_hash_table_index(id, mod=10):
    return int(hashlib.md5(id.encode()).hexdigest(), 16) % mod
