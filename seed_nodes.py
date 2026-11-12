# Thêm dữ liệu node mẫu vào SQLite

import sqlite3

# 1. Ket noi Database
conn = sqlite3.connect("fire_alarm.db")
cursor = conn.cursor()

# 2. Danh sach node can luu
nodes = [
    ("NODE-01", "Nut nhan khan cap", "BUTTON", "unknown"),
    ("NODE-02", "Cam bien khoi", "SMOKE", "unknown"),
    ("NODE-03", "Coi va den canh bao", "SIREN", "unknown")
]

# 3. Them du lieu vao bang nodes
cursor.executemany("""
    INSERT OR IGNORE INTO nodes (id, name, type, status)
    VALUES (?, ?, ?, ?)
""", nodes)

# 4. Luu du lieu
conn.commit()

# 5. Kiem tra du lieu da luu
cursor.execute("SELECT * FROM nodes")
result = cursor.fetchall()

for node in result:
    print(node)

# 6. Dong ket noi
conn.close()
