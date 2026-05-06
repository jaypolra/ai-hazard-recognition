"""
Zone Synchronization Manager for Multi-Camera Zone Linking and Validation.

This module handles:
- Linking zones across 4 cameras with unique zone_group_id
- Validating continuity (zones touch or overlap between adjacent cameras)
- Detecting and storing overlap regions
- Saving/loading zone groups from JSON files
- Retrieving camera-specific zones from groups
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional

try:
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
except ImportError:
    print("[WARNING] shapely not installed. Install with: pip install shapely")
    Polygon = None
    box = None


class ZoneSyncManager:
    """Manages multi-camera zone linking and continuity validation."""
    
    def __init__(self, zones_dir: str = "backend/zones"):
        """
        Initialize ZoneSyncManager.
        
        Args:
            zones_dir: Directory to store zone group JSON files
        """
        self.zones_dir = Path(zones_dir)
        self.zones_dir.mkdir(parents=True, exist_ok=True)
        self.zone_groups = {}
        self._load_all_zone_groups()
    
    def _load_all_zone_groups(self):
        """Load all existing zone groups from disk."""
        for zone_file in self.zones_dir.glob("zone_*.json"):
            try:
                with open(zone_file, 'r') as f:
                    zone_group = json.load(f)
                    zone_id = zone_group.get("zone_group_id")
                    if zone_id:
                        self.zone_groups[zone_id] = zone_group
            except Exception as e:
                print(f"[ZoneSyncManager] Error loading {zone_file}: {e}")
    
    def link_zones(self, zone_configs: List[Dict]) -> Tuple[bool, str, Optional[Dict]]:
        """
        Link zones from cameras 1-4 and validate continuity.
        
        Args:
            zone_configs: List of zone configs
                Format: [
                    {"camera_id": 1, "polygon": [[x,y], ...], "name": str},
                    {"camera_id": 2, "polygon": [[x,y], ...], "name": str},
                    ... (3, 4)
                ]
        
        Returns:
            (is_valid: bool, reason: str, zone_group_dict: dict or None)
        """
        
        # Validate input
        if not zone_configs or len(zone_configs) == 0:
            return False, "No zone configs provided", None
        
        # Sort by camera_id to ensure order
        zone_configs = sorted(zone_configs, key=lambda z: z.get("camera_id", 99))
        
        # Check we have camera IDs 1-4
        camera_ids = [z.get("camera_id") for z in zone_configs]
        if camera_ids != [1, 2, 3, 4]:
            return False, f"Must provide all 4 cameras in order. Got: {camera_ids}", None
        
        # Validate individual polygons
        for config in zone_configs:
            is_valid_poly, poly_reason = self._validate_polygon(config.get("polygon", []))
            if not is_valid_poly:
                cam_id = config.get("camera_id")
                return False, f"Camera {cam_id}: {poly_reason}", None
        
        # Check continuity between adjacent cameras
        is_continuous, continuity_reason, overlaps = self._validate_continuity(zone_configs)
        if not is_continuous:
            return False, f"Continuity validation failed: {continuity_reason}", None
        
        # Create zone group
        zone_group = self._create_zone_group(zone_configs, overlaps)
        
        # Save to disk
        success, save_reason = self.save_zone_group(zone_group)
        if not success:
            return False, f"Failed to save zone group: {save_reason}", None
        
        return True, f"Zone group created: {zone_group['zone_group_id']}", zone_group
    
    def _validate_polygon(self, polygon: List[List[float]]) -> Tuple[bool, str]:
        """
        Validate that polygon has at least 3 points and forms valid shape.
        
        Args:
            polygon: List of [x, y] coordinates
        
        Returns:
            (is_valid: bool, reason: str)
        """
        if not polygon:
            return False, "Polygon is empty"
        
        if len(polygon) < 3:
            return False, f"Polygon needs at least 3 points, got {len(polygon)}"
        
        # Check all points are [x, y] pairs
        try:
            for point in polygon:
                if len(point) != 2:
                    return False, f"Point {point} is not [x, y] format"
                float(point[0])
                float(point[1])
        except (TypeError, ValueError) as e:
            return False, f"Invalid point format: {e}"
        
        return True, "Valid"
    
    def _validate_continuity(self, zone_configs: List[Dict]) -> Tuple[bool, str, List[Dict]]:
        """
        Validate zones form continuous workspace (adjacent zones touch or overlap).
        
        Args:
            zone_configs: Sorted list of zone configs [cam1, cam2, cam3, cam4]
        
        Returns:
            (is_continuous: bool, reason: str, overlaps: list of overlap info)
        """
        overlaps = []
        
        # Check each adjacent pair: 1->2, 2->3, 3->4
        for i in range(len(zone_configs) - 1):
            cam1_config = zone_configs[i]
            cam2_config = zone_configs[i + 1]
            
            cam1_id = cam1_config.get("camera_id")
            cam2_id = cam2_config.get("camera_id")
            
            poly1 = cam1_config.get("polygon", [])
            poly2 = cam2_config.get("polygon", [])
            
            # Check overlap/touch
            overlap_area, overlap_type = self._detect_overlap(poly1, poly2)
            
            if overlap_area is None:
                cam_ids = f"{cam1_id}->{cam2_id}"
                return False, f"Camera {cam_ids} zones don't touch or overlap", []
            
            # Store overlap info
            overlaps.append({
                "camera_pair": [cam1_id, cam2_id],
                "overlap_type": overlap_type,  # "touch" or "overlap"
                "overlap_area": overlap_area
            })
        
        return True, "All adjacent cameras continuous", overlaps
    
    def _detect_overlap(self, poly1: List[List[float]], poly2: List[List[float]]) -> Tuple[Optional[List], Optional[str]]:
        """
        Detect if two polygons touch or overlap.
        
        Args:
            poly1, poly2: Polygon coordinates [[x,y], ...]
        
        Returns:
            (overlap_polygon: [[x,y], ...] or None, overlap_type: "touch" | "overlap" | None)
        """
        if not Polygon:
            # Shapely not available, do simple bounding box check
            return self._simple_overlap_check(poly1, poly2)
        
        try:
            shape1 = Polygon(poly1)
            shape2 = Polygon(poly2)
            
            # Check if shapes are valid
            if not shape1.is_valid or not shape2.is_valid:
                return None, None
            
            # Check intersection
            intersection = shape1.intersection(shape2)
            
            if intersection.is_empty:
                # Check if they touch (share boundary)
                if shape1.touches(shape2):
                    # They touch but don't overlap
                    # Return the touching line as "overlap"
                    boundary = shape1.boundary.intersection(shape2.boundary)
                    coords = list(boundary.coords) if hasattr(boundary, 'coords') else []
                    return coords, "touch"
                return None, None
            else:
                # They overlap
                if str(intersection.geom_type) == 'Polygon':
                    overlap_coords = list(intersection.exterior.coords)[:-1]  # Remove duplicate last point
                elif str(intersection.geom_type) == 'LineString':
                    # Line intersection (touching)
                    return list(intersection.coords), "touch"
                else:
                    # MultiPolygon or other
                    overlap_coords = list(intersection.exterior.coords)[:-1] if hasattr(intersection, 'exterior') else []
                
                return overlap_coords, "overlap"
        
        except Exception as e:
            print(f"[ZoneSyncManager] Error checking overlap: {e}")
            return None, None
    
    def _simple_overlap_check(self, poly1: List[List[float]], poly2: List[List[float]]) -> Tuple[Optional[List], Optional[str]]:
        """
        Simple bounding box overlap check (fallback when Shapely unavailable).
        
        Args:
            poly1, poly2: Polygon coordinates
        
        Returns:
            (overlap_area: [[x,y], ...] or None, type: str or None)
        """
        def get_bounds(poly):
            """Get bounding box: (min_x, min_y, max_x, max_y)"""
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            return (min(xs), min(ys), max(xs), max(ys))
        
        x1_min, y1_min, x1_max, y1_max = get_bounds(poly1)
        x2_min, y2_min, x2_max, y2_max = get_bounds(poly2)
        
        # Check if bounding boxes overlap or touch
        if x1_max < x2_min or x2_max < x1_min or y1_max < y2_min or y2_max < y1_min:
            return None, None  # No overlap
        
        # Bounding boxes touch or overlap
        overlap_type = "overlap" if (x1_max > x2_min and x2_max > x1_min and 
                                      y1_max > y2_min and y2_max > y1_min) else "touch"
        
        # Return bounding box of overlap
        overlap_box = [
            [max(x1_min, x2_min), max(y1_min, y2_min)],
            [min(x1_max, x2_max), max(y1_min, y2_min)],
            [min(x1_max, x2_max), min(y1_max, y2_max)],
            [max(x1_min, x2_min), min(y1_max, y2_max)]
        ]
        
        return overlap_box, overlap_type
    
    def _create_zone_group(self, zone_configs: List[Dict], overlaps: List[Dict]) -> Dict:
        """
        Create zone group dictionary with metadata.
        
        Args:
            zone_configs: Zone configs for each camera
            overlaps: Overlap information between adjacent cameras
        
        Returns:
            zone_group: Complete zone group dictionary
        """
        from datetime import datetime
        import uuid
        
        # Generate unique zone_group_id
        zone_group_id = f"zone_{uuid.uuid4().hex[:8]}"
        zone_name = zone_configs[0].get("name", "Multi-Camera Zone")
        
        zone_group = {
            "zone_group_id": zone_group_id,
            "name": zone_name,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "cameras": [],
            "validation": {
                "is_continuous": True,
                "continuity_type": "mixed",  # May have both "touch" and "overlap"
                "overlaps": overlaps
            }
        }
        
        # Add camera-specific zones
        for config in zone_configs:
            camera_zone = {
                "camera_id": config.get("camera_id"),
                "polygon": config.get("polygon", []),
                "blocker_left": config.get("blocker_left", []),
                "blocker_right": config.get("blocker_right", []),
                "name": config.get("name", f"Camera {config.get('camera_id')} Zone")
            }
            zone_group["cameras"].append(camera_zone)
        
        return zone_group
    
    def save_zone_group(self, zone_group: Dict) -> Tuple[bool, str]:
        """
        Save zone group to JSON file.
        
        Args:
            zone_group: Zone group dictionary
        
        Returns:
            (success: bool, reason: str)
        """
        try:
            zone_id = zone_group.get("zone_group_id")
            if not zone_id:
                return False, "zone_group_id not provided"
            
            file_path = self.zones_dir / f"{zone_id}.json"
            
            with open(file_path, 'w') as f:
                json.dump(zone_group, f, indent=2)
            
            # Cache in memory
            self.zone_groups[zone_id] = zone_group
            
            print(f"[ZoneSyncManager] Saved zone group: {zone_id}")
            return True, f"Saved to {file_path}"
        
        except Exception as e:
            return False, str(e)
    
    def load_zone_group(self, zone_group_id: str) -> Optional[Dict]:
        """
        Load zone group by ID.
        
        Args:
            zone_group_id: Zone group identifier
        
        Returns:
            zone_group: Zone group dictionary, or None if not found
        """
        # Check memory cache first
        if zone_group_id in self.zone_groups:
            return self.zone_groups[zone_group_id]
        
        # Try loading from disk
        file_path = self.zones_dir / f"{zone_group_id}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    zone_group = json.load(f)
                    self.zone_groups[zone_group_id] = zone_group
                    return zone_group
            except Exception as e:
                print(f"[ZoneSyncManager] Error loading {zone_group_id}: {e}")
        
        return None
    
    def get_zone_for_camera(self, zone_group_id: str, camera_id: int) -> Optional[Dict]:
        """
        Retrieve camera-specific zone from a zone group.
        
        Args:
            zone_group_id: Zone group identifier
            camera_id: Camera number (1-4)
        
        Returns:
            camera_zone: {"polygon": [[x,y], ...], "blocker_left": [x,y], "blocker_right": [x,y]}
                        or None if not found
        """
        zone_group = self.load_zone_group(zone_group_id)
        if not zone_group:
            return None
        
        cameras = zone_group.get("cameras", [])
        for camera_zone in cameras:
            if camera_zone.get("camera_id") == camera_id:
                return camera_zone
        
        return None
    
    def list_all_zone_groups(self) -> List[str]:
        """
        Return list of all zone_group_ids.
        
        Returns:
            List of zone_group_ids
        """
        return list(self.zone_groups.keys())
    
    def get_all_zone_groups(self) -> List[Dict]:
        """
        Return all zone group dictionaries.
        
        Returns:
            List of zone group dictionaries
        """
        return list(self.zone_groups.values())
    
    def delete_zone_group(self, zone_group_id: str) -> Tuple[bool, str]:
        """
        Delete zone group from disk and memory.
        
        Args:
            zone_group_id: Zone group identifier
        
        Returns:
            (success: bool, reason: str)
        """
        try:
            file_path = self.zones_dir / f"{zone_group_id}.json"
            
            if file_path.exists():
                os.remove(file_path)
            
            # Remove from memory cache
            if zone_group_id in self.zone_groups:
                del self.zone_groups[zone_group_id]
            
            print(f"[ZoneSyncManager] Deleted zone group: {zone_group_id}")
            return True, f"Deleted {zone_group_id}"
        
        except Exception as e:
            return False, str(e)
    
    def update_zone_group(self, zone_group_id: str, zone_group: Dict) -> Tuple[bool, str]:
        """
        Update existing zone group.
        
        Args:
            zone_group_id: Zone group identifier
            zone_group: Updated zone group dictionary
        
        Returns:
            (success: bool, reason: str)
        """
        zone_group["last_updated"] = datetime.now().isoformat()
        return self.save_zone_group(zone_group)
    
    def validate_zone_group_structure(self, zone_group: Dict) -> Tuple[bool, str]:
        """
        Validate zone group has all required fields.
        
        Args:
            zone_group: Zone group dictionary
        
        Returns:
            (is_valid: bool, reason: str)
        """
        required_fields = ["zone_group_id", "name", "created_at", "cameras", "validation"]
        
        for field in required_fields:
            if field not in zone_group:
                return False, f"Missing required field: {field}"
        
        cameras = zone_group.get("cameras", [])
        if len(cameras) != 4:
            return False, f"Must have exactly 4 cameras, got {len(cameras)}"
        
        for i, camera_zone in enumerate(cameras):
            if camera_zone.get("camera_id") != (i + 1):
                return False, f"Camera IDs must be 1, 2, 3, 4 in order"
        
        return True, "Valid structure"


# Global instance
_zone_sync_manager = None

def get_zone_sync_manager():
    """Get or create global ZoneSyncManager instance."""
    global _zone_sync_manager
    if _zone_sync_manager is None:
        _zone_sync_manager = ZoneSyncManager()
    return _zone_sync_manager
