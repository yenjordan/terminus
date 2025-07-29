# Data Science Libraries in Terminus

This document explains how pandas and scipy libraries have been configured to be available in every terminal session.

## Configuration Overview

The following changes have been made to ensure pandas and scipy are available in every terminal session:

1. **Added to requirements.txt**: pandas and scipy are now part of the project's dependencies
2. **Pre-installed in Docker image**: The Dockerfile now includes explicit installation of pandas, scipy, and numpy
3. **Auto-configured in terminal sessions**: Each terminal session automatically checks for and installs these libraries if needed
4. **Python startup configuration**: A Python startup file is created to auto-import these libraries

## Verifying the Setup

You can verify that pandas and scipy are properly installed and available using the provided verification script:

```bash
# Run the verification script
python3 verify_libraries.py
```

This script will:
- Check if pandas, scipy, and numpy are installed
- Display their versions
- Run a simple pandas test to confirm functionality

## Manual Verification

You can also manually verify the setup by running Python in any terminal session:

```bash
# Start Python
python3

# Import and use pandas
import pandas as pd
df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
print(df)

# Import and use scipy
import scipy as sp
print(sp.__version__)
```

## Troubleshooting

If the libraries are not available in a terminal session, you can manually install them:

```bash
pip install pandas scipy numpy
```

If you're using Docker, ensure you rebuild the Docker image after making changes to the Dockerfile:

```bash
docker-compose build --no-cache backend
docker-compose up -d
```

## Additional Information

- The Python environment is configured to automatically import pandas (as pd), scipy (as sp), and numpy (as np) when starting Python
- These libraries are installed system-wide in the Docker container
- Each user's terminal session also has a local .bashrc file that ensures these libraries are available 