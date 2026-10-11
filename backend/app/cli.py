"""
cli.py - Soporte para comandos de consola backend vía `python -m backend.app.cli ...`.
"""

import argparse
import sys
from backend.app.services.auth_service import auth_service


def main():
    parser = argparse.ArgumentParser(description="OMRChecker Web CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    admin_parser = subparsers.add_parser("create-admin", help="Crear administrador de forma segura por consola")
    admin_parser.add_argument("--nombre", required=True, help="Nombre del administrador")
    admin_parser.add_argument("--correo", required=True, help="Correo institucional")
    admin_parser.add_argument("--clave", required=True, help="Contraseña (mínimo 6 caracteres)")

    args = parser.parse_args()

    if args.command == "create-admin":
        try:
            admin = auth_service.create_admin_cli(nombre=args.nombre, correo=args.correo, clave=args.clave)
            print(f"✓ Administrador '{admin.nombre}' ({admin.correo}) inicializado exitosamente.")
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

