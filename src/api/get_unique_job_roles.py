from src.core.settings import config
from pymongo import MongoClient
from typing import List, Dict
import re
from fastapi import APIRouter, HTTPException, Depends #type: ignore
from src.utils.logger import get_logger
logger = get_logger("GetUniqueJobRoles")

router = APIRouter()
def normalize_job_role(role: str) -> str:
    """
    Normalize job role by standardizing common variations.
    
    Args:
        role: Raw job role string
        
    Returns:
        Normalized job role string
    """
    if not role:
        return ""
    
    # Convert to lowercase for case-insensitive comparison
    normalized = role.lower().strip()
    
    # Standardize common abbreviations and spellings
    replacements = {
        r'\bpl\s*/\s*sql\b': 'pl/sql',
        r'\bplsql\b': 'pl/sql',
        r'\bdba\b': 'database administrator',
        r'\bfi/co\b': 'fi-co',
        r'\bfi\s*/\s*co\b': 'fi-co',
        r'\bsr\.\b': 'senior',
        r'\bsr\b': 'senior',
        r'\band\b': '&',
        r'\s+': ' ',  # Normalize multiple spaces
    }
    
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized)
    
    # Remove common prefixes/suffixes that don't change the core role
    normalized = re.sub(r'^senior\s+', '', normalized)
    normalized = re.sub(r'^lead\s+', '', normalized)
    normalized = re.sub(r'^sr\s+', '', normalized)
    
    return normalized.strip()

def get_unique_job_roles(
    mongo_uri: str = "mongodb://localhost:27017/",
    database: str = "resumes_db", 
    collection: str = "resumes"
) -> List[str]:
    """
    Get all unique job roles from MongoDB resumes collection with deduplication.
    
    Args:
        mongo_uri: MongoDB connection string
        database: Database name
        collection: Collection name
    
    Returns:
        List of unique job roles
    """
    client = MongoClient(config.mongodb_uri)
    db = client[config.mongodb_database]
    collection = db[config.mongodb_collection]
    
    try:
        unique_roles = collection.distinct("job_role")
        
        # Filter out None/empty values
        clean_roles = [role for role in unique_roles if role]
        
        # Create a mapping of normalized -> best original name
        role_mapping = {}
        for role in clean_roles:
            normalized = normalize_job_role(role)
            
            # Choose the best original name (prefer longer, more descriptive names)
            if normalized not in role_mapping:
                role_mapping[normalized] = role
            else:
                # Prefer the version with proper capitalization and spelling
                current_best = role_mapping[normalized]
                if (len(role) > len(current_best) or 
                    (role.islower() and not current_best.islower()) or
                    ('database administrator' in role.lower() and 'dba' in current_best.lower())):
                    role_mapping[normalized] = role
        
        # Get the deduplicated roles
        deduplicated_roles = sorted(list(role_mapping.values()))
        
        return deduplicated_roles
        
    except Exception as e:
        print(f"Error fetching job roles: {e}")
        return []
    finally:
        client.close()

# Alternative approach: Group similar roles
def get_grouped_job_roles(
    mongo_uri: str = "mongodb://localhost:27017/",
    database: str = "resumes_db", 
    collection: str = "resumes"
) -> dict:
    """
    Get job roles grouped by normalized categories.
    
    Returns:
        Dictionary with normalized role as key and list of variations as value
    """
    client = MongoClient(config.mongodb_uri)
    db = client[config.mongodb_database]
    collection = db[config.mongodb_collection]
    
    try:
        unique_roles = collection.distinct("job_role")
        clean_roles = [role for role in unique_roles if role]
        
        # Group roles by normalized version
        grouped_roles = {}
        for role in clean_roles:
            normalized = normalize_job_role(role)
            if normalized not in grouped_roles:
                grouped_roles[normalized] = []
            grouped_roles[normalized].append(role)
        
        # Sort groups and variations
        for key in grouped_roles:
            grouped_roles[key] = sorted(grouped_roles[key])
        
        return dict(sorted(grouped_roles.items()))
        
    except Exception as e:
        print(f"Error fetching job roles: {e}")
        return []
    finally:
        client.close()


@router.get("/get_unique_job_roles")
async def get_unique_job_roles_endpoint(data: List[str] = Depends(get_unique_job_roles)):
    return {"job_roles": data}

# Usage
if __name__ == "__main__":
    print("=== Deduplicated Job Roles ===")
    roles = get_unique_job_roles()
    print(f"Found {len(roles)} unique job roles:")
    for role in roles:
        print(f"  - {role}")
    
    print("\n=== Grouped Job Roles ===")
    grouped = get_grouped_job_roles()
    for normalized, variations in grouped.items():
        print(f"\n{normalized.upper()}:")
        for variation in variations:
            print(f"  - {variation}")