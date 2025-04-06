from django import template
from blockchain.driver_verification import DriverBlockchain
from datetime import datetime

register = template.Library()

@register.simple_tag
def verify_driver_blockchain(driver):
    """
    Verify driver on blockchain and return verification status
    """
    # First check the stored verification status
    if driver.blockchain_verified:
        return True
        
    # If not verified, try to verify on blockchain
    return driver.verify_on_blockchain() 