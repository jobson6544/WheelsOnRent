from web3 import Web3
from eth_account import Account
import json
from datetime import datetime
from django.conf import settings
import hashlib
import logging

logger = logging.getLogger(__name__)

class DriverBlockchain:
    def __init__(self):
        """Initialize blockchain connection and contract"""
        try:
            # Connect to Ethereum network (using environment variable)
            self.w3 = Web3(Web3.HTTPProvider(settings.ETHEREUM_NODE_URL))
            
            # Verify connection
            if not self.w3.is_connected():
                raise ConnectionError("Failed to connect to Ethereum network")
            
            # Initialize contract
            self.contract_address = settings.DRIVER_CONTRACT_ADDRESS
            self.contract_abi = settings.DRIVER_CONTRACT_ABI
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            
            # Set account
            self.account_address = settings.ETHEREUM_ACCOUNT_ADDRESS
            
        except Exception as e:
            logger.error(f"Blockchain initialization error: {str(e)}")
            raise
    
    def create_driver_hash(self, driver_data):
        """
        Create a unique hash of driver's critical information
        
        Args:
            driver_data (dict): Dictionary containing driver information
                              (license_number, full_name, dob)
        Returns:
            str: SHA256 hash of driver data
        """
        try:
            data_string = (
                f"{driver_data['license_number']}"
                f"{driver_data['full_name']}"
                f"{driver_data['dob']}"
            )
            return hashlib.sha256(data_string.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error creating driver hash: {str(e)}")
            raise
    
    def verify_driver(self, driver_id, driver_data):
        """
        Verify driver's information on blockchain
        
        Args:
            driver_id (str): Unique identifier for the driver
            driver_data (dict): Driver's information to verify
        
        Returns:
            bool: True if driver is verified, False otherwise
        """
        try:
            driver_hash = self.create_driver_hash(driver_data)
            
            # Call the smart contract to verify driver
            is_verified = self.contract.functions.verifyDriver(
                driver_id,
                driver_hash
            ).call()
            
            logger.info(f"Driver {driver_id} verification status: {is_verified}")
            return is_verified
            
        except Exception as e:
            logger.error(f"Driver verification error: {str(e)}")
            return False
    
    def register_driver(self, driver_id, driver_data):
        """
        Register new driver on blockchain
        
        Args:
            driver_id (str): Unique identifier for the driver
            driver_data (dict): Driver's information to register
        
        Returns:
            dict: Transaction receipt if successful, None otherwise
        """
        try:
            driver_hash = self.create_driver_hash(driver_data)
            
            # Get nonce (transaction count)
            nonce = self.w3.eth.get_transaction_count(self.account_address)
            
            # Build transaction (using legacy transaction format for Ganache)
            transaction = self.contract.functions.registerDriver(
                driver_id,
                driver_hash
            ).build_transaction({
                'chainId': 1337,  # Default Ganache chainId
                'gas': 2000000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'from': self.account_address
            })
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                transaction,
                settings.ETHEREUM_PRIVATE_KEY
            )
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"Driver {driver_id} registered on blockchain. Transaction hash: {tx_hash.hex()}")
            return tx_receipt
            
        except Exception as e:
            logger.error(f"Driver registration error: {str(e)}")
            return None
    
    def get_driver_registration_time(self, driver_id):
        """
        Get the timestamp when a driver was registered
        
        Args:
            driver_id (str): Unique identifier for the driver
        
        Returns:
            datetime: Registration timestamp if found, None otherwise
        """
        try:
            driver_info = self.contract.functions.drivers(driver_id).call()
            if driver_info[1] > 0:  # timestamp exists
                return datetime.fromtimestamp(driver_info[1])
            return None
        except Exception as e:
            logger.error(f"Error getting driver registration time: {str(e)}")
            return None 