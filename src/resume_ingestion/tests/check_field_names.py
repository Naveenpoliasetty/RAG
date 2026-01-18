# tests/check_field_names.py
from resume_ingestion.database.mongodb_manager import MongoDBManager

def check_field_names():
    mongo = MongoDBManager()
    
    # Get one document and show all field names
    doc = mongo.collection.find_one()
    if doc:
        print("📋 ACTUAL FIELD NAMES IN DOCUMENTS:")
        for key in sorted(doc.keys()):
            value = doc[key]
            if isinstance(value, list):
                print(f"   {key}: list[{len(value)}]")
            elif isinstance(value, str):
                print(f"   {key}: str[{len(value)}]")
            else:
                print(f"   {key}: {type(value).__name__}")
    
    # Check what collections mapping expects
    from src.core.settings import config
    print("\n COLLECTIONS MAPPING IN CONFIG:")
    if hasattr(config, 'collections'):
        for key, value in config.collections.items():
            print(f"   {key} -> {value}")
    else:
        print("   No collections mapping found in config")

if __name__ == "__main__":
    check_field_names()