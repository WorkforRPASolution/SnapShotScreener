"""Configuration dataclass for SnapshotScreener."""
from dataclasses import dataclass
from datetime import date
from typing import Optional, List


@dataclass(frozen=True)
class ScreenerConfig:
    """Immutable configuration for a screening run.

    All fields are validated in ``__post_init__``.  Because ``frozen=True``
    prevents normal attribute assignment, any post-init transformations
    would need ``object.__setattr__``; however we only validate here.
    """

    # Target
    eqpids: List[str]
    date_from: date
    date_to: date

    # Cassandra
    db_host: str
    db_port: int = 9042
    db_keyspace: str = ""
    db_table: str = ""
    db_username: Optional[str] = None
    db_password: Optional[str] = None
    read_delay_ms: int = 200
    fname_delay_ms: int = 100  # Separate rate limit for fname queries
    max_connections: int = 2

    # Analysis
    session_gap_ms: int = 900_000
    phash_similar_threshold: int = 4
    phash_transition_threshold: int = 8
    delta_spike_ms: int = 30_000
    dbscan_eps: float = 0.03
    dbscan_min_samples: int = 2
    screen_width: int = 1920
    screen_height: int = 1080
    selector: str = "simple"
    sensitivity_sweep: bool = False
    fname_pattern: str = "auto"

    # Cache/Output
    cache_dir: str = "."
    output_dir: str = "."
    invalidate_cache: bool = False
    verbose: bool = False

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.date_from > self.date_to:
            raise ValueError(
                f"date_from ({self.date_from}) must be <= date_to ({self.date_to})"
            )

        positive_int_fields = [
            ("db_port", self.db_port),
            ("read_delay_ms", self.read_delay_ms),
            ("fname_delay_ms", self.fname_delay_ms),
            ("max_connections", self.max_connections),
            ("session_gap_ms", self.session_gap_ms),
            ("phash_similar_threshold", self.phash_similar_threshold),
            ("phash_transition_threshold", self.phash_transition_threshold),
            ("delta_spike_ms", self.delta_spike_ms),
            ("dbscan_min_samples", self.dbscan_min_samples),
            ("screen_width", self.screen_width),
            ("screen_height", self.screen_height),
        ]
        for name, value in positive_int_fields:
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")

        if self.dbscan_eps <= 0:
            raise ValueError(
                f"dbscan_eps must be a positive number, got {self.dbscan_eps!r}"
            )

    def __repr__(self) -> str:
        """Return repr with db_password masked."""
        fields = []
        for f in self.__dataclass_fields__:
            value = getattr(self, f)
            if f == "db_password" and value is not None:
                fields.append(f"{f}='****'")
            else:
                fields.append(f"{f}={value!r}")
        return f"ScreenerConfig({', '.join(fields)})"
