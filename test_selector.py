"""Genera un setlist de prueba y lo imprime."""
from src.selector import generate_setlist, print_setlist

# Set de 30 minutos, semilla aleatoria, pico de energia al 65% del set
setlist = generate_setlist(duration_minutes=30)
print_setlist(setlist)