"""Inspecciona rapidamente la biblioteca analizada."""
import sqlite3

conn = sqlite3.connect("data/library.db")
conn.row_factory = sqlite3.Row

def print_rows(title, query):
    print(f"\n=== {title} ===")
    for r in conn.execute(query):
        t = (r["title"] or "")[:40]
        artist = (r["artist"] or "?")[:15]
        print(f"{t:40s} | {artist:15s} | {r['bpm']:6.1f} BPM | {r['camelot']:5s} | energy={r['energy']:.2f} | dance={r['danceability']:.2f}")

# Resumen general
total = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
avg_bpm = conn.execute("SELECT AVG(bpm) FROM tracks").fetchone()[0]
print(f"\nTotal tracks: {total}")
print(f"BPM promedio: {avg_bpm:.1f}")

# Distribucion de Camelot
print("\n=== Distribucion Camelot ===")
for r in conn.execute("SELECT camelot, COUNT(*) as n FROM tracks GROUP BY camelot ORDER BY n DESC"):
    print(f"  {r['camelot']:5s} -> {r['n']} tracks")

# 10 mas lentas
print_rows("10 mas lentas", "SELECT * FROM tracks ORDER BY bpm ASC LIMIT 10")

# 10 mas rapidas
print_rows("10 mas rapidas", "SELECT * FROM tracks ORDER BY bpm DESC LIMIT 10")

# 10 con mas energia
print_rows("10 con mas energia", "SELECT * FROM tracks ORDER BY energy DESC LIMIT 10")

conn.close()