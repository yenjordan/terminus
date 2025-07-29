import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

// Simple fallback component
function App() {
  return (
    <div
      style={{
        maxWidth: '800px',
        margin: '0 auto',
        padding: '2rem',
        fontFamily: 'system-ui, sans-serif',
        textAlign: 'center',
      }}
    >
      <img
        src="/terminus-logo.svg"
        alt="Terminus Logo"
        style={{ width: '150px', marginBottom: '2rem' }}
      />
      <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>Terminus IDE</h1>
      <p style={{ fontSize: '1.2rem', lineHeight: 1.6, marginBottom: '1.5rem' }}>
        A professional Python development environment with real-time code execution, terminal
        support, and file management.
      </p>
      <div style={{ marginTop: '2rem' }}>
        <a
          href="/api/docs"
          style={{
            display: 'inline-block',
            margin: '0 1rem',
            padding: '0.75rem 1.5rem',
            backgroundColor: '#4a5568',
            color: 'white',
            textDecoration: 'none',
            borderRadius: '4px',
            fontWeight: 500,
          }}
        >
          API Documentation
        </a>
        <a
          href="/static-debug"
          style={{
            display: 'inline-block',
            margin: '0 1rem',
            padding: '0.75rem 1.5rem',
            backgroundColor: '#4a5568',
            color: 'white',
            textDecoration: 'none',
            borderRadius: '4px',
            fontWeight: 500,
          }}
        >
          Debug Information
        </a>
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
