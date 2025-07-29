#!/usr/bin/env python3
"""
Simple script to verify that the FastAPI app is correctly serving the frontend SPA routes.
This simulates requests to different routes to ensure they return the index.html file.
"""

import requests
import sys
import os

def check_route(base_url, route):
    """Check if a route returns the index.html content instead of 404"""
    url = f"{base_url.rstrip('/')}/{route.lstrip('/')}"
    print(f"Testing route: {url}")
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                print(f"✅ Route {route} returns HTML (status {response.status_code})")
                return True
            else:
                print(f"❌ Route {route} returns non-HTML content: {content_type}")
                return False
        else:
            print(f"❌ Route {route} returns status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing route {route}: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_routes.py <base_url>")
        print("Example: python check_routes.py https://terminus-aw4s.onrender.com")
        sys.exit(1)
    
    base_url = sys.argv[1]
    
    # Test routes
    routes_to_test = [
        "/",
        "/login",
        "/register",
        "/dashboard",
        "/ide",
        "/about",
        "/nonexistent-route-123"
    ]
    
    success_count = 0
    for route in routes_to_test:
        if check_route(base_url, route):
            success_count += 1
    
    print(f"\nResults: {success_count}/{len(routes_to_test)} routes passed")
    
    if success_count == len(routes_to_test):
        print("✅ All routes are working correctly!")
        return 0
    else:
        print("❌ Some routes failed the test")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 