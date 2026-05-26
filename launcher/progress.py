from sys import stderr
from tqdm import tqdm


def progress_bar(desc: str, **kwargs):
    is_tty = stderr.isatty()
    if not is_tty:
        print(f"[*] {desc}")

    return tqdm(
        desc=desc,
        dynamic_ncols=True,
        ascii=True,
        disable=not is_tty,
        **kwargs,
    )
