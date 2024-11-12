
import pytest
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.alert import Alert

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TestDeactivateUser:
    def setup_method(self, method):
        # Initialize the browser (Chrome in this case)
        self.driver = webdriver.Chrome()
        self.vars = {}

    def teardown_method(self, method):
        # Close the browser after the test
        self.driver.quit()

    def test_deactivateuser(self):
        try:
            logging.info("Navigating to admin login page")
            self.driver.get("http://127.0.0.1:8000/adminapp/login/")
            self.driver.set_window_size(1060, 800)

            logging.info("Entering login credentials")
            self.driver.find_element(By.ID, "yourEmail").click()
            self.driver.find_element(By.ID, "yourEmail").send_keys("admin@gmail.com")
            self.driver.find_element(By.ID, "yourPassword").send_keys("admin")
            self.driver.find_element(By.CSS_SELECTOR, ".btn").click()

            # Wait for the user management link to be clickable and click on it
            logging.info("Navigating to user management section")
            user_management_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#sidebar-nav > .nav-item:nth-child(3) > .nav-link > span"))
            )
            user_management_button.click()

            # Wait for the first user in the list to be clickable and click on it
            self.driver.find_element(By.CSS_SELECTOR, "#forms-nav > li:nth-child(1) span").click()

            logging.info("Selecting first user to deactivate")
            first_user_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "tr:nth-child(1) .btn"))
            )
            first_user_button.click()

            logging.info("Confirming deactivation of user")
            # Wait for the alert to appear and confirm the deactivation
            alert = WebDriverWait(self.driver, 10).until(EC.alert_is_present())
            assert alert.text == "Are you sure you want to deactivate this customer?"
            alert.accept()

            logging.info("User deactivated successfully")

            # Close the dropdown and logout
            self.driver.find_element(By.CSS_SELECTOR, ".d-md-block").click()
            self.driver.find_element(By.CSS_SELECTOR, ".dropdown-menu > .nav-item span").click()

            logging.info("Test Passed: User deactivated successfully")
        except Exception as e:
            logging.error(f"TEST FAILED: {str(e)}")
            raise