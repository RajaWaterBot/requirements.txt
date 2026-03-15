# database.py
import pymongo
import certifi
import config

client = pymongo.MongoClient(config.MONGO_URI, tlsCAFile=certifi.where())
db = client["BotDatabase"]
users_col = db["users"]
keys_col = db["keys"]
txn_col = db["transactions"]

def add_user(user_id, referred_by=None):
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({
            "user_id": user_id, "balance": 0.0, "total_recharge": 0.0,
            "total_refer": 0, "refer_income": 0.0, "referred_by": referred_by,
            "wallet": None, "is_banned": False
        })
        if referred_by:
            users_col.update_one({"user_id": referred_by}, {"$inc": {"total_refer": 1}})
        return True
    return False

def get_user(user_id):
    return users_col.find_one({"user_id": user_id})

def update_balance(user_id, amount, recharge=False):
    update_data = {"$inc": {"balance": amount}}
    if recharge and amount > 0:
        update_data["$inc"]["total_recharge"] = amount
    users_col.update_one({"user_id": user_id}, update_data)

def add_refer_income(user_id, amount):
    users_col.update_one({"user_id": user_id}, {"$inc": {"balance": amount, "refer_income": amount}})

def set_wallet(user_id, wallet):
    users_col.update_one({"user_id": user_id}, {"$set": {"wallet": wallet}})

# Key Management
def add_key(product, key_val):
    keys_col.insert_one({"product": product, "key": key_val, "status": "available"})

def get_and_use_key(product):
    key = keys_col.find_one_and_update(
        {"product": product, "status": "available"},
        {"$set": {"status": "used"}}
    )
    return key["key"] if key else None

def get_key_stock():
    stock = {}
    for p in config.PRODUCTS.keys():
        stock[p] = keys_col.count_documents({"product": p, "status": "available"})
    return stock
