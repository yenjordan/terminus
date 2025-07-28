#!/usr/bin/env python3
"""
script to check if pandas and scipy are properly installed/available.
"""

import sys
import importlib.util
import time

def check_library(name):
    """check if a library is installed and available."""
    print(f"Checking for {name}... ", end="", flush=True)
    spec = importlib.util.find_spec(name)
    
    if spec is None:
        print("\033[91mNOT FOUND\033[0m")
        return False
    
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        version = getattr(module, "__version__", "unknown")
        print(f"\033[92mOK\033[0m (version {version})")
        return True
    except Exception as e:
        print(f"\033[91mERROR\033[0m ({str(e)})")
        return False

def main():
    """function to check libraries."""
    print("\n\033[1mVerifying Python Data Science Libraries\033[0m")
    print("=" * 40)
    print(f"Python version: {sys.version}")
    print("-" * 40)
    
    libraries = ["pandas", "scipy", "numpy"]
    
    optional_libraries = ["matplotlib", "scikit-learn", "seaborn"]
    
    all_found = True
    for lib in libraries:
        if not check_library(lib):
            all_found = False
    
    print("\n\033[1mOptional Libraries:\033[0m")
    for lib in optional_libraries:
        check_library(lib)
    
    print("\n\033[1mSummary:\033[0m")
    if all_found:
        print("\033[92mAll required libraries are installed and working!\033[0m")
    else:
        print("\033[91mSome required libraries are missing or not working properly.\033[0m")
        print("Try running the following commands to install them:")
        print("  pip install pandas scipy numpy")
    
    try:
        print("\n\033[1mRunning a simple pandas test:\033[0m")
        import pandas as pd
        import numpy as np
        
        df = pd.DataFrame({
            'A': np.random.rand(5),
            'B': np.random.rand(5),
            'C': np.random.rand(5)
        })
        
        print("\nSample DataFrame:")
        print(df)
        print("\nDataFrame info:")
        print(df.info())
        print("\nDataFrame description:")
        print(df.describe())
        
        print("\n\033[92mPandas test completed successfully!\033[0m")
    except Exception as e:
        print(f"\n\033[91mPandas test failed: {str(e)}\033[0m")

if __name__ == "__main__":
    main() 