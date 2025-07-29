// API config
const API_URL = '/api'

export const getApiUrl = (path: string): string => {
  // removing leading slash if present
  const cleanPath = path.startsWith('/') ? path.substring(1) : path
  return `${API_URL}/${cleanPath}`
}

// logging the API URL configuration
console.log('API configuration loaded. API_URL:', API_URL)

export default {
  getApiUrl,
}
