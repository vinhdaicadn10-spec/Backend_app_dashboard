
from fastapi import APIRouter, HTTPException, status
from pymongo.errors import DuplicateKeyError

from schemas import NodeCreate, NodeUpdate
from mongo_db import nodes_collection


# Tao Router cho cac API Node
router = APIRouter(
    prefix="/api/nodes",
    tags=["Nodes"]
)


# =========================
# 1. GET - LAY DANH SACH NODE
# =========================

@router.get("")
def get_nodes():

    nodes_data = list(
        nodes_collection.find(
            {},
            {"_id": 0}
        ).sort("id", 1)
    )

    return {
        "source": "mongodb",
        "total": len(nodes_data),
        "nodes": nodes_data
    }


# =========================
# 2. GET - LAY CHI TIET NODE
# =========================

@router.get("/{node_id}")
def get_node_detail(node_id: str):

    node = nodes_collection.find_one(
        {"id": node_id},
        {"_id": 0}
    )

    if node is None:
        raise HTTPException(
            status_code=404,
            detail="Khong tim thay node"
        )

    return node


# =========================
# 3. POST - THEM NODE
# =========================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED
)
def create_node(new_node: NodeCreate):

    node = {
        "id": new_node.id,
        "name": new_node.name,
        "type": new_node.type,
        "status": "unknown"
    }

    try:
        nodes_collection.insert_one(node.copy())

    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Node ID da ton tai"
        )

    return node


# =========================
# 4. PATCH - CAP NHAT NODE
# =========================

@router.patch("/{node_id}")
def update_node(node_id: str, data: NodeUpdate):

    # Lay cac truong can cap nhat
    update_data = data.model_dump(
        exclude_unset=True,
        exclude_none=True
    )

    # Kiem tra co du lieu cap nhat khong
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="Can cung cap name hoac type"
        )

    # Cap nhat node trong MongoDB
    result = nodes_collection.update_one(
        {"id": node_id},
        {"$set": update_data}
    )

    # Kiem tra node co ton tai khong
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Khong tim thay node"
        )

    # Lay lai thong tin moi
    updated_node = nodes_collection.find_one(
        {"id": node_id},
        {"_id": 0}
    )

    return updated_node


# =========================
# 5. DELETE - XOA NODE
# =========================

@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_node(node_id: str):

    result = nodes_collection.delete_one(
        {"id": node_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Khong tim thay node"
        )
