import React, { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Tabs,
  Tab,
  CircularProgress,
  List,
  ListItem,
  Divider,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material'
import Editor from '@monaco-editor/react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '@/hooks/use-toast'
import { useTheme } from '@mui/material/styles'

interface CodeSubmissionProps {
  onClose: () => void
  currentFile?: {
    id: number
    name: string
    content: string
  }
  sessionId?: number
}

interface Submission {
  id: number
  title: string
  description: string
  code_content: string
  status: 'pending' | 'approved' | 'rejected' | 'revision_requested'
  created_at: string
}

interface Review {
  id: number
  reviewer_id: number
  status: string
  comments: string
  feedback: string
  quality_before_edits: number
  quality_after_edits: number
  edits_made: string
  is_customer_ready: boolean
  created_at: string
}

export function CodeSubmission({ onClose, currentFile, sessionId }: CodeSubmissionProps) {
  const { token } = useAuth()
  const { toast } = useToast()
  const theme = useTheme()
  const isDarkMode = theme.palette.mode === 'dark'
  const [activeTab, setActiveTab] = useState(0)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [selectedSubmission, setSelectedSubmission] = useState<Submission | null>(null)
  const [reviews, setReviews] = useState<Review[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)

  // Load user's submissions
  useEffect(() => {
    if (token) {
      loadSubmissions()
    }
  }, [token])

  const loadSubmissions = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/code-review/submissions/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setSubmissions(data)
      } else {
        console.error('Failed to load submissions:', response.status, response.statusText)
        toast({
          variant: 'destructive',
          title: 'Error',
          description: 'Failed to load submissions',
        })
      }
    } catch (error) {
      console.error('Error loading submissions:', error)
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to load submissions',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const loadReviews = async (submissionId: number) => {
    try {
      const response = await fetch(`/api/code-review/submissions/${submissionId}/reviews/`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setReviews(data)
      } else {
        toast({
          variant: 'destructive',
          title: 'Error',
          description: 'Failed to load reviews',
        })
      }
    } catch (error) {
      console.error('Error loading reviews:', error)
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to load reviews',
      })
    }
  }

  const handleSubmit = async () => {
    if (!currentFile) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'No file selected for submission',
      })
      return
    }

    if (!title.trim()) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Please enter a title for your submission',
      })
      return
    }

    setIsSubmitting(true)

    try {
      console.log('Submitting code with data:', {
        session_id: sessionId || null,
        file_id: currentFile.id,
        title,
        description,
        code_content: currentFile.content,
      })

      const response = await fetch('/api/code-review/submissions/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: sessionId || null,
          file_id: currentFile.id,
          title: title,
          description: description,
          code_content: currentFile.content,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        console.log('Submission successful:', data)
        toast({
          title: 'Success',
          description: 'Code submitted successfully for review',
        })
        setTitle('')
        setDescription('')
        loadSubmissions()
        setActiveTab(1) // Switch to feedback tab
      } else {
        const errorText = await response.text()
        let errorData
        try {
          errorData = JSON.parse(errorText)
        } catch (e) {
          errorData = { detail: errorText || 'Failed to submit code' }
        }
        console.error('Submission failed:', response.status, response.statusText, errorData)
        toast({
          variant: 'destructive',
          title: 'Error',
          description: errorData.detail || 'Failed to submit code',
        })
      }
    } catch (error) {
      console.error('Error submitting code:', error)
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'An error occurred while submitting your code',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue)
  }

  const handleViewDetails = (submission: Submission) => {
    setSelectedSubmission(submission)
    loadReviews(submission.id)
    setDetailsOpen(true)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'success'
      case 'rejected':
        return 'error'
      case 'revision_requested':
        return 'warning'
      default:
        return 'default'
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString()
  }

  // Determine language based on code content
  const getLanguage = (content: string): string => {
    // Check for Python syntax
    if (
      content.includes('def ') ||
      content.includes('import ') ||
      (content.includes('class ') && content.includes(':'))
    ) {
      return 'python'
    }
    // Check for JavaScript/TypeScript
    else if (
      content.includes('function ') ||
      content.includes('const ') ||
      content.includes('let ') ||
      content.includes('=>')
    ) {
      // Check for TypeScript specific syntax
      if (
        content.includes('interface ') ||
        (content.includes(':') && content.includes('type ')) ||
        content.includes('<T>')
      ) {
        return 'typescript'
      }
      return 'javascript'
    }
    // Check for HTML
    else if (content.includes('<html') || content.includes('<body') || content.includes('<div')) {
      return 'html'
    }
    // Check for CSS
    else if (
      content.includes('{') &&
      content.includes('}') &&
      content.includes(':') &&
      content.includes(';')
    ) {
      return 'css'
    }
    // Default to plaintext
    return 'plaintext'
  }

  return (
    <Dialog
      open={true}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { height: '80vh' },
      }}
    >
      <DialogTitle>
        Code Submission
        <Button onClick={onClose} sx={{ position: 'absolute', right: 8, top: 8 }}>
          Close
        </Button>
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={activeTab} onChange={handleTabChange}>
            <Tab label="Submit Code" />
            <Tab label="Feedback" />
          </Tabs>
        </Box>

        {/* Submit Code Tab */}
        {activeTab === 0 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Submit your code for review
            </Typography>
            <TextField
              label="Title"
              fullWidth
              margin="normal"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
            <TextField
              label="Description"
              fullWidth
              margin="normal"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              multiline
              rows={4}
            />
            <Box sx={{ mt: 2, mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                File to submit: {currentFile?.name || 'No file selected'}
              </Typography>
            </Box>
            <Button
              variant="contained"
              color="secondary"
              onClick={handleSubmit}
              disabled={isSubmitting || !currentFile}
              sx={{ mt: 2 }}
            >
              {isSubmitting ? (
                <>
                  <CircularProgress size={24} sx={{ mr: 1 }} color="inherit" />
                  Submitting...
                </>
              ) : (
                'Submit for Review'
              )}
            </Button>
          </Box>
        )}

        {/* Feedback Tab */}
        {activeTab === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Your Submissions
            </Typography>
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <CircularProgress />
              </Box>
            ) : submissions.length > 0 ? (
              <List>
                {submissions.map((submission) => (
                  <React.Fragment key={submission.id}>
                    <ListItem alignItems="flex-start" sx={{ flexDirection: 'column', py: 2 }}>
                      <Box
                        sx={{
                          width: '100%',
                          display: 'flex',
                          justifyContent: 'space-between',
                          mb: 1,
                        }}
                      >
                        <Typography variant="subtitle1">{submission.title}</Typography>
                        <Chip
                          label={submission.status}
                          color={getStatusColor(submission.status) as any}
                          size="small"
                        />
                      </Box>

                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {formatDate(submission.created_at)}
                      </Typography>

                      {submission.description && (
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          {submission.description.substring(0, 100)}
                          {submission.description.length > 100 ? '...' : ''}
                        </Typography>
                      )}

                      <Box sx={{ display: 'flex', gap: 1, alignSelf: 'flex-end', mt: 1 }}>
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => handleViewDetails(submission)}
                        >
                          View Details
                        </Button>
                      </Box>
                    </ListItem>
                    <Divider component="li" />
                  </React.Fragment>
                ))}
              </List>
            ) : (
              <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
                You haven't submitted any code for review yet.
              </Typography>
            )}
          </Box>
        )}

        {/* Submission Details Dialog */}
        {selectedSubmission && (
          <Dialog open={detailsOpen} onClose={() => setDetailsOpen(false)} maxWidth="md" fullWidth>
            <DialogTitle>Submission Details</DialogTitle>
            <DialogContent dividers>
              <Typography variant="h6">{selectedSubmission.title}</Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Submitted on {formatDate(selectedSubmission.created_at)}
              </Typography>
              <Chip
                label={selectedSubmission.status}
                color={getStatusColor(selectedSubmission.status) as any}
                size="small"
                sx={{ mb: 2 }}
              />

              {selectedSubmission.description && (
                <>
                  <Typography variant="subtitle1" sx={{ mt: 2 }}>
                    Description
                  </Typography>
                  <Typography variant="body2" paragraph>
                    {selectedSubmission.description}
                  </Typography>
                </>
              )}

              <Typography variant="subtitle1" sx={{ mt: 2 }}>
                Code
              </Typography>
              <Paper
                elevation={0}
                sx={{
                  p: 0,
                  height: '400px',
                  bgcolor: 'background.default',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  overflow: 'hidden',
                }}
              >
                <Editor
                  height="100%"
                  language={getLanguage(selectedSubmission.code_content)}
                  defaultValue={selectedSubmission.code_content}
                  theme={isDarkMode ? 'vs-dark' : 'vs'}
                  options={{
                    readOnly: true,
                    minimap: { enabled: true },
                    fontSize: 14,
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                  }}
                />
              </Paper>

              <Typography variant="subtitle1" sx={{ mt: 3 }}>
                Reviews
              </Typography>
              {reviews.length > 0 ? (
                reviews.map((review) => (
                  <Paper
                    key={review.id}
                    elevation={0}
                    sx={{
                      p: 2,
                      mt: 2,
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Chip
                        label={review.status}
                        color={getStatusColor(review.status) as any}
                        size="small"
                      />
                      <Typography variant="body2" color="text.secondary">
                        {formatDate(review.created_at)}
                      </Typography>
                    </Box>

                    {review.quality_before_edits && (
                      <Typography variant="body2" sx={{ mt: 1 }}>
                        Quality before edits: {review.quality_before_edits}/5
                      </Typography>
                    )}

                    {review.quality_after_edits && (
                      <Typography variant="body2" sx={{ mt: 1 }}>
                        Quality after edits: {review.quality_after_edits}/5
                      </Typography>
                    )}

                    {review.is_customer_ready !== undefined && (
                      <Typography variant="body2" sx={{ mt: 1 }}>
                        Customer ready: {review.is_customer_ready ? 'Yes' : 'No'}
                      </Typography>
                    )}

                    {review.edits_made && (
                      <>
                        <Typography variant="subtitle2" sx={{ mt: 2 }}>
                          Edits Made
                        </Typography>
                        <Typography variant="body2" paragraph>
                          {review.edits_made}
                        </Typography>
                      </>
                    )}

                    {review.comments && (
                      <>
                        <Typography variant="subtitle2" sx={{ mt: 2 }}>
                          Comments
                        </Typography>
                        <Typography variant="body2" paragraph>
                          {review.comments}
                        </Typography>
                      </>
                    )}

                    {review.feedback && (
                      <>
                        <Typography variant="subtitle2" sx={{ mt: 2 }}>
                          Feedback
                        </Typography>
                        <Typography variant="body2" paragraph>
                          {review.feedback}
                        </Typography>
                      </>
                    )}
                  </Paper>
                ))
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  No reviews yet.
                </Typography>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetailsOpen(false)}>Close</Button>
            </DialogActions>
          </Dialog>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default CodeSubmission
