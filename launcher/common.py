from argparse import ArgumentTypeError
from typing import Tuple

folder_to_install: Tuple[str] = ('appdata', 'db', 'gamedata')
"Folder to lookout for GAMMA mods installation"

anomaly_arg = {
    "--anomaly": {
        "help": "Path to ANOMALY directory",
        "required": True,
        "type": str
    }
}
"Common arg(s) for Anomaly commands"

gamma_arg = {
    "--gamma": {
        "help": "Path to GAMMA directory",
        "required": True,
        "type": str
    }
}
"Common arg(s) for GAMMA commands"

cache_dir_arg = {
    "--cache-directory": {
        "help": "Path to cache directory",
        "type": str,
        "dest": "cache_path"
    }
}
"Common arg(s) for cache directory function"


def parse_duration(value: str) -> int:
    "Parse a duration like 30s, 10m, 1h, or plain seconds."
    value = value.strip().lower()
    if not value:
        raise ArgumentTypeError("duration cannot be empty")

    suffix = value[-1]
    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
    }.get(suffix)

    number = value[:-1] if multiplier else value
    multiplier = multiplier or 1

    try:
        seconds = int(number)
    except ValueError as e:
        raise ArgumentTypeError(f"invalid duration: {value}") from e

    if seconds <= 0:
        raise ArgumentTypeError("duration must be greater than zero")

    return seconds * multiplier
