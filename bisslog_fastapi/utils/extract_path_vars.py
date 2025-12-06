"""Extract path variables from a FastAPI path pattern."""
import re


def extract_path_vars(path: str) -> list[str]:
    """Extract {vars} from a FastAPI path pattern."""
    return re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", path or "")
