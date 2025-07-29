#!/bin/bash
set -e

# Navigate to frontend directory
cd frontend

# Create a simple script to find all API calls
echo "Finding all API calls in the codebase..."
grep -r "fetch(" --include="*.tsx" --include="*.ts" src/

# Create a build with debug information
echo "Building with debug information..."
echo "console.log('API_URL in production:', process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api');" >> src/index.tsx

# Update the API URL to be more explicit
cat > src/lib/api.ts << 'EOF'
// API configuration
const API_URL = '/api'; // Always use /api for both production and development

export const getApiUrl = (path: string): string => {
  // Remove leading slash if present
  const cleanPath = path.startsWith('/') ? path.substring(1) : path;
  return `${API_URL}/${cleanPath}`;
};

// Log the API URL configuration
console.log('API configuration loaded. API_URL:', API_URL);

export default {
  getApiUrl,
};
EOF

# Update the AuthContext to use the correct API URLs
sed -i '' 's|fetch(getApiUrl|fetch("/api|g' src/context/AuthContext.tsx

echo "Fixed API URLs!" 