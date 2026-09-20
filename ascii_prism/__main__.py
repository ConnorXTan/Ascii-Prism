"""`python -m ascii_prism` serves the website. `python -m ascii_prism desktop`
runs the native OpenCV window instead."""

import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "desktop":
        from .app import main as desktop_main

        return desktop_main(argv[1:])
    if argv and argv[0] == "serve":
        argv = argv[1:]
    from .server import main as serve_main

    return serve_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
