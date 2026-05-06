import numpy as np
import os
import json

# ── Zone load cache: only re-read file when mtime changes ─────────────────────
_zone_cache: dict = {}   # path → (mtime, zones)

def save_polygon(path, polygon_data):
    """Save zones as JSON instead of pickle to avoid format issues"""
    try:
        # Convert numpy types to Python types if needed
        zones_to_save = []
        for zone in polygon_data:
            zone_dict = {
                "color": zone.get("color", "red"),
                "label": zone.get("label", "Zone"),
                "type": zone.get("type", zone.get("label", "Zone")),
                "points": [[float(x), float(y)] for x, y in zone.get("points", [])],
                "confidence": float(zone.get("confidence", 0.5))
            }
            zones_to_save.append(zone_dict)
        
        # Save as JSON file with .npy extension for backward compatibility
        json_path = path.replace('.npy', '.json')
        with open(json_path, 'w') as f:
            json.dump(zones_to_save, f, indent=2)
        
        print(f"[Polygon Save] Saved {len(zones_to_save)} zones to {json_path}")
    except Exception as e:
        print(f"[Polygon Save Error] {e}")

def load_polygon(path):
    """Load zones from JSON file (with fallback to old numpy format).
    Caches result and only re-reads when the file mtime changes."""
    global _zone_cache
    try:
        # Try JSON first
        json_path = path.replace('.npy', '.json')
        if os.path.exists(json_path):
            mtime = os.path.getmtime(json_path)
            cached = _zone_cache.get(json_path)
            if cached and cached[0] == mtime:
                return cached[1]                    # cache hit — no print, no disk I/O
            with open(json_path, 'r') as f:
                zones = json.load(f)
            _zone_cache[json_path] = (mtime, zones)
            print(f"[Polygon Load] Loaded {len(zones)} zones from {json_path}")
            return zones

        # Fallback to old numpy format for backward compatibility
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            cached = _zone_cache.get(path)
            if cached and cached[0] == mtime:
                return cached[1]
            with open(path, "rb") as f:
                data = np.load(f, allow_pickle=True)
                if isinstance(data, np.ndarray):
                    zones = list(data)
                    _zone_cache[path] = (mtime, zones)
                    print(f"[Polygon Load] Loaded {len(zones)} zones from {path} (numpy format)")
                    return zones
    except Exception as e:
        print(f"[Polygon Load Error] {path}: {e}")

    print(f"[Polygon Load] No zones found at {path}")
    return []


# ============================================================================
# Multi-Camera Zone Geometric Helper Functions
# ============================================================================

def calculate_polygon_overlap(poly1, poly2):
    """
    Calculate the overlap/intersection area between two polygons.
    
    Args:
        poly1, poly2: Polygon coordinates [[x,y], ...]
    
    Returns:
        overlap_coords: [[x,y], ...] if overlap exists, empty list otherwise
    """
    try:
        from shapely.geometry import Polygon as ShapelyPolygon
        
        shape1 = ShapelyPolygon(poly1)
        shape2 = ShapelyPolygon(poly2)
        
        if not shape1.is_valid or not shape2.is_valid:
            return []
        
        intersection = shape1.intersection(shape2)
        
        if intersection.is_empty:
            return []
        
        if str(intersection.geom_type) == 'Polygon':
            return list(intersection.exterior.coords)[:-1]
        elif str(intersection.geom_type) == 'LineString':
            return list(intersection.coords)
        else:
            return []
    
    except ImportError:
        print("[WARNING] shapely not available for overlap calculation")
        return []
    except Exception as e:
        print(f"[Polygon Utils] Error calculating overlap: {e}")
        return []


def polygons_touch_or_overlap(poly1, poly2):
    """
    Check if two polygons share an edge or overlap.
    
    Args:
        poly1, poly2: Polygon coordinates [[x,y], ...]
    
    Returns:
        is_continuous: bool - True if touching or overlapping
    """
    try:
        from shapely.geometry import Polygon as ShapelyPolygon
        
        shape1 = ShapelyPolygon(poly1)
        shape2 = ShapelyPolygon(poly2)
        
        if not shape1.is_valid or not shape2.is_valid:
            return False
        
        # Check if they touch or overlap
        return shape1.intersects(shape2) or shape1.touches(shape2)
    
    except ImportError:
        # Fallback to bounding box check
        return _bounding_box_overlap(poly1, poly2)
    except Exception as e:
        print(f"[Polygon Utils] Error checking continuity: {e}")
        return False


def _bounding_box_overlap(poly1, poly2):
    """
    Simple bounding box overlap check (fallback).
    
    Args:
        poly1, poly2: Polygon coordinates
    
    Returns:
        overlaps: bool
    """
    def get_bounds(poly):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        return (min(xs), min(ys), max(xs), max(ys))
    
    x1_min, y1_min, x1_max, y1_max = get_bounds(poly1)
    x2_min, y2_min, x2_max, y2_max = get_bounds(poly2)
    
    # Check overlap or touching
    return not (x1_max < x2_min or x2_max < x1_min or y1_max < y2_min or y2_max < y1_min)


def check_spatial_continuity(polygons):
    """
    Check if all adjacent polygons in camera sequence 1→2→3→4 are continuous.
    
    Args:
        polygons: dict of {camera_id: polygon_coords}
                  or list of polygon_coords in order [cam1, cam2, cam3, cam4]
    
    Returns:
        (is_continuous: bool, issues: list of problem descriptions)
    """
    issues = []
    
    # Convert to list if dict
    if isinstance(polygons, dict):
        polys = [polygons.get(i, []) for i in range(1, 5)]
    else:
        polys = polygons
    
    if len(polys) != 4:
        return False, [f"Expected 4 polygons, got {len(polys)}"]
    
    # Check each adjacent pair
    for i in range(len(polys) - 1):
        if not polys[i] or not polys[i+1]:
            issues.append(f"Camera {i+1}-{i+2}: Missing polygon data")
            continue
        
        if not polygons_touch_or_overlap(polys[i], polys[i+1]):
            issues.append(f"Camera {i+1}-{i+2}: Zones don't touch or overlap")
    
    is_continuous = len(issues) == 0
    return is_continuous, issues


def point_in_polygon(point, polygon):
    """
    Check if a point is inside a polygon.
    
    Args:
        point: [x, y]
        polygon: [[x,y], ...]
    
    Returns:
        is_inside: bool
    """
    try:
        from shapely.geometry import Point, Polygon as ShapelyPolygon
        
        p = Point(point)
        poly = ShapelyPolygon(polygon)
        return poly.contains(p) or poly.touches(p)
    
    except ImportError:
        # Simple ray casting algorithm fallback
        return _point_in_polygon_simple(point, polygon)
    except Exception as e:
        print(f"[Polygon Utils] Error checking point in polygon: {e}")
        return False


def _point_in_polygon_simple(point, polygon):
    """
    Simple point-in-polygon test using ray casting.
    
    Args:
        point: [x, y]
        polygon: [[x,y], ...]
    
    Returns:
        is_inside: bool
    """
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside
