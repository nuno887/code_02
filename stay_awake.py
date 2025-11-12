# Keeps the PC from sleeping while this script is running.
# Stop it with Ctrl+C or by closing the window.

import ctypes, time

ES_CONTINUOUS      = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040  # optional; keeps system active without waking display

# Enable stay-awake
ctypes.windll.kernel32.SetThreadExecutionState(
    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
)

print("Staying awake... (Ctrl+C to stop)")
try:
    while True:
        time.sleep(60)
finally:
    # Restore normal behavior when this script exits
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    print("Sleep behavior restored.")
