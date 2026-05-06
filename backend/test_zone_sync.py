"""
Unit tests for Zone Synchronization Manager (Phase 1).

Run with: python -m pytest test_zone_sync.py -v
Or directly: python test_zone_sync.py
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from zone_sync_manager import ZoneSyncManager, get_zone_sync_manager


class TestZoneSyncManager:
    """Test cases for ZoneSyncManager."""
    
    def setup_method(self):
        """Create fresh ZoneSyncManager for each test."""
        self.manager = ZoneSyncManager(zones_dir="backend/zones_test")
        # Clear any existing zones
        self.manager.zone_groups.clear()
    
    def test_valid_polygon(self):
        """Test: Valid polygon validation."""
        valid_poly = [[0, 0], [100, 0], [100, 100], [0, 100]]
        is_valid, reason = self.manager._validate_polygon(valid_poly)
        assert is_valid, f"Valid polygon rejected: {reason}"
        print("✓ test_valid_polygon passed")
    
    def test_invalid_polygon_empty(self):
        """Test: Empty polygon should be invalid."""
        is_valid, reason = self.manager._validate_polygon([])
        assert not is_valid, "Empty polygon should be invalid"
        print("✓ test_invalid_polygon_empty passed")
    
    def test_invalid_polygon_too_few_points(self):
        """Test: Polygon with < 3 points should be invalid."""
        poly = [[0, 0], [100, 100]]
        is_valid, reason = self.manager._validate_polygon(poly)
        assert not is_valid, "Polygon with 2 points should be invalid"
        print("✓ test_invalid_polygon_too_few_points passed")
    
    def test_zone_linking_valid_continuous(self):
        """Test: Define zones in cameras 1-4 with valid continuity."""
        # Create overlapping zones (camera order north to south)
        zone_configs = [
            {
                "camera_id": 1,
                "polygon": [[100, 50], [300, 50], [300, 200], [100, 200]],
                "blocker_left": [50, 125],
                "blocker_right": [350, 125],
                "name": "Camera 1 Zone"
            },
            {
                "camera_id": 2,
                "polygon": [[150, 60], [280, 60], [280, 210], [150, 210]],  # Overlaps with cam1
                "blocker_left": [120, 135],
                "blocker_right": [310, 135],
                "name": "Camera 2 Zone"
            },
            {
                "camera_id": 3,
                "polygon": [[160, 70], [270, 70], [270, 220], [160, 220]],  # Overlaps with cam2
                "blocker_left": [130, 145],
                "blocker_right": [300, 145],
                "name": "Camera 3 Zone"
            },
            {
                "camera_id": 4,
                "polygon": [[170, 80], [260, 80], [260, 230], [170, 230]],  # Overlaps with cam3
                "blocker_left": [140, 155],
                "blocker_right": [290, 155],
                "name": "Camera 4 Zone"
            }
        ]
        
        is_valid, reason, zone_group = self.manager.link_zones(zone_configs)
        
        assert is_valid, f"Valid continuous zones rejected: {reason}"
        assert zone_group is not None, "Zone group should be created"
        assert zone_group["zone_group_id"] is not None, "Zone group ID should exist"
        assert len(zone_group["cameras"]) == 4, "Should have 4 camera zones"
        print(f"✓ test_zone_linking_valid_continuous passed (zone_id: {zone_group['zone_group_id']})")
    
    def test_zone_linking_invalid_gap(self):
        """Test: Zone with gap between cameras should fail validation."""
        zone_configs = [
            {
                "camera_id": 1,
                "polygon": [[100, 50], [300, 50], [300, 200], [100, 200]],
                "name": "Camera 1 Zone"
            },
            {
                "camera_id": 2,
                "polygon": [[400, 400], [500, 400], [500, 500], [400, 500]],  # No overlap!
                "name": "Camera 2 Zone"
            },
            {
                "camera_id": 3,
                "polygon": [[410, 410], [490, 410], [490, 490], [410, 490]],
                "name": "Camera 3 Zone"
            },
            {
                "camera_id": 4,
                "polygon": [[420, 420], [480, 420], [480, 480], [420, 480]],
                "name": "Camera 4 Zone"
            }
        ]
        
        is_valid, reason, zone_group = self.manager.link_zones(zone_configs)
        
        assert not is_valid, "Invalid zones with gap should be rejected"
        assert zone_group is None, "Zone group should not be created for invalid zones"
        assert "Continuity" in reason, "Error should mention continuity"
        print(f"✓ test_zone_linking_invalid_gap passed (correctly rejected: {reason})")
    
    def test_zone_save_and_load(self):
        """Test: Save zone group to JSON and load it back."""
        # Create valid zone group
        zone_configs = [
            {
                "camera_id": 1,
                "polygon": [[100, 50], [200, 50], [200, 150], [100, 150]],
                "name": "Zone 1"
            },
            {
                "camera_id": 2,
                "polygon": [[150, 60], [250, 60], [250, 160], [150, 160]],
                "name": "Zone 2"
            },
            {
                "camera_id": 3,
                "polygon": [[160, 70], [260, 70], [260, 170], [160, 170]],
                "name": "Zone 3"
            },
            {
                "camera_id": 4,
                "polygon": [[170, 80], [270, 80], [270, 180], [170, 180]],
                "name": "Zone 4"
            }
        ]
        
        is_valid, reason, zone_group = self.manager.link_zones(zone_configs)
        assert is_valid, f"Failed to create zone: {reason}"
        
        zone_id = zone_group["zone_group_id"]
        
        # Load it back
        loaded_group = self.manager.load_zone_group(zone_id)
        assert loaded_group is not None, "Loaded zone group should not be None"
        assert loaded_group["zone_group_id"] == zone_id, "Zone ID should match"
        assert len(loaded_group["cameras"]) == 4, "Should have 4 cameras"
        
        print(f"✓ test_zone_save_and_load passed (zone_id: {zone_id})")
    
    def test_get_camera_specific_zone(self):
        """Test: Get camera-specific polygon from zone group."""
        zone_configs = [
            {
                "camera_id": 1,
                "polygon": [[100, 50], [200, 50], [200, 150], [100, 150]],
                "blocker_left": [50, 100],
                "blocker_right": [250, 100],
                "name": "Zone 1"
            },
            {
                "camera_id": 2,
                "polygon": [[150, 60], [250, 60], [250, 160], [150, 160]],
                "blocker_left": [100, 110],
                "blocker_right": [300, 110],
                "name": "Zone 2"
            },
            {
                "camera_id": 3,
                "polygon": [[160, 70], [260, 70], [260, 170], [160, 170]],
                "blocker_left": [110, 120],
                "blocker_right": [310, 120],
                "name": "Zone 3"
            },
            {
                "camera_id": 4,
                "polygon": [[170, 80], [270, 80], [270, 180], [170, 180]],
                "blocker_left": [120, 130],
                "blocker_right": [320, 130],
                "name": "Zone 4"
            }
        ]
        
        is_valid, reason, zone_group = self.manager.link_zones(zone_configs)
        assert is_valid, f"Failed to create zone: {reason}"
        
        zone_id = zone_group["zone_group_id"]
        
        # Get Camera 2's zone
        cam2_zone = self.manager.get_zone_for_camera(zone_id, 2)
        assert cam2_zone is not None, "Camera 2 zone should exist"
        assert cam2_zone["camera_id"] == 2, "Camera ID should be 2"
        assert cam2_zone["polygon"] == zone_configs[1]["polygon"], "Polygon should match"
        assert cam2_zone["blocker_left"] == [100, 110], "Blocker left position should match"
        
        print(f"✓ test_get_camera_specific_zone passed")
    
    def test_list_zone_groups(self):
        """Test: List all zone groups."""
        # Create first zone
        zones1 = [
            {
                "camera_id": 1,
                "polygon": [[100, 50], [200, 50], [200, 150], [100, 150]],
                "name": "Zone A"
            },
            {
                "camera_id": 2,
                "polygon": [[150, 60], [250, 60], [250, 160], [150, 160]],
                "name": "Zone A"
            },
            {
                "camera_id": 3,
                "polygon": [[160, 70], [260, 70], [260, 170], [160, 170]],
                "name": "Zone A"
            },
            {
                "camera_id": 4,
                "polygon": [[170, 80], [270, 80], [270, 180], [170, 180]],
                "name": "Zone A"
            }
        ]
        
        self.manager.link_zones(zones1)
        
        # Create second zone
        zones2 = [
            {
                "camera_id": 1,
                "polygon": [[300, 100], [400, 100], [400, 200], [300, 200]],
                "name": "Zone B"
            },
            {
                "camera_id": 2,
                "polygon": [[320, 110], [420, 110], [420, 210], [320, 210]],
                "name": "Zone B"
            },
            {
                "camera_id": 3,
                "polygon": [[330, 120], [430, 120], [430, 220], [330, 220]],
                "name": "Zone B"
            },
            {
                "camera_id": 4,
                "polygon": [[340, 130], [440, 130], [440, 230], [340, 230]],
                "name": "Zone B"
            }
        ]
        
        self.manager.link_zones(zones2)
        
        # List zones
        zone_ids = self.manager.list_all_zone_groups()
        assert len(zone_ids) == 2, f"Should have 2 zones, got {len(zone_ids)}"
        
        print(f"✓ test_list_zone_groups passed (count: {len(zone_ids)})")
    
    def test_delete_zone_group(self):
        """Test: Delete a zone group."""
        zone_configs = [
            {
                "camera_id": 1,
                "polygon": [[100, 50], [200, 50], [200, 150], [100, 150]],
                "name": "Zone"
            },
            {
                "camera_id": 2,
                "polygon": [[150, 60], [250, 60], [250, 160], [150, 160]],
                "name": "Zone"
            },
            {
                "camera_id": 3,
                "polygon": [[160, 70], [260, 70], [260, 170], [160, 170]],
                "name": "Zone"
            },
            {
                "camera_id": 4,
                "polygon": [[170, 80], [270, 80], [270, 180], [170, 180]],
                "name": "Zone"
            }
        ]
        
        is_valid, reason, zone_group = self.manager.link_zones(zone_configs)
        zone_id = zone_group["zone_group_id"]
        
        # Delete it
        success, message = self.manager.delete_zone_group(zone_id)
        assert success, f"Delete should succeed: {message}"
        
        # Try to load it (should fail)
        loaded = self.manager.load_zone_group(zone_id)
        assert loaded is None, "Deleted zone should not be loadable"
        
        print(f"✓ test_delete_zone_group passed")
    
    def test_overlap_detection(self):
        """Test: Detect overlap regions between adjacent cameras."""
        zone_configs = [
            {
                "camera_id": 1,
                "polygon": [[100, 50], [200, 50], [200, 150], [100, 150]],
                "name": "Zone"
            },
            {
                "camera_id": 2,
                "polygon": [[150, 60], [250, 60], [250, 160], [150, 160]],
                "name": "Zone"
            },
            {
                "camera_id": 3,
                "polygon": [[160, 70], [260, 70], [260, 170], [160, 170]],
                "name": "Zone"
            },
            {
                "camera_id": 4,
                "polygon": [[170, 80], [270, 80], [270, 180], [170, 180]],
                "name": "Zone"
            }
        ]
        
        is_valid, reason, zone_group = self.manager.link_zones(zone_configs)
        assert is_valid, f"Zone linking failed: {reason}"
        
        overlaps = zone_group["validation"]["overlaps"]
        assert len(overlaps) == 3, f"Should have 3 overlaps (1->2, 2->3, 3->4), got {len(overlaps)}"
        
        # Check first overlap
        assert overlaps[0]["camera_pair"] == [1, 2], "First overlap should be camera pair 1->2"
        assert overlaps[0]["overlap_type"] in ["overlap", "touch"], "Should be overlap or touch"
        
        print(f"✓ test_overlap_detection passed (detected {len(overlaps)} overlaps)")


def run_all_tests():
    """Run all tests."""
    test_instance = TestZoneSyncManager()
    
    tests = [
        test_instance.test_valid_polygon,
        test_instance.test_invalid_polygon_empty,
        test_instance.test_invalid_polygon_too_few_points,
        test_instance.test_zone_linking_valid_continuous,
        test_instance.test_zone_linking_invalid_gap,
        test_instance.test_zone_save_and_load,
        test_instance.test_get_camera_specific_zone,
        test_instance.test_list_zone_groups,
        test_instance.test_delete_zone_group,
        test_instance.test_overlap_detection,
    ]
    
    print("\n" + "="*70)
    print("PHASE 1: Zone Synchronization Manager Tests")
    print("="*70 + "\n")
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test_instance.setup_method()
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
