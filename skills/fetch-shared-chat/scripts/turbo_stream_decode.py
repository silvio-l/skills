#!/usr/bin/env python3
"""Standalone decoder for the turbo-stream wire format (react-router / remix
single-fetch), reimplemented from the turbo-stream v2 source (MIT, remix-run).
No Node/npm dependency at runtime."""

import json

HOLE, NAN, NEG_INF, NEG_ZERO, NULL, POS_INF, UNDEFINED = -1, -2, -3, -4, -5, -6, -7
TYPE_TAGS = {"B", "D", "E", "M", "N", "P", "R", "S", "Y", "U", "Z"}


def decode_first_line(first_line: str):
    values = json.loads(first_line)
    memo = {}

    def resolve(idx):
        if idx == NULL:
            return None
        if idx == UNDEFINED:
            return None
        if idx == HOLE:
            return None
        if idx == NAN:
            return float("nan")
        if idx == NEG_INF:
            return float("-inf")
        if idx == POS_INF:
            return float("inf")
        if idx == NEG_ZERO:
            return -0.0
        if idx in memo:
            return memo[idx]

        val = values[idx]
        if val is None or not isinstance(val, (dict, list)):
            memo[idx] = val
            return val

        if isinstance(val, list):
            if val and isinstance(val[0], str) and val[0] in TYPE_TAGS:
                tag = val[0]
                if tag in ("D", "U", "B", "R", "Y"):
                    # Date/URL/BigInt/RegExp/Symbol: keep the raw literal, we
                    # only need readable text, not real JS objects.
                    memo[idx] = val[1]
                    return val[1]
                if tag == "S":
                    result = []
                    memo[idx] = result
                    for item_idx in val[1:]:
                        result.append(resolve(item_idx))
                    return result
                if tag == "M":
                    result = {}
                    memo[idx] = result
                    items = val[1:]
                    for i in range(0, len(items), 2):
                        result[resolve(items[i])] = resolve(items[i + 1])
                    return result
                if tag == "N":
                    obj = {}
                    memo[idx] = obj
                    for k, v in val[1].items():
                        obj[resolve(int(k[1:]))] = resolve(v)
                    return obj
                if tag == "P":
                    memo[idx] = None  # unresolved deferred promise
                    return memo[idx]
                if tag == "E":
                    memo[idx] = f"[Error: {val[1]}]"
                    return memo[idx]
                if tag == "Z":
                    result = resolve(val[1])
                    memo[idx] = result
                    return result
                memo[idx] = val
                return val
            # plain array: every element is itself an index reference
            result = []
            memo[idx] = result
            for item in val:
                result.append(resolve(item))
            return result

        # plain object: keys are "_<keyIndex>" -> valueIndex
        obj = {}
        memo[idx] = obj
        for k, v in val.items():
            obj[resolve(int(k[1:]))] = resolve(v)
        return obj

    return resolve(0)


if __name__ == "__main__":
    import sys

    with open(sys.argv[1], encoding="utf-8") as f:
        first_line = f.readline()
    decoded = decode_first_line(first_line)
    print(json.dumps(decoded, indent=2, ensure_ascii=False))
