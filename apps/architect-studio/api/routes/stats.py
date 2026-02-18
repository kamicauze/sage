"""
Stats and usage endpoints for budget tracking.
"""
import json
from datetime import datetime
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException

from architect.api.models import UsageStats, MemoryStats
from architect.paths import USAGE_FILE as USAGE_FILE_PATH, USAGE_LOG_FILE as USAGE_LOG_FILE_PATH
from architect.api.security import validate_project_id

router = APIRouter(prefix="/stats", tags=["statistics"])

USAGE_FILE = USAGE_FILE_PATH
USAGE_LOG_FILE = USAGE_LOG_FILE_PATH


def _get_current_month_key() -> str:
    """Get current month key in YYYY-MM format."""
    return datetime.now().strftime("%Y-%m")


def _load_usage_data() -> Dict[str, float]:
    """Load usage data from JSON file."""
    if not USAGE_FILE.exists():
        return {}
    try:
        with open(USAGE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _load_usage_log(limit: int = 20) -> List[Dict[str, Any]]:
    """Load recent usage log entries."""
    if not USAGE_LOG_FILE.exists():
        return []

    try:
        entries = []
        with open(USAGE_LOG_FILE, 'r') as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except:
                    continue

        # Return most recent entries
        return entries[-limit:]
    except Exception:
        return []


def _get_today_spend(usage_log: List[Dict[str, Any]]) -> float:
    """Calculate today's spend from usage log."""
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0.0

    for entry in usage_log:
        try:
            entry_date = entry.get("timestamp", "")[:10]
            if entry_date == today:
                total += entry.get("cost", 0.0)
        except:
            continue

    return total


@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    daily_limit: float = 5.0,
    monthly_limit: float = 120.0
) -> UsageStats:
    """
    Get current usage and budget statistics.

    Args:
        daily_limit: Daily burst limit in USD (default: 5.0)
        monthly_limit: Monthly budget limit in USD (default: 120.0)

    Returns:
        UsageStats with current spend and budget information
    """
    # Load usage data
    usage_data = _load_usage_data()
    usage_log = _load_usage_log(limit=50)

    current_month = _get_current_month_key()
    monthly_spend = usage_data.get(current_month, 0.0)
    daily_spend = _get_today_spend(usage_log)

    # Calculate budget percentage
    budget_percentage = (monthly_spend / monthly_limit * 100) if monthly_limit > 0 else 0

    # Get recent calls (last 10)
    recent_calls = usage_log[-10:] if len(usage_log) > 10 else usage_log

    return UsageStats(
        current_month=current_month,
        monthly_spend=round(monthly_spend, 2),
        monthly_limit=monthly_limit,
        daily_spend=round(daily_spend, 2),
        daily_limit=daily_limit,
        budget_percentage=round(budget_percentage, 1),
        recent_calls=recent_calls
    )


@router.get("/usage/history")
async def get_usage_history(limit: int = 100) -> Dict[str, Any]:
    """
    Get detailed usage history.

    Args:
        limit: Maximum number of entries to return (default: 100)

    Returns:
        Dictionary with usage log entries
    """
    usage_log = _load_usage_log(limit=limit)

    # Group by date
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for entry in usage_log:
        date = entry.get("timestamp", "")[:10]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(entry)

    # Calculate daily totals
    daily_totals = {}
    for date, entries in by_date.items():
        total_cost = sum(e.get("cost", 0.0) for e in entries)
        daily_totals[date] = {
            "total_cost": round(total_cost, 2),
            "call_count": len(entries),
            "entries": entries
        }

    return {
        "total_entries": len(usage_log),
        "daily_breakdown": daily_totals,
        "all_entries": usage_log
    }


@router.get("/memory", response_model=MemoryStats)
async def get_memory_stats(project_id: str = "sage_brain") -> MemoryStats:
    """
    Get memory system statistics.

    Args:
        project_id: Project ID to get stats for (default: sage_brain)

    Returns:
        MemoryStats with collection information
    """
    try:
        project_id = validate_project_id(project_id)
        from architect.memory import ArchitectMemory

        memory = ArchitectMemory()

        # Try to get collection
        try:
            collection = memory._get_collection(project_id)
            total_chunks = collection.count()
            collection_exists = True

            # Get all items to count by zone
            if total_chunks > 0:
                results = collection.get()
                zones: Dict[str, int] = {}

                if results and results.get('metadatas'):
                    for meta in results['metadatas']:
                        zone_name = meta.get('zone_name', 'unknown')
                        zones[zone_name] = zones.get(zone_name, 0) + 1
            else:
                zones = {}

        except Exception as e:
            print(f"Collection error: {e}")
            total_chunks = 0
            zones = {}
            collection_exists = False

        return MemoryStats(
            project_id=project_id,
            total_chunks=total_chunks,
            zones=zones,
            collection_exists=collection_exists
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get memory stats: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Basic health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "usage_tracking": USAGE_FILE.exists(),
            "usage_log": USAGE_LOG_FILE.exists()
        }
    }
