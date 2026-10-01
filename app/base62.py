# Base62 Alphabet: 10 digits + 26 lowercase + 26 uppercase = 62 characters
# Index mapping:
#   0-9   -> '0'-'9'
#   10-35 -> 'a'-'z'
#   36-61 -> 'A'-'Z'
BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(BASE62_ALPHABET)  # 62

def encode(num: int) -> str:
    """
    Convert a non-negative integer into a Base62 string.
    How it works:
      Repeatedly divide `num` by 62:
      - The remainder becomes the current character (from right to left).
      - The quotient is carried over to the next iteration.
      - Finally, reverse the characters to get the standard left-to-right order.
    Example:
      12345 -> '3d7'
    """
    if num < 0:
        raise ValueError("Number must be non-negative")
    if num == 0:
        return BASE62_ALPHABET[0]
    digits = []
    while num > 0:
        num, rem = divmod(num, BASE)
        digits.append(BASE62_ALPHABET[rem])
    return "".join(reversed(digits))


def decode(code: str) -> int:
    """
    Convert a Base62 string back into its original integer.
    How it works:
      For each character:
      - Find its position/index (0 to 61) in the alphabet.
      - Multiply the accumulated number by 62 and add the new index.
    Example:
      '3d7' -> 12345
    """
    if not code:
        raise ValueError("Code cannot be empty")
    num = 0
    for char in code:
        idx = BASE62_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid Base62 character: '{char}'")
        num = num * BASE + idx
    return num

