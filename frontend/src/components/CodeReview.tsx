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
  ListItemText,
  Divider,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Rating,
  FormControlLabel,
  Switch,
  FormGroup,
  FormControl,
  FormLabel,
  Grid,
} from '@mui/material'
import Editor from '@monaco-editor/react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '@/hooks/use-toast'
import { useTheme } from '@mui/material/styles'

interface CodeReviewProps {
  onClose: () => void
}

interface Submission {
  id: number
  title: string
  description: string
  code_content: string
  status: 'pending' | 'approved' | 'rejected' | 'revision_requested'
  created_at: string
  submitter_id: number
}

interface Review {
  id: number
  submission_id: number
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

export function CodeReview({ onClose }: CodeReviewProps) {
  const { token } = useAuth()
  const { toast } = useToast()
  const theme = useTheme()
  const isDarkMode = theme.palette.mode === 'dark'
  const [activeTab, setActiveTab] = useState(0)
  const [pendingSubmissions, setPendingSubmissions] = useState<Submission[]>([])
  const [completedSubmissions, setCompletedSubmissions] = useState<Submission[]>([])
  const [selectedSubmission, setSelectedSubmission] = useState<Submission | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)

  // Review form state
  const [reviewStatus, setReviewStatus] = useState<'approved' | 'rejected' | 'revision_requested'>(
    'approved'
  )
  const [comments, setComments] = useState('')
  const [feedback, setFeedback] = useState('')
  const [qualityBefore, setQualityBefore] = useState<number | null>(null)
  const [qualityAfter, setQualityAfter] = useState<number | null>(null)
  const [editsMade, setEditsMade] = useState('')
  const [isCustomerReady, setIsCustomerReady] = useState(false)

  useEffect(() => {
    if (token) {
      loadSubmissions()
    }
  }, [token])

