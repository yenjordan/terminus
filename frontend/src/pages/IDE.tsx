import React, { useEffect, useState, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Divider,
  Tooltip,
  Grid,
  Tabs,
  Tab,
  CircularProgress,
} from '@mui/material'
import {
  PlayArrow as RunIcon,
  Save as SaveIcon,
  Upload as UploadIcon,
  Send as SubmitIcon,
  FolderOpen as OpenIcon,
  RateReview as ReviewIcon,
} from '@mui/icons-material'
import CodeEditor from '../components/CodeEditor'
import Terminal from '../components/Terminal'
import FileExplorer from '../components/FileExplorer'
import { SessionManager } from '../components/SessionManager'
import { CodeReview } from '../components/CodeReview'
import { CodeSubmission } from '../components/CodeSubmission'
import { ProtectedRoute } from '../components/ProtectedRoute'
import { useToast } from '@/hooks/use-toast'

interface Session {
  id: number
  name: string
  description?: string
  is_active: boolean
  last_accessed: string
  created_at: string
  updated_at: string
}

interface CodeFile {
  id: number
  name: string
  path: string
  content: string
  file_type: string
  session_id: number
  size_bytes: number
  created_at: string
  updated_at: string
}

interface CodeSubmission {
  id: number
  user_id: number
  code: string
  language: string
  status: 'pending' | 'approved' | 'rejected'
  reviewer_id?: number
  feedback?: string
  created_at: string
  updated_at: string
}

