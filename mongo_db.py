
from pymongo import MongoClient

# Dia chi MongoDB
MONGO_URL = "mongodb://localhost:27017/"

# Ket noi MongoDB
client = MongoClient(
    MONGO_URL,
    serverSelectionTimeoutMS=5000,
    tz_aware=True
)

# Chon Database
db = client["fire_alarm"]

# Collection quan ly Node
nodes_collection = db["nodes"]

# Collection quan ly Gateway
gateways_collection = db["gateways"]

# smoke_readings là collection dùng để lưu các lần đo của cảm biến khói.
smoke_readings_collection = db["smoke_readings"]