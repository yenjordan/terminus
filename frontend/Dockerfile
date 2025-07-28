FROM node:22-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with legacy peer deps flag to handle React version conflicts
RUN npm install --legacy-peer-deps

# Copy the rest of the application
COPY . .

# Expose the port
EXPOSE 5173

# Start the development server with host flag to make it accessible from outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]