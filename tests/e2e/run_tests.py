#!/usr/bin/env python3
import os
import sys
import unittest

def main():
    # Determine project root and cases directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cases_dir = os.path.join(project_root, "tests", "e2e", "cases")
    
    # Ensure project root is in sys.path for easy importing of modules
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    print("=" * 70)
    print("Caelestia Shell E2E Test Runner")
    print(f"Project root: {project_root}")
    print(f"Discovering tests in: {cases_dir}")
    print("=" * 70)
    
    # Ensure cases directory exists
    os.makedirs(cases_dir, exist_ok=True)
    
    # Pre-create subdirectories to establish correct layout
    subdirs = [
        "tier1_feature_coverage",
        "tier2_boundary_corner",
        "tier3_cross_feature",
        "tier4_real_world"
    ]
    for subdir in subdirs:
        subdir_path = os.path.join(cases_dir, subdir)
        os.makedirs(subdir_path, exist_ok=True)
        # Create an empty __init__.py so Python treats them as packages
        init_file = os.path.join(subdir_path, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                pass

    # Standard unittest test discovery
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=cases_dir, pattern='test_*.py')
    
    # Run the tests with a verbose runner
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 70)
    print("Test Run Summary:")
    print(f"  Tests run: {result.testsRun}")
    print(f"  Errors   : {len(result.errors)}")
    print(f"  Failures : {len(result.failures)}")
    print("=" * 70)
    
    if result.wasSuccessful():
        print("SUCCESS: All discovered tests passed.")
        sys.exit(0)
    else:
        print("FAILURE: Some tests failed or encountered errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
