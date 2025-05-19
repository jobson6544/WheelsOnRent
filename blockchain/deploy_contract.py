from web3 import Web3
from solcx import compile_source
import os
import sys
import json
from django.conf import settings

# Add the project directory to path so Django settings can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wheelsonrent.settings")

import django
django.setup()

# Driver verification contract
DRIVER_CONTRACT_SOURCE = '''
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract DriverVerification {
    struct Driver {
        string hash;
        uint256 timestamp;
    }
    
    mapping(string => Driver) public drivers;
    
    event DriverRegistered(string driverId, uint256 timestamp);
    
    function registerDriver(string memory driverId, string memory driverHash) public {
        drivers[driverId] = Driver(driverHash, block.timestamp);
        emit DriverRegistered(driverId, block.timestamp);
    }
    
    function verifyDriver(string memory driverId, string memory driverHash) public view returns (bool) {
        return (keccak256(abi.encodePacked(drivers[driverId].hash)) == 
                keccak256(abi.encodePacked(driverHash))) && drivers[driverId].timestamp > 0;
    }
}
'''

def deploy_contract():
    try:
        # Connect to Ethereum network
        w3 = Web3(Web3.HTTPProvider(settings.ETHEREUM_NODE_URL))
        
        # Verify connection
        if not w3.is_connected():
            print("Failed to connect to Ethereum network")
            return
        
        print(f"Connected to Ethereum network at {settings.ETHEREUM_NODE_URL}")
        
        # Account setup
        account_address = settings.ETHEREUM_ACCOUNT_ADDRESS
        private_key = settings.ETHEREUM_PRIVATE_KEY
        
        # Compile contract
        print("Compiling contract...")
        compiled_sol = compile_source(DRIVER_CONTRACT_SOURCE, output_values=['abi', 'bin'])
        contract_id, contract_interface = compiled_sol.popitem()
        
        bytecode = contract_interface['bin']
        abi = contract_interface['abi']
        
        # Deploy contract
        print(f"Deploying contract from address: {account_address}")
        
        # Get contract factory
        DriverVerification = w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Get nonce
        nonce = w3.eth.get_transaction_count(account_address)
        
        # Build transaction
        transaction = DriverVerification.constructor().build_transaction({
            'chainId': 1337,
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'from': account_address
        })
        
        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
        
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(f"Transaction sent: {tx_hash.hex()}")
        
        # Wait for transaction receipt
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        contract_address = tx_receipt['contractAddress']
        
        print(f"Contract deployed at address: {contract_address}")
        print("\nUpdate the DRIVER_CONTRACT_ADDRESS in settings.py with this address.")
        
        # Save ABI to a file for later use
        abi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'contract_abi.json')
        with open(abi_path, 'w') as f:
            json.dump(abi, f)
        
        print(f"Contract ABI saved to {abi_path}")
        
        return contract_address, abi
        
    except Exception as e:
        print(f"Error deploying contract: {str(e)}")
        return None, None

if __name__ == "__main__":
    print("Deploying Driver Verification Contract...")
    contract_address, abi = deploy_contract()
    if contract_address:
        print("\nDeployment successful!")
    else:
        print("\nDeployment failed.") 