# Generated by Selenium IDE
import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
import sys

class TestVendorregister():
    def setup_method(self, method):
        print("\n\033[94m=== Starting Vendor Registration Test ===\033[0m")  # Blue color
        try:
            self.driver = webdriver.Chrome()
            print("\033[92m✓ Browser initialized successfully\033[0m")  # Green color
        except WebDriverException as e:
            print(f"\033[91m✗ Failed to initialize browser: {str(e)}\033[0m")  # Red color
            raise
        self.vars = {}
  
    def teardown_method(self, method):
        try:
            self.driver.quit()
            print("\033[92m✓ Browser closed successfully\033[0m")
        except Exception as e:
            print(f"\033[91m✗ Failed to close browser: {str(e)}\033[0m")
        print("\033[94m=== Vendor Registration Test Completed ===\033[0m")
  
    def test_vendorregister(self):
        try:
            # Navigate to homepage
            self.driver.get("http://127.0.0.1:8000/")
            print("\033[92m✓ Navigated to homepage\033[0m")
            
            # Set window size (increased height)
            self.driver.set_window_size(1055, 1000)  # Increased height
            print("\033[92m✓ Window size set\033[0m")
            
            # Click vendor login link
            self.driver.find_element(By.LINK_TEXT, "Vendor Login").click()
            print("\033[92m✓ Clicked vendor login link\033[0m")
            
            # Click signup link
            self.driver.find_element(By.LINK_TEXT, "Signup").click()
            print("\033[92m✓ Clicked signup link\033[0m")
            
            try:
                wait = WebDriverWait(self.driver, 10)
                
                # Fill registration form
                email_field = self.driver.find_element(By.ID, "id_email")
                email_field.send_keys("testvendor@gmail.com")
                print("\033[92m✓ Entered email\033[0m")
                
                username_field = self.driver.find_element(By.ID, "id_username")
                username_field.click()
                username_field.send_keys("testuser1")
                print("\033[92m✓ Entered username\033[0m")
                
                fullname_field = self.driver.find_element(By.ID, "id_full_name")
                fullname_field.click()
                fullname_field.send_keys("test user1")
                print("\033[92m✓ Entered full name\033[0m")
                
                password1_field = self.driver.find_element(By.ID, "id_password1")
                password1_field.click()
                password1_field.send_keys("Jobzz@6544")
                print("\033[92m✓ Entered password\033[0m")
                
                password2_field = self.driver.find_element(By.ID, "id_password2")
                password2_field.send_keys("Jobzz@6544")
                print("\033[92m✓ Confirmed password\033[0m")
                
                # Submit registration form
                submit_button = self.driver.find_element(By.CSS_SELECTOR, "button")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                time.sleep(1)  # Wait for scroll
                submit_button.click()
                print("\033[92m✓ Submitted registration form\033[0m")
                
                # Wait for business details form
                time.sleep(2)  # Add small delay for form transition
                
                # Fill business details
                business_name = wait.until(EC.presence_of_element_located((By.ID, "id_business_name")))
                business_name.click()
                business_name.send_keys("RentWithUs")
                print("\033[92m✓ Entered business name\033[0m")
                
                address_field = self.driver.find_element(By.ID, "id_full_address")
                address_field.click()
                address_field.send_keys("kottayam")
                print("\033[92m✓ Entered business address\033[0m")
                
                # Submit business details - with scroll and wait
                submit_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn-secondary")))
                self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                time.sleep(1)  # Wait for scroll
                
                # Try different methods to click the button
                try:
                    submit_button.click()
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", submit_button)
                    except:
                        actions = ActionChains(self.driver)
                        actions.move_to_element(submit_button).click().perform()
                        
                print("\033[92m✓ Submitted business details\033[0m")
                
                print("\n\033[92m✓ TEST PASSED: Vendor registration completed successfully\033[0m")
                
            except Exception as e:
                print(f"\033[91m✗ Form filling failed: {str(e)}\033[0m")
                raise
                
        except Exception as e:
            print(f"\n\033[91m✗ TEST FAILED: {str(e)}\033[0m")
            # Take screenshot on failure
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            self.driver.save_screenshot(f'test_failure_{timestamp}.png')
            print(f"\033[93mScreenshot saved as test_failure_{timestamp}.png\033[0m")
            raise

def run_test():
    """Function to run the test and handle exceptions"""
    test = TestVendorregister()
    try:
        test.setup_method(None)
        test.test_vendorregister()
        return True
    except Exception as e:
        print(f"\n\033[91mTest execution failed: {str(e)}\033[0m")
        return False
    finally:
        test.teardown_method(None)

if __name__ == "__main__":
    success = run_test()
    if success:
        print("\n\033[92mAll tests completed successfully!\033[0m")
        sys.exit(0)
    else:
        print("\n\033[91mTest execution failed!\033[0m")
        sys.exit(1)
  
