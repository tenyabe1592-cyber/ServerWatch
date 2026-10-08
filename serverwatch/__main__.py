from __future__ import annotations

import argparse
import getpass

from .auth import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="ServerWatch maintenance commands")
    parser.add_argument("command", choices=["hash-password"])
    args = parser.parse_args()
    if args.command == "hash-password":
        password = getpass.getpass("Password (minimum 14 characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("passwords do not match")
        print(hash_password(password))


if __name__ == "__main__":
    main()

