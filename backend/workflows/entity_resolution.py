import difflib
from typing import List, Dict, Any, Tuple
from datetime import datetime
from backend.storage.workflow_store import WorkflowStore

class EntityResolutionEngine:
    """
    Groups random document uploads into unified Employee Profiles
    using fuzzy matching on identifying features (FullName, DOB).
    """

    def __init__(self, store: WorkflowStore):
        self.store = store

    def _normalize_string(self, s: str) -> str:
        if not s:
            return ""
        return str(s).strip().lower()

    def _similarity(self, a: str, b: str) -> float:
        """Returns string similarity ratio between 0.0 and 1.0"""
        return difflib.SequenceMatcher(None, self._normalize_string(a), self._normalize_string(b)).ratio()

    def resolve_and_group(self, account_id: str, documents_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes a list of document extractions and groups them into profiles.
        documents_data format expected:
        [
            {"workflow_id": "...", "extracted_name": "John Doe", "extracted_dob": "15-08-1994", "type": "aadhaar"},
            ...
        ]
        """
        profiles = [] # List of {"profile_id": str, "name": str, "dob": str, "documents": list}
        
        for doc in documents_data:
            name = doc.get("extracted_name", "")
            dob = doc.get("extracted_dob", "")
            workflow_id = doc.get("workflow_id")
            
            # Skip if no identifying information is present
            if not name:
                continue

            matched_profile = None
            for profile in profiles:
                # Require DOB match if both have DOBs, otherwise rely on high name similarity
                dob_match = False
                if dob and profile["dob"] and self._normalize_string(dob) == self._normalize_string(profile["dob"]):
                    dob_match = True
                
                name_sim = self._similarity(name, profile["name"])
                
                if dob_match and name_sim > 0.6:
                    matched_profile = profile
                    break
                elif not profile["dob"] and not dob and name_sim > 0.85:
                    matched_profile = profile
                    break

            if matched_profile:
                matched_profile["documents"].append(doc)
                # Upgrade name to longest version if similar (e.g. "J. Doe" -> "John Doe")
                if len(name) > len(matched_profile["name"]):
                    matched_profile["name"] = name
                # Add dob if newly discovered
                if dob and not matched_profile["dob"]:
                    matched_profile["dob"] = dob
            else:
                # Create a new profile cluster
                profiles.append({
                    "profile_id": None, # Will be assigned by DB
                    "name": name,
                    "dob": dob,
                    "documents": [doc]
                })

        # Persist grouped profiles to DB
        results = []
        for p in profiles:
            pid = self.store.create_employee_profile(
                account_id=account_id,
                full_name=p["name"],
                dob=p["dob"]
            )
            p["profile_id"] = pid
            
            # Update workflows with their new profile_id
            for d in p["documents"]:
                workflow_data = self.store.get_workflow(d["workflow_id"])
                if workflow_data:
                    workflow_data["profile_id"] = pid
                    self.store.persist_workflow(d["workflow_id"], workflow_data)

            results.append(p)
            
        return results
