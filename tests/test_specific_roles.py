
import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.retriever.get_ids import ResumeIdsRetriever

def test_specific_roles():
    roles_to_test = [
        "oracle cloud procurement sme", 
        "oracle cloud hcm consultant", 
        "oracle consultant"
    ]
    
    print(f"--- Testing Specific Job Roles: {roles_to_test} ---")
    retriever = ResumeIdsRetriever()
    
    # Test all together
    print(f"\nQuerying for ALL roles together...")
    ids = retriever.get_resume_ids_by_job_roles(roles_to_test)
    print(f"Total IDs retrieved: {len(ids)}")
    
    # Test individually to see breakdown
    print(f"\nBreakdown by individual role query:")
    for role in roles_to_test:
        ids = retriever.get_resume_ids_by_job_roles([role])
        print(f"  Role: '{role}' -> Retrieved {len(ids)} IDs")

if __name__ == "__main__":
    test_specific_roles()
