import os
import subprocess

# Change to the project directory
project_dir = "/home/pi/TabSort-master 0.1"
os.chdir(project_dir)

# Make the shell script executable
os.system("chmod +x run_tabsort.sh")

# Launch the shell script in the GUI environment
subprocess.Popen(["/bin/bash", "-c", "DISPLAY=:0 ./run_tabsort.sh"])
