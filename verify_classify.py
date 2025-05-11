import requests
import json
import os

API_BASE_URL = "http://localhost:8000" # Your FastAPI server URL
CLASSIFY_ENDPOINT = f"{API_BASE_URL}/classify"

# --- !!! USER: FILL THIS SECTION CAREFULLY !!! ---
# Define the expected outputs for your test images.
# Use 'None' for feature values that are expected to be "not found" by the API.
EXPECTED_DATA = [
    {
        "file_path": "images/WALicense.png",
        "expected_document_type": "drivers_license",
        "expected_features": {
            "license_number": "TIKEKY448KS",
            "date_of_birth": "1996-05-10",
            "issue_date": "2017-11-22",
            "expiration_date": "2023-05-10",
            "first_name": "TIKE",
            "last_name": "DOE",
        }
    },
    {
        "file_path": "images/EADSample.jpg",
        "expected_document_type": "ead_card",
        "expected_features": {
            "card_number": "SRC0000000773",
            "category": "C09",
            "card_expires_date": "2011-05-10",
            "last_name": "SPECIMEN",
            "first_name": "TEST",
        }
    },
    {
        "file_path": "images/UKPassport.jpg",
        "expected_document_type": "passport",
        "expected_features": {
            "full_name": "ANGELA ZOE UK SPECIMEN",
            "date_of_birth": "1988-12-04",
            "country": "GBR",
            "issue_date": "2010-11-05",
            "expiration_date": "2020-11-05",
        }
    },
]

def print_test_header(test_case_num, file_path):
    print(f"\n--- Test Case {test_case_num}: {file_path} ---")

def print_status(message, success=True):
    prefix = "✅" if success else "❌"
    print(f"  {prefix} {message}")

def compare_values(field_name, response_value, expected_value):
    if response_value == expected_value:
        print_status(f"{field_name}: Matches ('{response_value}')")
        return True
    else:
        print_status(f"{field_name}: Mismatch - Got '{response_value}', Expected '{expected_value}'", success=False)
        return False

def run_tests():
    passed_tests = 0
    failed_tests = 0
    total_tests = len(EXPECTED_DATA)

    print(f"Starting API tests for {CLASSIFY_ENDPOINT}...")
    print(f"Found {total_tests} test case(s).")

    for i, test_case in enumerate(EXPECTED_DATA):
        test_case_num = i + 1
        file_path = test_case["file_path"]
        expected_doc_type = test_case["expected_document_type"]
        expected_features = test_case["expected_features"]
        expected_filename = os.path.basename(file_path)

        print_test_header(test_case_num, file_path)

        if not os.path.exists(file_path):
            print_status(f"File not found at '{file_path}'. Skipping test.", success=False)
            failed_tests += 1
            continue

        current_test_passed_all_checks = True

        try:
            with open(file_path, 'rb') as f:
                files = {'image': (expected_filename, f, 'image/png')} # Adjust mime type if needed, though server checks PIL
                
                print(f"  Attempting to POST {file_path} to {CLASSIFY_ENDPOINT}...")
                response = requests.post(CLASSIFY_ENDPOINT, files=files, timeout=60) # Increased timeout for LLM calls

            print(f"  Response Status Code: {response.status_code}")

            if response.status_code == 200:
                try:
                    response_data = response.json()
                    # print(f"  Raw Response Data: {json.dumps(response_data, indent=2)}") # Uncomment for debugging

                    # 1. Check Document Type
                    if not compare_values("Document Type", response_data.get("document_type"), expected_doc_type):
                        current_test_passed_all_checks = False

                    # 2. Check Original Filename (server derives this)
                    if not compare_values("Original Filename", response_data.get("original_filename"), expected_filename):
                        current_test_passed_all_checks = False
                    
                    # 3. Check Features
                    response_features = response_data.get("features", {})
                    print("  Comparing Features:")
                    feature_comparison_passed = True
                    for key, expected_value in expected_features.items():
                        if key not in response_features:
                            print_status(f"  Feature '{key}': Missing in response (expected: '{expected_value}')", success=False)
                            feature_comparison_passed = False
                        elif not compare_values(f"  Feature '{key}'", response_features[key], expected_value):
                            feature_comparison_passed = False
                    
                    if not feature_comparison_passed:
                        current_test_passed_all_checks = False
                    
                    # Check for unexpected extra keys in response features (optional, can be strict)
                    # for key in response_features:
                    #     if key not in expected_features:
                    #         print_status(f"  Feature '{key}': Unexpected extra feature in response (value: '{response_features[key]}')", success=False)
                    #         current_test_passed_all_checks = False # Make this a failure if strictness is desired

                except json.JSONDecodeError:
                    print_status("Failed to decode JSON response from server.", success=False)
                    current_test_passed_all_checks = False
                except KeyError as e:
                    print_status(f"KeyError in response: {e}. Response might not have expected structure.", success=False)
                    print(f"  Response content: {response.text}")
                    current_test_passed_all_checks = False
            else:
                print_status(f"API request failed with status {response.status_code}.", success=False)
                try:
                    error_detail = response.json().get("detail", response.text)
                    print(f"    Error Detail: {error_detail}")
                except json.JSONDecodeError:
                    print(f"    Error Content: {response.text}")
                current_test_passed_all_checks = False
        
        except requests.exceptions.ConnectionError:
            print_status(f"Connection Error: Could not connect to the server at {CLASSIFY_ENDPOINT}. Is it running?", success=False)
            current_test_passed_all_checks = False
            # Stop further tests if server is not reachable
            failed_tests += (total_tests - i) 
            break 
        except Exception as e:
            print_status(f"An unexpected error occurred during the test: {e}", success=False)
            current_test_passed_all_checks = False

        if current_test_passed_all_checks:
            passed_tests += 1
            print("  --- Test Case Result: PASSED ---")
        else:
            failed_tests += 1
            print("  --- Test Case Result: FAILED ---")


    print("\n--- Test Summary ---")
    print(f"Total tests run: {passed_tests + failed_tests} out of {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print("--------------------")

if __name__ == "__main__":
    run_tests()
