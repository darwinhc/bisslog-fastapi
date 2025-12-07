"""Extract path variables from a FastAPI path pattern."""
import re


from typing import List

def extract_path_vars(path: str) -> List[str]:
    """Extract {vars} from a FastAPI path pattern."""
    return re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", path or "")
