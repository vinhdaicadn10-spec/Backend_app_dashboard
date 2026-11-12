
from pymongo import MongoClient

# 1. Dia chi MongoDB Server
MONGO_URL = "mongodb://localhost:27017/"

# 2. Ket noi MongoDB
with MongoClient(
    MONGO_URL,
    serverSelectionTimeoutMS=5000
) as client:

    # 3. Kiem tra ket noi
    client.admin.command("ping")
    print("Ket noi MongoDB thanh cong!")

    # 4. Chon Database
    db = client["fire_alarm"]

    # 5. Chon Collection
    nodes_collection = db["nodes"]

    # 6. Lay danh sach node
    nodes = list(
        nodes_collection.find({}, {"_id": 0})
    )

    # 7. In ket qua
    print("Tong so node:", len(nodes))

    for node in nodes:
        print(node)
