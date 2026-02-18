from dataclasses import dataclass, asdict
from typing import Any, Optional

@dataclass
class Metric:
    name: str
    value: Any
    collector_type: str
    timestamp: str
    unit: Optional[str] = None