  const loadSubmissions = async () => {
    setIsLoading(true)
    try {
      // loading pending submissions
      const pendingResponse = await fetch('/api/code-review/submissions/?status_filter=pending', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      // loading completed submissions (approved or rejected)
      const completedResponse = await fetch(
        '/api/code-review/submissions/?status_filter=approved,rejected',
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      if (pendingResponse.ok && completedResponse.ok) {
        const pendingData = await pendingResponse.json()
        const completedData = await completedResponse.json()

        console.log('Pending submissions:', pendingData)
        console.log('Completed submissions:', completedData)

        setPendingSubmissions(pendingData)
        setCompletedSubmissions(completedData)
      } else {
        console.error(
          'Failed to load submissions:',
          pendingResponse.status,
          pendingResponse.statusText,
          completedResponse.status,
          completedResponse.statusText
        )
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

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue)
  }

  const handleViewDetails = (submission: Submission) => {
    setSelectedSubmission(submission)
    setDetailsOpen(true)
  }

  const handleReviewSubmission = (submission: Submission) => {
    setSelectedSubmission(submission)
    // Reset review form
    setReviewStatus('approved')
    setComments('')
    setFeedback('')
    setQualityBefore(null)
    setQualityAfter(null)
    setEditsMade('')
    setIsCustomerReady(false)
    setReviewOpen(true)
  }

  const handleSubmitReview = async () => {
    if (!selectedSubmission) return

    if (qualityBefore === null) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Please rate the quality before edits',
      })
      return
    }

    if (qualityAfter === null) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Please rate the quality after edits',
      })
      return
    }

    setIsSubmitting(true)

    try {
      const response = await fetch(
        `/api/code-review/submissions/${selectedSubmission.id}/reviews/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            status: reviewStatus,
            comments: comments,
            feedback: feedback,
            quality_before_edits: qualityBefore,
            quality_after_edits: qualityAfter,
            edits_made: editsMade,
            is_customer_ready: isCustomerReady,
          }),
        }
      )

      if (response.ok) {
        toast({
          title: 'Success',
          description: 'Review submitted successfully',
        })
        setReviewOpen(false)
        loadSubmissions() // refreshing the submissions list
      } else {
        const errorData = await response.json()
        toast({
          variant: 'destructive',
          title: 'Error',
          description: errorData.detail || 'Failed to submit review',
        })
      }
    } catch (error) {
      console.error('Error submitting review:', error)
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'An error occurred while submitting your review',
      })
    } finally {
      setIsSubmitting(false)
    }
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

  // determining language based on code content
  const getLanguage = (content: string): string => {
    //  check for Python shebang
    if (
      content.trim().startsWith('#!/usr/bin/env python') ||
      content.trim().startsWith('#!python')
    ) {
      return 'python'
    }

    // looking for common Python imports and patterns
    const pythonPatterns = [
      'import pandas',
      'import numpy',
      'import scipy',
      'from pandas',
      'from numpy',
      'from scipy',
      'def __init__',
      'if __name__ == "__main__"',
      "if __name__ == '__main__'",
    ]

    if (
      content.includes('def ') ||
      content.includes('import ') ||
      (content.includes('class ') && content.includes(':')) ||
      pythonPatterns.some((pattern) => content.includes(pattern))
    ) {
      return 'python'
    }

    // checking for JavaScript/TypeScript
    else if (
      content.includes('function ') ||
      content.includes('const ') ||
      content.includes('let ') ||
      content.includes('=>') ||
      content.includes('export ') ||
      content.includes('import React')
    ) {
      // checking for TypeScript specific syntax
      if (
        content.includes('interface ') ||
        content.includes('type ') ||
        content.includes('<T>') ||
        content.includes('as ') ||
        content.includes(': string') ||
        content.includes(': number') ||
        content.includes(': boolean')
      ) {
        return 'typescript'
      }
      return 'javascript'
    }

    // checking for HTML
    else if (
      content.includes('<html') ||
      content.includes('<body') ||
      content.includes('<div') ||
      content.includes('<!DOCTYPE')
    ) {
      return 'html'
    }

    // checking for CSS
    else if (
      content.includes('{') &&
      content.includes('}') &&
      content.includes(':') &&
      (content.includes(';') || content.includes('px') || content.includes('em'))
    ) {
      return 'css'
    }

    // checking for JSON
    else if (
      (content.trim().startsWith('{') && content.trim().endsWith('}')) ||
      (content.trim().startsWith('[') && content.trim().endsWith(']'))
    ) {
      try {
        JSON.parse(content)
        return 'json'
      } catch (e) {
        // Not valid JSON, continue with other checks
      }
    }

    // checking for Markdown
    else if (
      content.includes('# ') ||
      content.includes('## ') ||
      content.includes('### ') ||
      content.includes('```')
    ) {
      return 'markdown'
    }

    // default to python for the most common use case in this app
    return 'python'
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
        Code Review
        <Button onClick={onClose} sx={{ position: 'absolute', right: 8, top: 8 }}>
          Close
        </Button>
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={activeTab} onChange={handleTabChange}>
            <Tab label="Pending Reviews" />
            <Tab label="Completed Reviews" />
          </Tabs>
        </Box>

        {/* Pending Submissions Tab */}
        {activeTab === 0 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Submissions Awaiting Review
            </Typography>
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <CircularProgress />
              </Box>
            ) : pendingSubmissions.length > 0 ? (
              <List>
                {pendingSubmissions.map((submission) => (
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
                        <Button
                          variant="contained"
                          size="small"
                          onClick={() => handleReviewSubmission(submission)}
                        >
                          Review
                        </Button>
                      </Box>
                    </ListItem>
                    <Divider component="li" />
                  </React.Fragment>
                ))}
              </List>
            ) : (
              <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
                No pending submissions to review.
              </Typography>
            )}
          </Box>
        )}

        {/* Completed Submissions Tab */}
        {activeTab === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Completed Reviews
            </Typography>
            {isLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <CircularProgress />
              </Box>
            ) : completedSubmissions.length > 0 ? (
              <List>
                {completedSubmissions.map((submission) => (
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
                No completed reviews yet.
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
                  theme={isDarkMode ? 'vs-dark' : 'light'}
                  beforeMount={(monaco) => {
                    // Ensure languages are registered
                    monaco.languages.getLanguages().forEach((lang) => {
                      console.log(`Language registered: ${lang.id}`)
                    })
                  }}
                  options={{
                    readOnly: true,
                    minimap: {
                      enabled: true,
                      showSlider: 'always',
                      renderCharacters: true,
                      maxColumn: 120,
                      scale: 1,
                    },
                    fontSize: 14,
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                    fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
                    fontLigatures: true,
                  }}
                />
              </Paper>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetailsOpen(false)}>Close</Button>
              {selectedSubmission.status === 'pending' && (
                <Button
                  variant="contained"
                  onClick={() => {
                    setDetailsOpen(false)
                    handleReviewSubmission(selectedSubmission)
                  }}
                >
                  Review This Submission
                </Button>
              )}
            </DialogActions>
          </Dialog>
        )}

        {/* Review Submission Dialog */}
        {selectedSubmission && (
          <Dialog
            open={reviewOpen}
            onClose={() => !isSubmitting && setReviewOpen(false)}
            maxWidth="lg"
            fullWidth
            PaperProps={{
              sx: { height: '90vh' },
            }}
          >
            <DialogTitle>Review Submission: {selectedSubmission.title}</DialogTitle>
            <DialogContent dividers>
              <Grid container spacing={2}>
                {/* Left side - Code content */}
                <Grid item xs={6}>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    Code to Review
                  </Typography>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 0,
                      height: 'calc(100% - 40px)',
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
                      theme={isDarkMode ? 'vs-dark' : 'light'}
                      beforeMount={(monaco) => {
                        // Ensure languages are registered
                        monaco.languages.getLanguages().forEach((lang) => {
                          console.log(`Language registered: ${lang.id}`)
                        })
                      }}
                      options={{
                        readOnly: true,
                        minimap: {
                          enabled: true,
                          showSlider: 'always',
                          renderCharacters: true,
                          maxColumn: 120,
                          scale: 1,
                        },
                        fontSize: 14,
                        lineNumbers: 'on',
                        scrollBeyondLastLine: false,
                        fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
                        fontLigatures: true,
                      }}
                    />
                  </Paper>
                </Grid>

                {/* Right side - Review form */}
                <Grid item xs={6}>
                  <Box sx={{ mb: 3 }}>
                    <FormControl component="fieldset" sx={{ mb: 2 }}>
                      <FormLabel component="legend">Review Status</FormLabel>
                      <Tabs
                        value={reviewStatus}
                        onChange={(e, newValue) => setReviewStatus(newValue)}
                        aria-label="review status"
                      >
                        <Tab label="Approve" value="approved" />
                        <Tab label="Reject" value="rejected" />
                        <Tab label="Request Revision" value="revision_requested" />
                      </Tabs>
                    </FormControl>

                    <FormControl component="fieldset" fullWidth sx={{ mb: 3 }}>
                      <FormLabel component="legend">Quality Assessment</FormLabel>
                      <Box sx={{ mt: 1, mb: 3 }}>
                        <Typography variant="body2" gutterBottom>
                          What is the quality of the task overall before you made edits? Rate 1-5
                        </Typography>
                        <Rating
                          name="quality-before"
                          value={qualityBefore}
                          onChange={(event, newValue) => {
                            setQualityBefore(newValue)
                          }}
                          max={5}
                          size="large"
                        />
                      </Box>

                      <TextField
                        label="What edits, if any, did you make to this task?"
                        multiline
                        rows={4}
                        fullWidth
                        value={editsMade}
                        onChange={(e) => setEditsMade(e.target.value)}
                        margin="normal"
                      />

                      <Box sx={{ mt: 3, mb: 3 }}>
                        <Typography variant="body2" gutterBottom>
                          What is the quality of the task overall after your edits? Rate 1-5
                        </Typography>
                        <Rating
                          name="quality-after"
                          value={qualityAfter}
                          onChange={(event, newValue) => {
                            setQualityAfter(newValue)
                          }}
                          max={5}
                          size="large"
                        />
                      </Box>

                      <FormGroup>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={isCustomerReady}
                              onChange={(e) => setIsCustomerReady(e.target.checked)}
                            />
                          }
                          label="Is this task good enough to send to the customer after the edits you have made?"
                        />
                      </FormGroup>
                    </FormControl>

                    <TextField
                      label="Comments"
                      multiline
                      rows={3}
                      fullWidth
                      value={comments}
                      onChange={(e) => setComments(e.target.value)}
                      margin="normal"
                    />

                    <TextField
                      label="Next steps to take"
                      multiline
                      rows={3}
                      fullWidth
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      margin="normal"
                    />
                  </Box>
                </Grid>
              </Grid>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setReviewOpen(false)} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button
                variant="contained"
                onClick={handleSubmitReview}
                disabled={isSubmitting || qualityBefore === null || qualityAfter === null}
              >
                {isSubmitting ? (
                  <>
                    <CircularProgress size={24} sx={{ mr: 1 }} color="inherit" />
                    Submitting...
                  </>
                ) : (
                  'Submit Review'
                )}
              </Button>
            </DialogActions>
          </Dialog>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default CodeReview
