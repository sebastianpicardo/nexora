import os
import subprocess
import sys
import time

# Set up environment
env = dict(os.environ)
env['DATABASE_URL'] = 'sqlite:///./test.db'
env['SUPABASE_URL'] = ''
env['SUPABASE_SERVICE_ROLE_KEY'] = ''
env['SECRET_KEY'] = 'test-jwt-secret'
env['SESSION_SECRET'] = 'test-session-secret'
env['APP_ENV'] = 'test'
env['STORAGE_BACKEND'] = 'local'

# Kill any existing python processes on port 8001
subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
time.sleep(2)

# Start the server
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'src.main:app', '--port', '8001', '--host', '0.0.0.0'],
    cwd=r'D:\Nexora', env=env
)
print('Server PID:', proc.pid)

# Wait for server to start
time.sleep(8)

# Test if server is up
try:
    import urllib.request
    r = urllib.request.urlopen('http://127.0.0.1:8001/api/auth/config', timeout=5)
    print('Server is up!')
    print(r.read().decode()[:200])
except Exception as e:
    print('Server not ready:', e)
    proc.terminate()