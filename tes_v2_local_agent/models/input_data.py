from pydantic import BaseModel
from typing import Dict, Any, List, Union

class InputData(BaseModel):
    # Support both flat and nested JSON
    data: Union[Dict[str, Any], List[Dict[str, Any]]]
