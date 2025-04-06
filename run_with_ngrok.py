import subprocess
import time
from pyngrok import ngrok

# Start the Django server in the background
django_process = subprocess.Popen(["python", "manage.py", "runserver", "8000"])

# Open an ngrok tunnel to the Django server
public_url = ngrok.connect(8000).public_url
print(f"\n* ngrok tunnel opened at {public_url}")
print("* Access your app through this URL to use geolocation features")

# Keep the process running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    # Close the ngrok tunnel on Ctrl+C
    print("* Closing ngrok tunnel and Django server...")
    ngrok.kill()
    django_process.terminate() 