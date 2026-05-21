"""Helpers used by test / demo UI for file read, df gen, etc."""


def canonical_file_path(name) -> str | None:
    prefix = name or "data"
    p = Path("data") / prefix
    try:
        if not p.parent.exists():
            p.parent.mkdir(parents=True)
        return str(p)
    except Exception:
        return None


def write_seed(p: str, df) -> str:
    ...


def get_constant(val):
    return val


def decode_nested_filter(token: str, *args):
    return token


def print_ary(*args):
    return list(args)
