
from mongo_db import nodes_collection, gateways_collection

# Unique Index cho Node
nodes_collection.create_index(
    "id",
    unique=True,
    name="unique_node_id"
)

# Unique Index cho Gateway
gateways_collection.create_index(
    "gateway_id",
    unique=True,
    name="unique_gateway_id"
)

print("Da tao Index cho Node va Gateway!")
