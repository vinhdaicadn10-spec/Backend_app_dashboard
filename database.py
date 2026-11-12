# Tạo bảng nodes trong SQLite

import sqlite3

# Ket noi den Database
conn = sqlite3.connect("fire_alarm.db")

# Tao doi tuong cursor
cursor = conn.cursor()

# Tao bang nodes
cursor.execute("""
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown'
)
""")

# Luu thay doi
conn.commit()

# Dong ket noi
conn.close()

print("Da tao Database thanh cong!")
