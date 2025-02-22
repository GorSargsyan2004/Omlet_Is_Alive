import sys
import os
import gzip
import shutil
import datetime
import threading
import time

# Define log directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the folder exists

# Function to get the log file name based on the date
def get_log_filename():
    return os.path.join(LOG_DIR, datetime.datetime.now().strftime("%d-%m-%Y.log"))

# Function to compress a file into .gz
def compress_log_file(log_file):
    compressed_file = log_file + ".gz"
    with open(log_file, "rb") as f_in, gzip.open(compressed_file, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(log_file)  # Delete original log after compression

# Class to handle log rotation
class DailyLogger:
    def __init__(self):
        self.log_file = get_log_filename()
        self.log_stream = open(self.log_file, "a", encoding="utf-8")
        sys.stdout = self  # Redirect print() to this class
        self.start_log_rotation()

    def write(self, message):
        """Write output to both console and log file."""
        self.log_stream.write(message)
        self.log_stream.flush()  # Ensure immediate write
        sys.__stdout__.write(message)  # Print to real console

    def flush(self):
        """Required for compatibility with sys.stdout."""
        self.log_stream.flush()

    def start_log_rotation(self):
        """Check and rotate logs at midnight."""
        def rotate_logs():
            while True:
                now = datetime.datetime.now()
                next_midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                sleep_time = (next_midnight - now).total_seconds()
                time.sleep(sleep_time)

                # Create a new log file before compressing the old one
                new_log_file = get_log_filename()
                new_log_stream = open(new_log_file, "a", encoding="utf-8")

                # Swap log files safely
                old_log_file = self.log_file
                old_log_stream = self.log_stream
                self.log_file = new_log_file
                self.log_stream = new_log_stream
                sys.stdout = self

                # Now close and compress the old log file
                old_log_stream.close()
                compress_log_file(old_log_file)

        threading.Thread(target=rotate_logs, daemon=True).start()


