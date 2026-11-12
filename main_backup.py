# Bản sao lưu code main.py cũ

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# Tao ung dung FastAPI
app = FastAPI()

# Duong dan den Database
DB_PATH = Path(__file__).resolve().parent / "fire_alarm.db"


# =========================
# 1. API TRANG CHU
# =========================

@app.get("/")
def home():
    return {
        "message": "Backend he thong bao chay dang hoat dong"
    }


# =========================
# 2. API KIEM TRA SERVER
# =========================

@app.get("/api/health")
def check_health():
    return {
        "status": "ok",
        "message": "Server dang hoat dong"
    }


# =========================
# 3. DANH SACH NODE TAM
# =========================

# Tam giu lai cho API POST va GET chi tiet
nodes = [
    {
        "id": "NODE-01",
        "name": "Nut nhan khan cap",
        "type": "BUTTON",
        "status": "unknown"
    },
    {
        "id": "NODE-02",
        "name": "Cam bien khoi",
        "type": "SMOKE",
        "status": "unknown"
    },
    {
        "id": "NODE-03",
        "name": "Coi va den canh bao",
        "type": "SIREN",
        "status": "unknown"
    }
]


# =========================
# 4. API LAY DANH SACH NODE TU SQLITE
# =========================

@app.get("/api/nodes")
def get_nodes():

    # Ket noi den Database
    conn = sqlite3.connect(DB_PATH)

    # Cho phep doc cot theo ten
    conn.row_factory = sqlite3.Row

    try:
        # Lay danh sach node tu SQLite
        cursor = conn.execute(
            "SELECT id, name, type, status FROM nodes ORDER BY id"
        )

        # Lay tat ca ket qua
        rows = cursor.fetchall()

        # Chuyen du lieu thanh Dictionary
        nodes_data = [dict(row) for row in rows]

        return {
            "source": "sqlite",
            "total": len(nodes_data),
            "nodes": nodes_data
        }

    finally:
        # Dong ket noi Database
        conn.close()


# =========================
# 5. API LAY CHI TIET NODE
# =========================


# API lay chi tiet mot node tu SQLite
@app.get("/api/nodes/{node_id}")
def get_node_detail(node_id: str):

    # 1. Ket noi den Database
    conn = sqlite3.connect(DB_PATH)

    # 2. Cho phep truy cap cot theo ten
    conn.row_factory = sqlite3.Row

    try:
        # 3. Tim node theo ID
        cursor = conn.execute(
            """
            SELECT id, name, type, status
            FROM nodes
            WHERE id = ?
            """,
            (node_id,)
        )

        # 4. Lay mot ket qua
        node = cursor.fetchone()

        # 5. Kiem tra node co ton tai khong
        if node is None:
            raise HTTPException(
                status_code=404,
                detail="Khong tim thay node"
            )

        # 6. Tra ve thong tin node
        return dict(node)

    finally:
        # 7. Dong ket noi Database
        conn.close()


# =========================
# 6. DINH NGHIA DU LIEU THEM NODE
# =========================
# Du lieu khi THEM node moi (POST)
class NodeCreate(BaseModel):
    id: str
    name: str
    type: str

# Du lieu dung de cap nhat node
class NodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)


# =========================
# 7. API THEM NODE MOI
# =========================


# API them node moi vao SQLite
@app.post("/api/nodes", status_code=status.HTTP_201_CREATED)
def create_node(new_node: NodeCreate):

    # 1. Ket noi Database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 2. Them node vao bang nodes
        conn.execute("""
            INSERT INTO nodes (id, name, type)
            VALUES (?, ?, ?)
        """, (
            new_node.id,
            new_node.name,
            new_node.type
        ))

        # 3. Luu du lieu
        conn.commit()

        # 4. Lay node vua them
        cursor = conn.execute(
            """
            SELECT id, name, type, status
            FROM nodes
            WHERE id = ?
            """,
            (new_node.id,)
        )

        node = cursor.fetchone()

        return dict(node)

    except sqlite3.IntegrityError:
        conn.rollback()

        raise HTTPException(
            status_code=409,
            detail="Node ID da ton tai"
        )

    finally:
        # 5. Dong ket noi
        conn.close()
    
# API cap nhat thong tin node
@app.patch("/api/nodes/{node_id}")
def update_node(node_id: str, update_data: NodeUpdate):

    # 1. Kiem tra co du lieu can cap nhat khong
    if update_data.name is None and update_data.type is None:
        raise HTTPException(
            status_code=400,
            detail="Can cung cap name hoac type"
        )

    # 2. Ket noi SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 3. Tim node theo ID
        cursor = conn.execute(
            "SELECT id, name, type, status FROM nodes WHERE id = ?",
            (node_id,)
        )

        node = cursor.fetchone()

        # 4. Kiem tra node co ton tai khong
        if node is None:
            raise HTTPException(
                status_code=404,
                detail="Khong tim thay node"
            )

        # 5. Lay gia tri moi hoac giu gia tri cu
        new_name = (
            update_data.name
            if update_data.name is not None
            else node["name"]
        )

        new_type = (
            update_data.type
            if update_data.type is not None
            else node["type"]
        )

        # 6. Cap nhat Database
        conn.execute(
            """
            UPDATE nodes
            SET name = ?, type = ?
            WHERE id = ?
            """,
            (new_name, new_type, node_id)
        )

        # 7. Luu thay doi
        conn.commit()

        # 8. Doc lai node vua cap nhat
        cursor = conn.execute(
            "SELECT id, name, type, status FROM nodes WHERE id = ?",
            (node_id,)
        )

        updated_node = cursor.fetchone()

        return dict(updated_node)

    finally:
        # 9. Dong ket noi
        conn.close()

# =========================
# API XOA NODE KHOI SQLITE
# =========================

@app.delete(
    "/api/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_node(node_id: str):

    # 1. Ket noi Database
    conn = sqlite3.connect(DB_PATH)

    try:
        # 2. Xoa node theo ID
        cursor = conn.execute(
            "DELETE FROM nodes WHERE id = ?",
            (node_id,)
        )

        # 3. Kiem tra co node nao bi xoa khong
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Khong tim thay node"
            )

        # 4. Luu thay doi
        conn.commit()

    finally:
        # 5. Dong ket noi
        conn.close()

    
