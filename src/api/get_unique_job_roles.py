from src.core.settings import config
from pymongo import MongoClient
from typing import List
from fastapi import APIRouter, Depends #type: ignore
from src.utils.logger import get_pipeline_logger
import json

logger = get_pipeline_logger(__name__, "GetUniqueJobRoles")

router = APIRouter()

def get_unique_job_roles(
    collection: str = "resumes"
) -> List[str]:
    """
    Get all unique job roles from MongoDB resumes collection.
    Since job roles are normalized at ingestion time, we can directly use them.
    
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
        # Get distinct job roles (already normalized at ingestion)
        unique_roles = collection.distinct("job_role")
        
        # Filter out None/empty values
        clean_roles = [role for role in unique_roles if role and role.strip()]
        
        # Return sorted unique roles
        return sorted(clean_roles)
        
    except Exception as e:
        logger.error(f"Error fetching job roles: {e}")
        return []
    finally:
        client.close()

# Alternative approach: Group similar roles
def get_grouped_job_roles( 
    collection: str = "resumes"
) -> dict:
    """
    Get job roles grouped by normalized categories.
    Since job roles are already normalized at ingestion, grouping is straightforward.
    
    Returns:
        Dictionary with normalized role as key and list of variations as value
    """
    client = MongoClient(config.mongodb_uri)
    db = client[config.mongodb_database]
    collection = db[config.mongodb_collection]
    
    try:
        # Get distinct job roles (already normalized at ingestion)
        unique_roles = collection.distinct("job_role")
        
        # Filter out None/empty values
        clean_roles = [role for role in unique_roles if role and role.strip()]
        
        # Since roles are already normalized, each role is its own group
        # This maintains the same API structure but with simplified logic
        grouped_roles = {}
        for role in clean_roles:
            # Use the role itself as the key since it's already normalized
            if role not in grouped_roles:
                grouped_roles[role] = []
            grouped_roles[role].append(role)
        
        # Sort groups
        return dict(sorted(grouped_roles.items()))
        
    except Exception as e:
        logger.error(f"Error fetching job roles: {e}")
        return {}
    finally:
        client.close()


@router.get("/get_job_roles")
async def get_job_roles_endpoint(data: List[str] = Depends(get_unique_job_roles)):
    return {"job_roles": data}

# Usage
if __name__ == "__main__":
    logger.info("=== Deduplicated Job Roles ===")
    roles = get_unique_job_roles()
    logger.info(f"Found {len(roles)} unique job roles:")
    for role in roles:
        logger.info(f"  - {role}")
    
    with open("job_roles.json", "w") as f:
        json.dump(roles, f, indent=4)
    
    logger.info("\n=== Grouped Job Roles ===")
    grouped = get_grouped_job_roles()
    for normalized, variations in grouped.items():
        logger.info(f"\n{normalized.upper()}:")
        for variation in variations:
            logger.info(f"  - {variation}")