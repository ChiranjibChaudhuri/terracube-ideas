"""
Pydantic validators for temporal operations and cellular automata.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class TemporalLevel(str, Enum):
    """Temporal hierarchy levels from IDEAS paper (T0-T9)."""
    INSTANT = "instant"        # T0: Single moment
    MICRO = "micro"          # T1: Very short duration
    MINUTE = "minute"        # T2: Minute-level
    HOUR = "hour"            # T3: Hour-level
    DAY = "day"              # T4: Day-level
    WEEK = "week"            # T5: Week-level
    MONTH = "month"          # T6: Month-level
    QUARTER = "quarter"       # T7: Season/quarter
    YEAR = "year"            # T8: Year-level
    DECADE = "decade"        # T9: Decade-level


class TemporalOperation(str, Enum):
    """Types of temporal operations."""
    SNAPSHOT = "snapshot"              # Get data at specific time
    RANGE = "range"                  # Get data across time range
    AGGREGATE = "aggregate"           # Aggregate to coarser temporal resolution
    DIFFERENCE = "difference"          # Compute difference between times
    TIMESERIES = "timeseries"         # Extract time series for cells


class CARuleType(str, Enum):
    """Types of cellular automata rules."""
    FIRE_SPREAD = "fire_spread"       # Fire spread simulation
    EPIDEMIC = "epidemic"           # Epidemic spread
    OPINION = "opinion"              # Opinion dynamics
    GAME_OF_LIFE = "game_of_life"   # Conway's Game of Life
    CUSTOM = "custom"                 # Custom rule set


class TemporalSnapshotRequest(BaseModel):
    """Request model for temporal snapshot query."""
    dataset_id: str = Field(
        ...,
        description="Dataset to query"
    )
    tid: int = Field(
        ...,
        ge=0,
        description="Temporal ID to snapshot"
    )
    dggids: Optional[List[str]] = Field(
        default=None,
        description="Optional filter for specific cells"
    )

    @field_validator('dggids')
    @classmethod
    def validate_dggids(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and dedupe DGGID list."""
        if v is None:
            return None
        if not v:
            raise ValueError("dggids cannot be empty if provided")
        if len(v) > 10000:
            raise ValueError("dggids too large (max 10000)")
        return list(set(v))


class TemporalRangeRequest(BaseModel):
    """Request model for temporal range query."""
    dataset_id: str = Field(
        ...,
        description="Dataset to query"
    )
    tid_start: int = Field(
        ...,
        ge=0,
        description="Start temporal ID (inclusive)"
    )
    tid_end: int = Field(
        ...,
        ge=0,
        description="End temporal ID (inclusive)"
    )
    dggids: Optional[List[str]] = Field(
        default=None,
        description="Optional filter for specific cells"
    )
    aggregation: Optional[str] = Field(
        default="raw",
        pattern="^(raw|mean|max|min|sum|count)$",
        description="How to aggregate multiple time points"
    )

    @field_validator('tid_start', 'tid_end')
    @classmethod
    def validate_range(cls, v_start: int, v_end: int) -> tuple:
        """Validate that start <= end."""
        if v_start > v_end:
            raise ValueError("tid_start must be less than or equal to tid_end")
        return v_start, v_end


class TemporalAggregateRequest(BaseModel):
    """Request model for temporal aggregation."""
    dataset_id: str = Field(
        ...,
        description="Dataset to aggregate"
    )
    source_level: TemporalLevel = Field(
        ...,
        description="Source temporal resolution"
    )
    target_level: TemporalLevel = Field(
        ...,
        description="Target temporal resolution (coarser)"
    )
    aggregation: str = Field(
        default="mean",
        pattern="^(mean|median|max|min|sum|count|first|last)$",
        description="Aggregation method"
    )
    output_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name for output dataset"
    )

    @field_validator('source_level', 'target_level')
    @classmethod
    def validate_levels(cls, source: TemporalLevel, target: TemporalLevel) -> tuple:
        """Validate that target is coarser than source."""
        level_order = {
            TemporalLevel.INSTANT: 0,
            TemporalLevel.MICRO: 1,
            TemporalLevel.MINUTE: 2,
            TemporalLevel.HOUR: 3,
            TemporalLevel.DAY: 4,
            TemporalLevel.WEEK: 5,
            TemporalLevel.MONTH: 6,
            TemporalLevel.QUARTER: 7,
            TemporalLevel.YEAR: 8,
            TemporalLevel.DECADE: 9,
        }
        if level_order[target] <= level_order[source]:
            raise ValueError("target_level must be coarser (higher) than source_level")
        return source, target


class CAInitializeRequest(BaseModel):
    """Request model for initializing a cellular automata simulation."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Simulation name"
    )
    rule_type: CARuleType = Field(
        ...,
        description="Type of CA rule"
    )
    dataset_id: str = Field(
        ...,
        description="Base dataset for cell geometry"
    )
    state_attribute: str = Field(
        default="state",
        max_length=100,
        description="Attribute to store cell state"
    )
    initial_state: Optional[Dict[str, int]] = Field(
        default=None,
        description="Map of DGGIDs to initial state values"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rule-specific parameters"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Simulation description"
    )


class CAStepRequest(BaseModel):
    """Request model for stepping a CA simulation."""
    simulation_id: str = Field(
        ...,
        description="Simulation ID"
    )
    steps: int = Field(
        default=1,
        ge=1,
        le=1000,
        description="Number of steps to run"
    )
    save_interval: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Save snapshot every N steps (None for final only)"
    )


class CARunRequest(BaseModel):
    """Request model for running a CA simulation to completion."""
    simulation_id: str = Field(
        ...,
        description="Simulation ID"
    )
    max_steps: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Maximum steps to run"
    )
    stop_condition: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Custom stop condition (e.g., 'no_changes', 'threshold:0.9')"
    )
    save_interval: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Save snapshot every N steps"
    )
    output_dataset: bool = Field(
        default=False,
        description="Create output dataset from final state"
    )
