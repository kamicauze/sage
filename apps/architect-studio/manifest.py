"""
Architect Manifest Loader (Schema v1.1)
Parses project manifests and validates essential fields.
"""
import yaml
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class CognitiveZone:
    name: str
    role: str  # truth, soul, hands, infra
    paths: List[str]

@dataclass
class ProjectManifest:
    id: str
    name: str
    repo_path: str
    zones: List[CognitiveZone] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, manifest_path: str):
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        try:
            with open(manifest_path, "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Invalid YAML in manifest: {e}")

        # Basic Validation
        project = data.get("project", {})
        if not project.get("id"):
            raise ValueError("Manifest missing required field: project.id")

        # Parse Zones (Schema v1.1)
        zones = []
        memory = data.get("memory", {})
        
        # If explicit zones are defined (v1.1)
        if "zones" in memory:
            for z in memory["zones"]:
                zones.append(CognitiveZone(
                    name=z.get("name", "Unknown Zone"),
                    role=z.get("role", "unknown"),
                    paths=z.get("paths", [])
                ))
        
        # Fallback for v1.0 (flat include_paths) -> Default Zone
        elif "include_paths" in memory:
            zones.append(CognitiveZone(
                name="Default Zone",
                role="generic",
                paths=memory["include_paths"]
            ))

        return cls(
            id=project["id"],
            name=project.get("name", project["id"]),
            repo_path=project.get("paths", {}).get("repo_path", "."),
            zones=zones,
            raw=data
        )

    @property
    def policy(self) -> Dict[str, Any]:
        return self.raw.get("policy", {})

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize to a stable, POSIX-like relative path form."""
        normalized = os.path.normpath(path).replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized.lstrip("/")

    def _path_variants(self, file_path: str) -> List[str]:
        """
        Build compatible path variants so manifests keep working across
        legacy and migrated repo layouts.
        """
        variants = set()

        # Original representation
        normalized = self._normalize_path(file_path)
        if normalized:
            variants.add(normalized)

        # If absolute path, also include path relative to manifest repo root.
        if os.path.isabs(file_path):
            repo_root = os.path.abspath(self.repo_path)
            try:
                rel = os.path.relpath(file_path, start=repo_root)
                if not rel.startswith(".."):
                    variants.add(self._normalize_path(rel))
            except Exception:
                pass

        # Legacy <-> new layout aliases
        aliases = [
            ("brain", "apps/brain-runtime"),
            ("architect", "apps/architect-studio"),
            ("shared", "packages/shared"),
        ]

        # Expand both directions once for each alias.
        expanded = set(variants)
        for variant in list(variants):
            for legacy, modern in aliases:
                for src, dst in ((legacy, modern), (modern, legacy)):
                    if variant == src:
                        expanded.add(dst)
                    elif variant.startswith(src + "/"):
                        expanded.add(dst + variant[len(src):])
        variants |= expanded

        return sorted(v for v in variants if v)

    def get_zone_for_file(self, file_path: str) -> Optional[CognitiveZone]:
        """Find the first matching zone for a file path."""
        file_variants = self._path_variants(file_path)

        for zone in self.zones:
            for path_prefix in zone.paths:
                prefix = self._normalize_path(path_prefix)
                if not prefix:
                    continue

                for candidate in file_variants:
                    if candidate == prefix or candidate.startswith(prefix + "/"):
                        return zone
        return None
