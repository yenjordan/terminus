import React from 'react'
import ReactDOM from 'react-dom/client'
import Router from './routes/router'
import './index.css'
import { AuthProvider } from './context/AuthContext'

// Error handling
const ErrorFallback = () => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        padding: '20px',
        backgroundColor: '#f0f0f0',
        color: '#333',
      }}
    >
      <h1>Something went wrong</h1>
      <p>An error occurred while loading the application.</p>
      <p>Please check the browser console for more details.</p>
    </div>
  )
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Rendering error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback />
    }

    return this.props.children
  }
}

const rootElement = document.getElementById('root')
if (rootElement) {
  try {
    console.log('Starting to render app...')
    ReactDOM.createRoot(rootElement).render(
      <React.StrictMode>
        <ErrorBoundary>
          <AuthProvider>
            <Router />
          </AuthProvider>
        </ErrorBoundary>
      </React.StrictMode>
    )
    console.log('App rendered successfully')
  } catch (error) {
    console.error('Error rendering app:', error)
    rootElement.innerHTML =
      '<div style="padding: 20px; text-align: center;"><h1>Failed to load application</h1><p>Please check the console for errors.</p></div>'
  }
}
