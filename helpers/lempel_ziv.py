from math import ceil, floor

ASCII_TO_INT: dict = {i.to_bytes(1, "big"): i for i in range(256)}
INT_TO_ASCII: dict = {i: b for b, i in ASCII_TO_INT.items()}


def compress(data: bytes | str) -> bytes:
    if isinstance(data, str):
        data = data.encode()
    keys: dict[bytes, int] = ASCII_TO_INT.copy()
    n_keys: int = 256
    compressed: list[int] = []
    start: int = 0
    n_data: int = len(data) + 1
    while True:
        if n_keys >= 512:
            keys = ASCII_TO_INT.copy()
            n_keys = 256
        for i in range(1, n_data - start):
            w: bytes = data[start : start + i]
            if w not in keys:
                compressed.append(keys[w[:-1]])
                keys[w] = n_keys
                start += i - 1
                n_keys += 1
                break
        else:
            compressed.append(keys[w]) # type: ignore[reportPossiblyUnboundVariable]
            break
    bits: str = "".join([bin(i)[2:].zfill(9) for i in compressed])
    return int(bits, 2).to_bytes(ceil(len(bits) / 8), "big")


def decompress(data: bytes | str) -> bytes:
    if isinstance(data, str):
        data = data.encode()
    keys: dict[int, bytes] = INT_TO_ASCII.copy()
    bits: str = bin(int.from_bytes(data, "big"))[2:].zfill(len(data) * 8)
    n_extended_bytes: int = floor(len(bits) / 9)
    bits: str = bits[-n_extended_bytes * 9 :]
    data_list: list[int] = [
        int(bits[i * 9 : (i + 1) * 9], 2) for i in range(n_extended_bytes)
    ]
    previous = keys[data_list[0]]
    uncompressed: list[bytes] = [previous]
    n_keys: int = 256
    for i in data_list[1:]:
        if n_keys >= 512:
            keys = INT_TO_ASCII.copy()
            n_keys = 256
        try:
            current = keys[i]
        except KeyError:
            current = previous + previous[:1]
        uncompressed.append(current)
        keys[n_keys] = previous + current[:1]
        previous = current
        n_keys += 1
    return b"".join(uncompressed)
