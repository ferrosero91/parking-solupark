#!/usr/bin/env python
"""
Script para generar una SECRET_KEY segura para Django
Uso: python generate_secret_key.py
"""
from django.core.management.utils import get_random_secret_key

if __name__ == '__main__':
    secret_key = get_random_secret_key()
    print("\n" + "="*60)
    print("Nueva SECRET_KEY generada:")
    print("="*60)
    print(f"\n{secret_key}\n")
    print("="*60)
    print("\nCopia esta clave y úsala en tu archivo .env:")
    print(f"SECRET_KEY={secret_key}")
    print("="*60 + "\n")