export function IDE() {
  const { token, user } = useAuth()
  const [isLoading, setIsLoading] = useState(false) // Changed to false so UI renders immediately
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [files, setFiles] = useState<CodeFile[]>([])
  const [currentFile, setCurrentFile] = useState<CodeFile | null>(null)
  const [activeTab, setActiveTab] = useState<number>(0)
  const [inputContent, setInputContent] = useState<string>('')
  const [outputContent, setOutputContent] = useState<string>('')
  const [isRunning, setIsRunning] = useState(false)
  const [submissions, setSubmissions] = useState<CodeSubmission[]>([])
  const [showSubmissions, setShowSubmissions] = useState(false)
  const [showReviews, setShowReviews] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [tempSessionId, setTempSessionId] = useState<number>(1) // Temporary session ID for immediate terminal loading
  const { toast } = useToast()

  // Determine if the user is a reviewer
  const isReviewer = user?.role === 'reviewer'

  // Load session and file from localStorage
  useEffect(() => {
    if (token && user) {
      const savedSessionId = localStorage.getItem('currentSessionId')
      if (savedSessionId) {
        console.log('Restoring session from localStorage:', savedSessionId)
      }

      console.log('Token and user data available, initializing IDE')
      console.log('User role for initialization:', user.role)
      initializeIDE(savedSessionId ? parseInt(savedSessionId, 10) : undefined)
    } else if (token) {
      console.log('Waiting for user data before initializing IDE')
    } else {
      console.error('No token available in useEffect')
    }
  }, [token, user])

  // Debug user data
  useEffect(() => {
    console.log('Current user data:', user)
    if (user) {
      console.log('User role:', user.role)
      console.log('Is reviewer:', user.role === 'reviewer')
    } else if (token) {
      console.log('User data not loaded yet but token exists')
    }
  }, [user, token])

  // Save current session to localStorage
  useEffect(() => {
    if (currentSession) {
      localStorage.setItem('currentSessionId', currentSession.id.toString())
    }
  }, [currentSession])

  // Save current file to localStorage
  useEffect(() => {
    if (currentFile && currentSession) {
      localStorage.setItem(`fileId_session_${currentSession.id}`, currentFile.id.toString())
    }
  }, [currentFile, currentSession])

  const initializeIDE = async (savedSessionId?: number) => {
    try {
      console.log('Initializing IDE with token:', token ? 'Valid token present' : 'No token')

      // Get user sessions
      const sessionsResponse = await fetch('/api/sessions/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (!sessionsResponse.ok) {
        throw new Error('Failed to fetch sessions')
      }

      const sessions = await sessionsResponse.json()

      // If no sessions, create a default one
      if (sessions.length === 0) {
        const newSession = await createDefaultSession()
        setCurrentSession(newSession)
        setTempSessionId(newSession.id) // Update temp session ID with real one

        // Create main.py file in the new session
        await createMainPyFile(newSession.id)

        // Load session files (this will automatically load main.py)
        await loadSessionFiles(newSession.id)
      } else {
        // Try to restore saved session or use the most recently accessed one
        let activeSession

        if (savedSessionId) {
          activeSession = sessions.find((s: Session) => s.id === savedSessionId)
        }

        if (!activeSession) {
          activeSession = sessions.find((s: Session) => s.is_active) || sessions[0]
        }

        setCurrentSession(activeSession)
        setTempSessionId(activeSession.id) // Update temp session ID with real one

        // Load session files (this will check for main.py and create it if needed)
        await loadSessionFiles(activeSession.id)
      }

      // Load submissions if user is a reviewer
      if (user?.role === 'reviewer' || user?.role === 'admin' || user?.role === 'moderator') {
        await loadSubmissions()
      }
    } catch (error) {
      console.error('Failed to initialize IDE:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const createDefaultSession = async () => {
    try {
      const response = await fetch('/api/sessions/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: 'Default Session',
          description: 'Your coding workspace',
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to create session')
      }

      return await response.json()
    } catch (error) {
      console.error('Failed to create default session:', error)
      throw error
    }
  }

  const createMainPyFile = async (sessionId: number) => {
    try {
      // Get user role to determine which content to show
      const isReviewer = user?.role === 'reviewer'

      console.log('Creating main.py file with user role:', user?.role)
      console.log('isReviewer value:', isReviewer)

      // Data analysis example using pandas and scipy
      const dataAnalysisExample = `
import pandas as pd
from scipy import stats

data = {
    'Name': ['Alice', 'Bob', 'Charlie', 'David', 'Eva'],
    'Score': [85, 90, 78, 92, 88]
}
df = pd.DataFrame(data)

mean_score = df['Score'].mean()
median_score = df['Score'].median()
mode_score = stats.mode(df['Score'], keepdims=True).mode[0]

print("Student Scores:")
print(df)
print("\\nStatistics:")
print(f"Mean: {mean_score}")
print(f"Median: {median_score}")
print(f"Mode: {mode_score}")
`

      // Create different content based on user role
      const mainPyContent = isReviewer
        ? `# Welcome to Terminus IDE

# As a reviewer, you can:
# 1. View submissions waiting for your review
# 2. Provide quality ratings and feedback on submissions
# 3. Approve, reject, or request revisions for code submissions

# You can run this example code to analyze student scores:
${dataAnalysisExample}`
        : `# Welcome to Terminus IDE

# As an attempter, you can:
# 1. Write and test your code in this editor
# 2. Submit your code for review when you're ready
# 3. See reviews of your submissions

# You can run this example code to analyze student scores:
${dataAnalysisExample}`

      const response = await fetch(`/api/files/?session_id=${sessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: 'main.py',
          path: '/main.py',
          content: mainPyContent,
          file_type: 'python',
        }),
      })

      if (response.ok) {
        console.log('Successfully created main.py file')
        return await response.json()
      } else {
        console.error('Failed to create main.py file:', response.statusText)
        return null
      }
    } catch (error) {
      console.error('Failed to create main.py file:', error)
      return null
    }
  }

  const createWelcomeFile = async (sessionId: number) => {
    try {
      const welcomeContent = `# Welcome to Terminus IDE!
# 
# This is a professional Python development environment.
# Features:
# - Full terminal support (ls, cat, python, pip install, etc.)
# - Code execution with real-time output
# - File management and editing
# - Code submission and review system
# - Secure execution environment with pandas and scipy

import pandas as pd
from scipy import stats

# Example data analysis
data = {
    'Name': ['Alice', 'Bob', 'Charlie', 'David', 'Eva'],
    'Score': [85, 90, 78, 92, 88]
}
df = pd.DataFrame(data)

# Try running this file to see the output!
print("Welcome to Terminus IDE!")
print("\\nSample DataFrame:")
print(df)
`

      const response = await fetch(`/api/files/?session_id=${sessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: 'welcome.py',
          path: '/welcome.py',
          content: welcomeContent,
          file_type: 'python',
        }),
      })

      if (response.ok) {
        return await response.json()
      } else {
        console.error('Failed to create welcome file:', response.statusText)
      }
    } catch (error) {
      console.error('Failed to create welcome file:', error)
    }
  }

  const loadSessionFiles = async (sessionId: number) => {
    try {
      const response = await fetch(`/api/files/session/${sessionId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (response.ok) {
        const sessionFiles = await response.json()

        // Filter out npm-related files and package.json
        const filteredFiles = sessionFiles.filter((file: CodeFile) => {
          // Skip npm log files and package.json
          return !(
            file.name.includes('package.json') ||
            file.name.endsWith('.log') ||
            file.name.includes('npm-debug') ||
            file.path.includes('node_modules') ||
            file.path.includes('.npm') ||
            file.path.includes('.npmrc')
          )
        })

        setFiles(filteredFiles)

        // Check if main.py exists
        const mainPyFile = filteredFiles.find((file: CodeFile) => file.name === 'main.py')

        // If main.py doesn't exist, create it
        if (!mainPyFile) {
          console.log('Creating main.py file for session', sessionId)
          const newMainPy = await createMainPyFile(sessionId)
          if (newMainPy) {
            // Add the new main.py to the files array
            setFiles((prev) => [...prev, newMainPy])
            // Set it as the current file
            setCurrentFile(newMainPy)
            return
          }
        } else {
          // Check if the content matches the expected content for the user's role
          const isReviewer = user?.role === 'reviewer'
          const hasReviewerContent = mainPyFile.content.includes('Reviewer Mode')
          const hasAttempterContent = mainPyFile.content.includes('Attempter Mode')

          console.log('Checking main.py content - User role:', user?.role)
          console.log('Has reviewer content:', hasReviewerContent)
          console.log('Has attempter content:', hasAttempterContent)

          // If the content doesn't match the user's role, recreate the file
          if ((isReviewer && !hasReviewerContent) || (!isReviewer && !hasAttempterContent)) {
            console.log('Recreating main.py file to match user role:', user?.role)

            // Delete the existing main.py
            await fetch(`/api/files/${mainPyFile.id}`, {
              method: 'DELETE',
              headers: {
                Authorization: `Bearer ${token}`,
              },
            })

            // Create a new main.py with the correct content
            const newMainPy = await createMainPyFile(sessionId)
            if (newMainPy) {
              // Update the files array
              setFiles((prev) => prev.filter((f) => f.id !== mainPyFile.id).concat(newMainPy))
              // Set it as the current file
              setCurrentFile(newMainPy)
              return
            }
          } else {
            // If main.py exists and content matches role, load it by default
            console.log('Loading existing main.py file')
            setCurrentFile(mainPyFile)
            return
          }
        }

        // Only try to restore the previously selected file if we didn't already select main.py
        const savedFileId = localStorage.getItem(`fileId_session_${sessionId}`)
        if (savedFileId) {
          const savedFile = filteredFiles.find(
            (file: CodeFile) => file.id.toString() === savedFileId
          )
          if (savedFile) {
            await fetchFileContent(parseInt(savedFileId, 10))
            return
          }
        }

        // If no saved file or it doesn't exist anymore, and we didn't load main.py,
        // use the first file
        if (filteredFiles.length > 0) {
          setCurrentFile(filteredFiles[0])
        } else {
          setCurrentFile(null)
        }
      }
    } catch (error) {
      console.error('Failed to load session files:', error)
    }
  }

  const fetchFileContent = async (fileId: number) => {
    try {
      const response = await fetch(`/api/files/${fileId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (response.ok) {
        const file = await response.json()
        setCurrentFile(file)
      }
    } catch (error) {
      console.error('Failed to fetch file content:', error)
    }
  }

  const handleDeleteFile = async (fileId: number): Promise<boolean> => {
    if (!token) return false

    try {
      const response = await fetch(`/api/files/${fileId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (response.ok) {
        // If the deleted file is the current file, clear it
        if (currentFile?.id === fileId) {
          setCurrentFile(null)
          // Remove from localStorage
          if (currentSession) {
            localStorage.removeItem(`fileId_session_${currentSession.id}`)
          }
        }

        // Remove the file from the files array
        setFiles((prev) => prev.filter((file) => file.id !== fileId))

        // Notify terminal of file deletion to update the workspace
        notifyTerminalOfFileChange()

        return true
      } else {
        console.error('Failed to delete file:', response.statusText)
        return false
      }
    } catch (error) {
      console.error('Error deleting file:', error)
      return false
    }
  }

  const loadSubmissions = async () => {
    try {
      const response = await fetch('/api/submissions/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (response.ok) {
        const submissionsData = await response.json()
        setSubmissions(submissionsData)
      }
    } catch (error) {
      console.error('Failed to load submissions:', error)
    }
  }

  const handleSessionChange = async (newSession: Session) => {
    if (newSession.id === currentSession?.id) return

    // Set loading state to show immediate feedback
    setIsLoading(true)

    // Update the session immediately to prevent UI lag
    setCurrentSession(newSession)
    setTempSessionId(newSession.id)

    // Clear current file to prevent displaying stale content
    setCurrentFile(null)

    try {
      // Load files for the new session (this will check for main.py and create it if needed)
      await loadSessionFiles(newSession.id)
    } catch (error) {
      console.error('Failed to change session:', error)
    } finally {
      // Always turn off loading state
      setIsLoading(false)
    }
  }

  const handleFileSelect = async (file: CodeFile) => {
    console.log(`Selected file: ${file.name} (ID: ${file.id})`)

    // Fetch the latest content of the file
    try {
      const response = await fetch(`/api/files/${file.id}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (response.ok) {
        const freshFile = await response.json()
        // Update the file in the files array
        setFiles((prevFiles) => prevFiles.map((f) => (f.id === freshFile.id ? freshFile : f)))
        // Set as current file
        setCurrentFile(freshFile)
      } else {
        // If fetch fails, use the existing file object
        setCurrentFile(file)
      }
    } catch (error) {
      console.error('Failed to fetch latest file content:', error)
      // If fetch fails, use the existing file object
      setCurrentFile(file)
    }

    // Save to localStorage for this session
    if (currentSession) {
      localStorage.setItem(`fileId_session_${currentSession.id}`, file.id.toString())
    }
  }

  const notifyTerminalOfFileChange = () => {
    // Find the terminal WebSocket and send a file_change message
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && currentSession) {
      console.log('Notifying terminal of file change')
      wsRef.current.send(
        JSON.stringify({
          type: 'file_change',
          session_id: currentSession.id,
        })
      )
    }
  }

  const handleCreateFile = async (name: string, path: string, content: string = '') => {
    if (!currentSession) return

    try {
      console.log(`Creating file: ${name} at path: ${path} in session: ${currentSession.id}`)

      const response = await fetch(`/api/files/?session_id=${currentSession.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: name,
          path: path,
          content: content,
          file_type: name.endsWith('.py') ? 'python' : 'text',
        }),
      })

      if (response.ok) {
        const newFile = await response.json()
        setFiles((prev) => [...prev, newFile])
        setCurrentFile(newFile)

        // Notify terminal of file change
        notifyTerminalOfFileChange()
      } else {
        console.error('Failed to create file:', response.statusText)
        alert('Failed to create file. Please try again.')
      }
    } catch (error) {
      console.error('Error creating file:', error)
      alert('Error creating file. Please try again.')
    }
  }

  const handleUploadFile = async (file: File) => {
    if (!currentSession) return

    try {
      const content = await file.text()
      const fileType = file.name.endsWith('.py') ? 'python' : 'text'

      const response = await fetch(`/api/files/?session_id=${currentSession.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: file.name,
          path: `/${file.name}`,
          content: content,
          file_type: fileType,
        }),
      })

      if (response.ok) {
        const newFile = await response.json()
        setFiles((prev) => [...prev, newFile])
        setCurrentFile(newFile)

        // Notify terminal of file change
        notifyTerminalOfFileChange()
      }
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('Error uploading file. Please try again.')
    }
  }

  const handleFileContentChange = async (newContent: string) => {
    if (!currentFile) return

    // Don't update if content hasn't changed
    if (currentFile.content === newContent) return

    // Update the file locally first for instant feedback
    setCurrentFile((prev) => (prev ? { ...prev, content: newContent } : null))

    // Also update in the files array
    setFiles((prev) =>
      prev.map((file) => (file.id === currentFile.id ? { ...file, content: newContent } : file))
    )

    try {
      const response = await fetch(`/api/files/${currentFile.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          content: newContent,
        }),
      })

      if (response.ok) {
        // No need to update state again as we already did it above
        // Just log success
        console.log(`File ${currentFile.name} updated successfully`)

        // Notify terminal of file change so it uses the updated version
        notifyTerminalOfFileChange()
      } else {
        console.error('Failed to update file:', response.statusText)
      }
    } catch (error) {
      console.error('Failed to update file:', error)
    }
  }

  const handleFileChange = () => {
    if (currentSession) {
      loadSessionFiles(currentSession.id)
    }
  }

  const handleRunCode = async () => {
    if (!currentFile || !currentSession) {
      alert('Please select a file to run')
      return
    }

    setIsRunning(true)
    setActiveTab(1) // Switch to Output tab (now at index 1)
    setOutputContent('Running code...')

    try {
      console.log(`Running code from file: ${currentFile.name}`)

      // Instead of running a file path, send the code content directly for execution
      if (currentSession) {
        // For Python files, execute the code directly via the API
        const response = await fetch(`/api/terminal/code/execute`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            code: currentFile.content,
            session_id: currentSession.id,
            language: currentFile.file_type || 'python',
            input_data: inputContent || '',
          }),
        })

        if (response.ok) {
          const result = await response.json()
          // Update the output panel with the execution result
          if (result.output) {
            setOutputContent(result.output)
          } else if (result.error) {
            setOutputContent(`Error:\n${result.error}`)
          } else {
            setOutputContent('Code executed successfully with no output.')
          }
        } else {
          const errorData = await response.text()
          console.error('Error executing code:', errorData)
          setOutputContent(`Error executing code: ${errorData}`)
        }
      }
    } catch (error) {
      console.error('Failed to run code:', error)
      setOutputContent(`Error running code: ${error}`)
    } finally {
      setTimeout(() => setIsRunning(false), 1000)
    }
  }

  const handleSaveFile = async () => {
    if (!currentFile) return

    try {
      // Save the file explicitly
      const response = await fetch(`/api/files/${currentFile.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          content: currentFile.content,
        }),
      })

      if (response.ok) {
        // Show a brief success message
        toast({
          title: 'File saved',
          description: `${currentFile.name} has been saved successfully.`,
          duration: 2000,
        })

        // Notify terminal of file change to ensure it uses the latest version
        notifyTerminalOfFileChange()
        console.log('File saved:', currentFile.name)
      } else {
        toast({
          variant: 'destructive',
          title: 'Save failed',
          description: 'Failed to save the file. Please try again.',
        })
        console.error('Failed to save file:', response.statusText)
      }
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Save failed',
        description: 'An error occurred while saving the file.',
      })
      console.error('Error saving file:', error)
    }
  }

  const handleOpenFile = () => {
    fileInputRef.current?.click()
  }

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      handleUploadFile(file)
    }
    event.target.value = ''
  }

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue)
  }

  // Only show loading indicator when initially fetching sessions
  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          bgcolor: 'background.default',
        }}
      >
        <Box sx={{ textAlign: 'center' }}>
          <CircularProgress size={60} sx={{ mb: 3 }} />
          <Typography variant="h5" sx={{ mb: 1 }}>
            Loading Terminus IDE...
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Setting up your development environment
          </Typography>
        </Box>
      </Box>
    )
  }

  return (
    <ProtectedRoute>
      <Box
        sx={{
          height: 'calc(100vh - 64px)',
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'background.default',
          overflow: 'hidden',
        }}
      >
        {/* Toolbar */}
        <Paper
          elevation={0}
          sx={{
            p: 1,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tooltip title="Open File">
              <Button
                variant="outlined"
                size="small"
                startIcon={<OpenIcon />}
                onClick={handleOpenFile}
              >
                Open
              </Button>
            </Tooltip>
            <Tooltip title="Save File">
              <Button
                variant="outlined"
                size="small"
                startIcon={<SaveIcon />}
                onClick={handleSaveFile}
                disabled={!currentFile}
              >
                Save
              </Button>
            </Tooltip>

            {/* Show Submit button for attempters */}
            {!isReviewer && (
              <Tooltip title="Submit Code for Review">
                <Button
                  variant="outlined"
                  size="small"
                  color="secondary"
                  startIcon={<SubmitIcon />}
                  onClick={() => setShowSubmissions(true)}
                  disabled={!currentFile}
                >
                  Submit for Review
                </Button>
              </Tooltip>
            )}

            {/* Show Review button for reviewers */}
            {isReviewer && (
              <Tooltip title="Review Code Submissions">
                <Button
                  variant="outlined"
                  size="small"
                  color="secondary"
                  startIcon={<ReviewIcon />}
                  onClick={() => setShowReviews(true)}
                >
                  Review Code
                </Button>
              </Tooltip>
            )}
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<RunIcon />}
              onClick={handleRunCode}
              disabled={isRunning || !currentFile}
            >
              {isRunning ? (
                <>
                  <CircularProgress size={16} sx={{ mr: 1 }} color="inherit" />
                  Running...
                </>
              ) : (
                'Run Code'
              )}
            </Button>
            <SessionManager currentSession={currentSession} onSessionChange={handleSessionChange} />
          </Box>
        </Paper>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".py,.txt,.md,.json,.js,.ts,.css,.html"
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
        />

        {/* Main content area */}
        <Box
          sx={{
            display: 'flex',
            flexGrow: 1,
            overflow: 'hidden',
            p: 1,
            gap: 1,
          }}
        >
          {/* File Explorer */}
          <Box sx={{ width: 250, flexShrink: 0 }}>
            <FileExplorer
              files={files}
              currentFile={currentFile}
              onFileSelect={handleFileSelect}
              onCreateFile={handleCreateFile}
              onUploadFile={handleUploadFile}
              currentSession={currentSession}
              onFilesUpdated={() => currentSession && loadSessionFiles(currentSession.id)}
              onDeleteFile={handleDeleteFile}
            />
          </Box>

          {/* Code Editor and Terminal */}
          <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Code Editor */}
            <Box sx={{ flexGrow: 1, mb: 1, overflow: 'hidden' }}>
              {currentFile ? (
                <CodeEditor file={currentFile} onContentChange={handleFileContentChange} />
              ) : (
                <Paper
                  elevation={0}
                  sx={{
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <Box sx={{ textAlign: 'center', p: 3 }}>
                    <Typography variant="h4" sx={{ mb: 2 }}>
                      💻
                    </Typography>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                      Welcome to Terminus IDE
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                      A professional Python development environment
                    </Typography>
                    <Box sx={{ mb: 3 }}>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        • Full terminal support (ls, cat, python, pip install)
                      </Typography>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        • Real-time code execution with pandas & scipy
                      </Typography>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        • Code submission and review system
                      </Typography>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        • Secure execution environment
                      </Typography>
                    </Box>
                    <Button variant="contained" onClick={handleOpenFile}>
                      Open File to Get Started
                    </Button>
                  </Box>
                </Paper>
              )}
            </Box>

            {/* Input/Output and Terminal */}
            <Box sx={{ height: 300, display: 'flex', gap: 1 }}>
              {/* Input/Output Panel */}
              <Paper
                elevation={0}
                sx={{
                  width: '50%',
                  display: 'flex',
                  flexDirection: 'column',
                  borderRadius: 1,
                  border: '1px solid',
                  borderColor: 'divider',
                  overflow: 'hidden',
                }}
              >
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                  <Tabs
                    value={activeTab}
                    onChange={handleTabChange}
                    variant="fullWidth"
                    textColor="primary"
                    indicatorColor="primary"
                  >
                    <Tab label="Input" />
                    <Tab label="Output" />
                  </Tabs>
                </Box>

                <Box sx={{ flexGrow: 1, overflow: 'auto', p: 1 }}>
                  {activeTab === 0 ? (
                    <Box
                      component="textarea"
                      value={inputContent}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                        setInputContent(e.target.value)
                      }
                      placeholder="Enter input data for your program here..."
                      sx={{
                        width: '100%',
                        height: '100%',
                        p: 1,
                        border: 'none',
                        resize: 'none',
                        fontFamily: '"Fira Code", monospace',
                        fontSize: '0.875rem',
                        bgcolor: 'background.paper',
                        borderRadius: 1,
                        '&:focus': {
                          outline: 'none',
                          boxShadow: 'none',
                        },
                      }}
                    />
                  ) : (
                    <Box
                      component="pre"
                      sx={{
                        height: '100%',
                        m: 0,
                        p: 1,
                        fontFamily: '"Fira Code", monospace',
                        fontSize: '0.875rem',
                        overflow: 'auto',
                        bgcolor: 'background.paper',
                        borderRadius: 1,
                      }}
                    >
                      {outputContent || 'Program output will appear here...'}
                    </Box>
                  )}
                </Box>
              </Paper>

              {/* Terminal Panel */}
              <Box sx={{ width: '50%' }}>
                {/* Always render the Terminal component with either the current session ID or the temporary one */}
                <Terminal
                  sessionId={currentSession?.id || tempSessionId}
                  onFileChange={handleFileChange}
                  inputData={inputContent}
                  wsRef={wsRef}
                />
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Code Submission Modal for Attempters */}
        {showSubmissions && (
          <CodeSubmission
            onClose={() => setShowSubmissions(false)}
            currentFile={currentFile || undefined}
            sessionId={currentSession?.id}
          />
        )}

        {/* Code Review Modal for Reviewers */}
        {showReviews && <CodeReview onClose={() => setShowReviews(false)} />}
      </Box>
    </ProtectedRoute>
  )
}

export default IDE
