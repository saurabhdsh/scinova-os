#!/usr/bin/env python3
"""Admin CLI — create users for SciNova OS."""

import argparse
import sys

from app.database import SessionLocal
from app.services.user_service import (
    CannotDeleteLastAdminError,
    CannotDeleteSelfError,
    UserNotFoundError,
    UsernameTakenError,
    create_user,
    delete_user,
)


def main():
    parser = argparse.ArgumentParser(description="SciNova OS admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user", help="Create a new user")
    create.add_argument("--username", required=True)
    create.add_argument("--password", required=True)
    create.add_argument("--role", default="scientist", choices=["admin", "scientist", "reviewer"])
    create.add_argument("--name", default=None, help="Full display name")

    delete = sub.add_parser("delete-user", help="Delete a user and their workspace data")
    delete.add_argument("--username", required=True)
    delete.add_argument("--actor-username", default="admin", help="Admin performing the delete")

    args = parser.parse_args()
    if args.command == "create-user":
        db = SessionLocal()
        try:
            user = create_user(
                db,
                username=args.username,
                password=args.password,
                role=args.role,
                full_name=args.name,
            )
        except UsernameTakenError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        finally:
            db.close()
        print("User created successfully")
        print(f"  id:       {user.id}")
        print(f"  username: {user.username}")
        print(f"  role:     {user.role}")
        print(f"  name:     {user.full_name}")
        return

    if args.command == "delete-user":
        db = SessionLocal()
        try:
            from app.models.db_models import User

            target = db.query(User).filter(User.username == args.username).first()
            actor = db.query(User).filter(User.username == args.actor_username).first()
            if not target:
                print(f"Error: user '{args.username}' not found", file=sys.stderr)
                sys.exit(1)
            if not actor:
                print(f"Error: actor '{args.actor_username}' not found", file=sys.stderr)
                sys.exit(1)
            delete_user(db, target.id, actor_user_id=actor.id)
        except (UsernameTakenError, CannotDeleteSelfError, CannotDeleteLastAdminError, UserNotFoundError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        finally:
            db.close()
        print(f"User '{args.username}' deleted successfully")


if __name__ == "__main__":
    main()
