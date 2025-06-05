from dataclasses import dataclass, field
import time

@dataclass
class PluginResult:
    slug: str
    status: str  # "True", "False", "skipped", or "error:..."
    timestamp: float = field(default_factory=time.time)

    @property
    def readable_time(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
