# -*- coding: utf-8 -*-
"""
Template tags para verificar roles y permisos de usuarios
"""

from django import template

register = template.Library()


@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Verifica si el usuario pertenece a un grupo específico
    Uso: {% if user|has_group:"Admin" %}
    """
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter(name='is_admin')
def is_admin(user):
    """
    Verifica si el usuario es administrador
    Uso: {% if user|is_admin %}
    """
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser or 
        user.groups.filter(name__in=['Admin', 'Administrador']).exists() or 
        user.is_staff
    )


@register.filter(name='is_cajero')
def is_cajero(user):
    """
    Verifica si el usuario es cajero
    Uso: {% if user|is_cajero %}
    """
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Cajero').exists()


@register.filter(name='is_operador')
def is_operador(user):
    """
    Verifica si el usuario es operador
    Uso: {% if user|is_operador %}
    """
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Operador').exists()


@register.filter(name='can_access_admin')
def can_access_admin(user):
    """
    Verifica si el usuario puede acceder a funciones administrativas
    """
    if not user or not user.is_authenticated:
        return False
    return is_admin(user)


@register.filter(name='can_access_reports')
def can_access_reports(user):
    """
    Verifica si el usuario puede acceder a reportes
    """
    if not user or not user.is_authenticated:
        return False
    return is_admin(user) or is_cajero(user)


@register.filter(name='can_access_cash_register')
def can_access_cash_register(user):
    """
    Verifica si el usuario puede acceder al cuadre de caja
    """
    if not user or not user.is_authenticated:
        return False
    return is_admin(user) or is_cajero(user)
