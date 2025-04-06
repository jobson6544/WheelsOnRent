from web3 import Web3
import json
import os
from pathlib import Path
from dotenv import load_dotenv
import sys

def deploy_contract():
    try:
        # Load environment variables
        load_dotenv()
        
        print("Starting contract deployment process...")
        
        # Connect to local Ethereum network
        w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
        
        # Check connection
        if not w3.is_connected():
            raise Exception("Could not connect to Ethereum network")
        
        print("Connected to Ethereum network")
        
        # Set default account
        account_address = os.getenv('ETHEREUM_ACCOUNT_ADDRESS')
        private_key = os.getenv('ETHEREUM_PRIVATE_KEY')
        
        if not account_address or not private_key:
            raise Exception("Missing ETHEREUM_ACCOUNT_ADDRESS or ETHEREUM_PRIVATE_KEY in .env")
            
        print(f"Using account: {account_address}")
        
        # Check account balance
        balance = w3.eth.get_balance(account_address)
        print(f"Account balance: {w3.from_wei(balance, 'ether')} ETH")
        
        if balance == 0:
            raise Exception("Account has no ETH balance")
        
        # Get the absolute path of the current script
        current_dir = Path(__file__).resolve().parent
        contract_path = current_dir / 'contracts' / 'DriverVerification.sol'
        abi_path = current_dir / 'contracts' / 'DriverVerification.abi'
        
        print(f"Contract path: {contract_path}")
        print(f"ABI path: {abi_path}")
        
        if not contract_path.exists():
            raise Exception(f"Contract file not found at {contract_path}")
        if not abi_path.exists():
            raise Exception(f"ABI file not found at {abi_path}")
        
        # Read the Solidity contract file
        with open(contract_path, 'r') as file:
            contract_source = file.read()
            
        # Read the ABI file
        with open(abi_path, 'r') as file:
            contract_abi = json.load(file)
            
        print("Contract files loaded successfully")
        
        # Compile the contract using solcx
        from solcx import compile_source, install_solc, get_installed_solc_versions
        
        # Install specific Solidity version if not already installed
        print("Checking Solidity compiler...")
        if '0.8.0' not in [str(v) for v in get_installed_solc_versions()]:
            print("Installing Solidity compiler 0.8.0...")
            install_solc('0.8.0')
        
        # Compile the contract
        print("Compiling contract...")
        compiled_sol = compile_source(
            contract_source,
            output_values=['abi', 'bin'],
            solc_version='0.8.0'
        )
        
        contract_id, contract_interface = compiled_sol.popitem()
        bytecode = contract_interface['bin']
        abi = contract_interface['abi']
        
        print("Contract compiled successfully")
        
        # Deploy the contract
        print("Deploying contract...")
        Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Get nonce
        nonce = w3.eth.get_transaction_count(account_address)
        
        # Estimate gas
        gas_estimate = Contract.constructor().estimate_gas({'from': account_address})
        gas_price = w3.eth.gas_price
        
        print(f"Estimated gas: {gas_estimate}")
        print(f"Gas price: {gas_price}")
        print(f"Total cost: {w3.from_wei(gas_estimate * gas_price, 'ether')} ETH")
        
        # Build the transaction
        transaction = Contract.constructor().build_transaction({
            'chainId': 1337,  # Default Ganache chainId
            'gas': gas_estimate,
            'gasPrice': gas_price,
            'nonce': nonce,
            'from': account_address
        })
        
        # Sign the transaction
        signed_txn = w3.eth.account.sign_transaction(
            transaction,
            private_key
        )
        
        print("Sending transaction...")
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        # Wait for the transaction to be mined
        print("Waiting for contract deployment...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"Contract deployed successfully!")
        print(f"Contract address: {tx_receipt.contractAddress}")
        
        # Update .env file with contract address
        env_path = current_dir.parent / '.env'
        if not env_path.exists():
            raise Exception(f".env file not found at {env_path}")
            
        with open(env_path, 'r') as file:
            env_content = file.read()
        
        # Update contract address
        if 'DRIVER_CONTRACT_ADDRESS' in env_content:
            # Replace existing value
            start = env_content.find('DRIVER_CONTRACT_ADDRESS=')
            end = env_content.find('\n', start)
            if end == -1:  # If it's the last line
                end = len(env_content)
            env_content = env_content[:start] + f'DRIVER_CONTRACT_ADDRESS={tx_receipt.contractAddress}' + env_content[end:]
        else:
            # Add new value
            env_content += f'\nDRIVER_CONTRACT_ADDRESS={tx_receipt.contractAddress}'
        
        with open(env_path, 'w') as file:
            file.write(env_content)
        
        print("Updated .env file with contract address")
        
        return tx_receipt.contractAddress
        
    except Exception as e:
        print(f"\nError during deployment:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print("\nStack trace:")
        import traceback
        traceback.print_exc()
        raise

if __name__ == '__main__':
    try:
        contract_address = deploy_contract()
        print(f"\nDeployment successful! Contract address: {contract_address}")
        print("\nNext steps:")
        print("1. Make sure Ganache is still running")
        print("2. Run 'python manage.py register_drivers' to register existing drivers")
    except Exception as e:
        print("\nDeployment failed. Please check the error messages above.") 