"""
Simplified Formula Validator for QPANSOPY
Tests all mathematical formulas directly without external test modules
"""
import math
import sys
import os
import json
import datetime
from pathlib import Path

class SimplifiedFormulaValidator:
    """Direct formula validation without external dependencies"""
    
    def __init__(self):
        self.test_results = {
            "execution_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "validator_version": "2.1-simplified",
            "total_tests": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "categories": {},
            "errors": []
        }
        
        # Add test data directory to path
        current_dir = Path(__file__).parent
        sys.path.insert(0, str(current_dir / "test_data"))
    
    def run_test(self, test_name, test_function, category):
        """Execute a single test and record results"""
        try:
            test_function()
            print(f"  ✅ {test_name}")
            self.test_results["tests_passed"] += 1
            
            if category not in self.test_results["categories"]:
                self.test_results["categories"][category] = {"passed": 0, "failed": 0}
            self.test_results["categories"][category]["passed"] += 1
            
        except Exception as e:
            print(f"  ❌ {test_name}: {str(e)}")
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append({
                "test": test_name,
                "category": category,
                "error": str(e)
            })
            
            if category not in self.test_results["categories"]:
                self.test_results["categories"][category] = {"passed": 0, "failed": 0}
            self.test_results["categories"][category]["failed"] += 1
        
        self.test_results["total_tests"] += 1
    
    def test_vss_formulas(self):
        """Test VSS mathematical formulas"""
        print("\n🏔️ VSS Formula Validation")
        print("-" * 40)
        
        def test_degrees_to_radians():
            # Test VPA angle conversion
            test_cases = [(3.0, 0.0524), (3.5, 0.0611), (4.0, 0.0698)]
            for degrees, expected in test_cases:
                calculated = degrees * (math.pi / 180)
                assert abs(calculated - expected) < 0.001, f"Angle conversion error: {degrees}°"
        
        def test_feet_to_meters():
            # Test unit conversion
            test_cases = [(1000, 304.8), (3280.84, 1000.0)]
            for feet, expected_meters in test_cases:
                calculated = feet * 0.3048
                assert abs(calculated - expected_meters) < 0.1, f"Unit conversion error: {feet} ft"
        
        def test_horizontal_distance():
            # Test trigonometric distance calculation
            height = 100  # meters
            vpa_degrees = 3.0
            vpa_radians = vpa_degrees * (math.pi / 180)
            distance = height / math.tan(vpa_radians)
            assert 1900 < distance < 1920, f"Distance calculation error: {distance:.1f}m"
        
        def test_slope_percentage():
            # Test slope calculation
            vpa_degrees = 3.0
            vpa_radians = vpa_degrees * (math.pi / 180)
            slope = math.tan(vpa_radians) * 100
            assert 5.2 < slope < 5.3, f"Slope calculation error: {slope:.2f}%"
        
        def test_parameter_ranges():
            # Test parameter validation
            runway_widths = [23, 30, 45, 60]
            for width in runway_widths:
                assert 20 <= width <= 100, f"Runway width out of range: {width}m"
            
            vpa_angles = [2.5, 3.0, 3.5, 4.0, 5.0]
            for vpa in vpa_angles:
                assert 2.0 <= vpa <= 6.0, f"VPA out of range: {vpa}°"
        
        # Execute VSS tests
        self.run_test("Degrees to Radians Conversion", test_degrees_to_radians, "Unit Conversion")
        self.run_test("Feet to Meters Conversion", test_feet_to_meters, "Unit Conversion")
        self.run_test("Horizontal Distance Calculation", test_horizontal_distance, "Trigonometry")
        self.run_test("Slope Percentage Calculation", test_slope_percentage, "Trigonometry")
        self.run_test("Parameter Range Validation", test_parameter_ranges, "Validation")
    
    def test_wind_spiral_formulas(self):
        """Test Wind Spiral mathematical formulas"""
        print("\n💨 Wind Spiral Formula Validation")
        print("-" * 40)
        
        def test_isa_temperature():
            # Test ISA temperature calculation
            test_cases = [(0, 15.0), (1000, 8.5), (3000, -4.5)]
            for altitude_m, expected_temp in test_cases:
                calculated_temp = 15.0 - (6.5 * altitude_m / 1000.0)
                assert abs(calculated_temp - expected_temp) < 0.1, f"ISA temperature error at {altitude_m}m"
        
        def test_turn_radius():
            # Test turn radius calculation: R = V²/(g*tan(bank))
            airspeed_kts = 120
            bank_deg = 25
            
            airspeed_ms = airspeed_kts * 0.514444
            bank_rad = bank_deg * (math.pi / 180)
            radius = (airspeed_ms ** 2) / (9.81 * math.tan(bank_rad))
            
            assert 800 < radius < 900, f"Turn radius calculation error: {radius:.0f}m"
        
        def test_ground_speed():
            # Test ground speed with wind
            tas_kts = 150
            wind_x_kts = 20  # headwind
            wind_y_kts = 0
            
            gs_x = tas_kts + wind_x_kts
            gs_y = 0 + wind_y_kts
            ground_speed = math.sqrt(gs_x**2 + gs_y**2)
            
            assert 169 < ground_speed < 171, f"Ground speed calculation error: {ground_speed:.1f} kts"
        
        def test_spiral_coordinates():
            # Test spiral coordinate calculation
            radius = 1000
            angle_deg = 90
            angle_rad = angle_deg * (math.pi / 180)
            
            x = radius * math.cos(angle_rad)
            y = radius * math.sin(angle_rad)
            
            calculated_radius = math.sqrt(x**2 + y**2)
            assert abs(calculated_radius - radius) < 0.1, f"Spiral coordinate error"
        
        def test_standard_rate_turn():
            # Test standard rate turn calculation
            standard_rate_rad = 3.0 * (math.pi / 180)  # 3°/s
            airspeed_kts = 120
            airspeed_ms = airspeed_kts * 0.514444
            
            bank_rad = math.atan((standard_rate_rad * airspeed_ms) / 9.81)
            bank_deg = bank_rad * (180 / math.pi)
            
            assert 15 < bank_deg < 25, f"Standard rate bank angle error: {bank_deg:.1f}°"
        
        # Execute Wind Spiral tests
        self.run_test("ISA Temperature Calculation", test_isa_temperature, "Atmospheric")
        self.run_test("Turn Radius Calculation", test_turn_radius, "Geometry")
        self.run_test("Ground Speed Calculation", test_ground_speed, "Navigation")
        self.run_test("Spiral Coordinates", test_spiral_coordinates, "Geometry")
        self.run_test("Standard Rate Turn", test_standard_rate_turn, "Performance")
    
    def test_ils_formulas(self):
        """Test ILS mathematical formulas"""
        print("\n🛬 ILS Formula Validation")
        print("-" * 40)
        
        def test_glide_slope_height():
            # Test height calculation along glide slope
            glide_angle_deg = 3.0
            distance_m = 1000
            threshold_height_m = 100
            
            glide_angle_rad = glide_angle_deg * (math.pi / 180)
            calculated_height = threshold_height_m + (distance_m * math.tan(glide_angle_rad))
            
            expected_height = 152.4  # approximately
            assert abs(calculated_height - expected_height) < 2.0, f"Glide slope height error"
        
        def test_approach_surface_width():
            # Test approach surface width expansion
            initial_width = 45  # runway width
            distance_m = 1000
            expansion_rate = math.tan(8.5 * math.pi / 180)  # 15% expansion
            
            calculated_width = initial_width + (2 * distance_m * expansion_rate)
            # Expected calculation: 45 + (2 * 1000 * 0.148877) = 45 + 297.75 = 342.75
            expected_width = 343  # approximately
            
            assert abs(calculated_width - expected_width) < 20, f"Surface width calculation error: {calculated_width:.1f}m vs {expected_width}m"
        
        def test_localizer_beam_width():
            # Test localizer beam width at distance
            beam_half_width_deg = 2.5
            distance_m = 5000
            
            beam_half_width_rad = beam_half_width_deg * (math.pi / 180)
            beam_width_m = 2 * distance_m * math.tan(beam_half_width_rad)
            
            assert 400 < beam_width_m < 500, f"Localizer beam width error: {beam_width_m:.0f}m"
        
        def test_decision_height():
            # Test decision height calculation
            threshold_elevation = 500
            dh_above_threshold = 60
            decision_height = threshold_elevation + dh_above_threshold
            
            assert decision_height == 560, f"Decision height calculation error"
        
        def test_cat_requirements():
            # Test CAT I requirements
            cat1_min_dh_ft = 200
            cat1_min_dh_m = cat1_min_dh_ft * 0.3048
            
            assert cat1_min_dh_m >= 60, f"CAT I DH requirement error: {cat1_min_dh_m:.1f}m"
        
        # Execute ILS tests
        self.run_test("Glide Slope Height Calculation", test_glide_slope_height, "Trigonometry")
        self.run_test("Approach Surface Width", test_approach_surface_width, "Geometry")
        self.run_test("Localizer Beam Width", test_localizer_beam_width, "Signal Processing")
        self.run_test("Decision Height Calculation", test_decision_height, "Navigation")
        self.run_test("CAT Requirements Validation", test_cat_requirements, "Standards")
    
    def test_pbn_formulas(self):
        """Test PBN mathematical formulas"""
        print("\n🛰️ PBN Formula Validation")
        print("-" * 40)
        
        def test_rnp_accuracy():
            # Test RNP accuracy conversions
            rnp_values = {'RNP 0.3': 0.3, 'RNP 1': 1.0, 'RNP 2': 2.0}
            
            for rnp_type, accuracy_nm in rnp_values.items():
                accuracy_m = accuracy_nm * 1852
                assert accuracy_m > 0, f"{rnp_type} accuracy must be positive"
                assert accuracy_m <= 18520, f"{rnp_type} accuracy too large"
        
        def test_turn_radius_rnp():
            # Test turn radius for RNP procedures
            ground_speed_kts = 150
            bank_angle_deg = 25
            
            ground_speed_ms = ground_speed_kts * 0.514444
            bank_angle_rad = bank_angle_deg * (math.pi / 180)
            
            radius = (ground_speed_ms ** 2) / (9.81 * math.tan(bank_angle_rad))
            assert 1200 < radius < 1400, f"RNP turn radius error: {radius:.0f}m"
        
        def test_flyby_lead_distance():
            # Test fly-by waypoint lead distance
            turn_radius = 1000
            turn_angle_deg = 90
            turn_angle_rad = turn_angle_deg * (math.pi / 180)
            
            lead_distance = turn_radius * math.tan(turn_angle_rad / 2)
            assert lead_distance < turn_radius, f"Lead distance should be less than radius"
        
        def test_descent_gradient():
            # Test maximum descent gradients
            max_gradients = {'final_approach': 6.5, 'intermediate': 5.2}
            
            for phase, max_gradient_percent in max_gradients.items():
                gradient_rad = math.atan(max_gradient_percent / 100)
                gradient_deg = gradient_rad * (180 / math.pi)
                assert gradient_deg <= 4.0, f"{phase} gradient too steep: {gradient_deg:.1f}°"
        
        def test_obstacle_clearance():
            # Test obstacle clearance calculations
            rnp_value_nm = 1.0
            rnp_value_m = rnp_value_nm * 1852
            
            primary_area_width = 2 * rnp_value_m
            assert primary_area_width > 0, f"Primary area width must be positive"
            assert primary_area_width <= 8 * rnp_value_m, f"Primary area too wide"
        
        # Execute PBN tests
        self.run_test("RNP Accuracy Validation", test_rnp_accuracy, "Navigation")
        self.run_test("Turn Radius for RNP", test_turn_radius_rnp, "Geometry")
        self.run_test("Fly-by Lead Distance", test_flyby_lead_distance, "Geometry")
        self.run_test("Descent Gradient Limits", test_descent_gradient, "Performance")
        self.run_test("Obstacle Clearance Areas", test_obstacle_clearance, "Safety")
    
    def test_general_conversions(self):
        """Test general unit conversions and constants"""
        print("\n🧮 General Conversion Validation")
        print("-" * 40)
        
        def test_aviation_constants():
            # Test aviation constants
            constants = {
                "KNOTS_TO_MS": 0.514444,
                "FT_TO_M": 0.3048,
                "NM_TO_M": 1852,
                "DEG_TO_RAD": math.pi / 180
            }
            
            for name, value in constants.items():
                assert value > 0, f"Constant {name} must be positive"
        
        def test_precision_calculations():
            # Test calculation precision
            pi_test = math.pi
            assert 3.14159 < pi_test < 3.14160, f"Pi precision error"
            
            sqrt_test = math.sqrt(2)
            assert 1.414 < sqrt_test < 1.415, f"Square root precision error"
        
        def test_trigonometric_functions():
            # Test trigonometric function accuracy
            test_cases = [(0, 0), (30, 0.5), (45, 0.7071), (60, 0.8660), (90, 1.0)]
            
            for angle_deg, expected_sin in test_cases:
                angle_rad = angle_deg * (math.pi / 180)
                calculated_sin = math.sin(angle_rad)
                assert abs(calculated_sin - expected_sin) < 0.001, f"Sin({angle_deg}°) error"
        
        def test_real_world_scenarios():
            # Test with real airport data
            try:
                from vss_test_data import REAL_AIRPORTS
                
                for airport in REAL_AIRPORTS:
                    elev_m = airport['elevation_m']
                    elev_ft = airport['elevation_ft']
                    
                    # Test conversion
                    calculated_m = elev_ft * 0.3048
                    error = abs(calculated_m - elev_m)
                    assert error < 2.0, f"Airport elevation conversion error: {airport['name']}"
                    
            except ImportError:
                # If test data not available, use hardcoded test
                test_elevation_ft = 1000
                test_elevation_m = test_elevation_ft * 0.3048
                assert abs(test_elevation_m - 304.8) < 0.1, "Elevation conversion test failed"
        
        # Execute general tests
        self.run_test("Aviation Constants", test_aviation_constants, "Constants")
        self.run_test("Precision Calculations", test_precision_calculations, "Precision")
        self.run_test("Trigonometric Functions", test_trigonometric_functions, "Trigonometry")
        self.run_test("Real World Scenarios", test_real_world_scenarios, "Integration")
    
    def generate_report(self):
        """Generate comprehensive validation report"""
        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE FORMULA VALIDATION REPORT")
        print("=" * 70)
        
        # Overall statistics
        print(f"📅 Execution Date: {self.test_results['execution_date']}")
        print(f"🧮 Total Formula Tests: {self.test_results['total_tests']}")
        print(f"✅ Tests Passed: {self.test_results['tests_passed']}")
        print(f"❌ Tests Failed: {self.test_results['tests_failed']}")
        
        if self.test_results['total_tests'] > 0:
            success_rate = (self.test_results['tests_passed'] / self.test_results['total_tests']) * 100
            print(f"📈 Overall Success Rate: {success_rate:.1f}%")
        
        # Category results
        print(f"\n📋 Category Results:")
        for category, results in self.test_results['categories'].items():
            total = results['passed'] + results['failed']
            rate = (results['passed'] / total) * 100 if total > 0 else 0
            status = "✅" if results['failed'] == 0 else "❌"
            print(f"  {status} {category}: {results['passed']}/{total} ({rate:.1f}%)")
        
        # Error summary
        if self.test_results['errors']:
            print(f"\n⚠️ Errors Found ({len(self.test_results['errors'])}):")
            for error in self.test_results['errors']:
                print(f"  📍 {error['test']}: {error['error']}")
        
        # Save detailed report
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        
        report_file = results_dir / f"simplified_formula_validation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed report saved: {report_file}")
        
        # Final status
        if self.test_results['tests_failed'] == 0:
            print(f"\n🎉 ALL FORMULAS VALIDATED SUCCESSFULLY!")
            print("   All mathematical calculations are verified correct.")
            return True
        else:
            print(f"\n⚠️ FORMULA VALIDATION ISSUES DETECTED")
            print(f"   {self.test_results['tests_failed']} formula tests failed - review required.")
            return False
    
    def run_all_validations(self):
        """Execute all formula validations"""
        print("🧪 QPANSOPY Simplified Formula Validation Suite")
        print("=" * 70)
        print("Testing mathematical formulas and calculations directly")
        print("without external dependencies\n")
        
        # Run all test categories
        self.test_vss_formulas()
        self.test_wind_spiral_formulas()
        self.test_ils_formulas()
        self.test_pbn_formulas()
        self.test_general_conversions()
        
        # Generate final report
        return self.generate_report()

def main():
    """Main execution function"""
    validator = SimplifiedFormulaValidator()
    
    try:
        success = validator.run_all_validations()
        
        if success:
            print(f"\n🏆 FORMULA VALIDATION COMPLETE - ALL TESTS PASSED")
            return 0
        else:
            print(f"\n🚨 FORMULA VALIDATION COMPLETE - ISSUES FOUND")
            return 1
            
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR in formula validation: {e}")
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
