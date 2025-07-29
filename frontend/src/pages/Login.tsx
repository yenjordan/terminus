import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Box,
  Paper,
  Typography,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
  CircularProgress,
} from '@mui/material'
import CodeIcon from '@mui/icons-material/Code'
import LoginForm from '../features/auth/LoginForm'
import { useToast } from '@/hooks/use-toast'

export default function Login() {
  const { toast } = useToast()

  // Delete account states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteConfirmDialogOpen, setDeleteConfirmDialogOpen] = useState(false)
  const [deleteEmail, setDeleteEmail] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [isDeleting, setIsDeleting] = useState(false)

  const handleOpenDeleteDialog = () => {
    setDeleteDialogOpen(true)
  }

  const handleCloseDeleteDialog = () => {
    setDeleteDialogOpen(false)
    setDeleteEmail('')
    setDeletePassword('')
  }

  const handleOpenDeleteConfirmDialog = () => {
    // Validate inputs
    if (!deleteEmail || !deletePassword) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Please enter both email and password',
      })
      return
    }

    setDeleteDialogOpen(false)
    setDeleteConfirmDialogOpen(true)
  }

  const handleCloseDeleteConfirmDialog = () => {
    setDeleteConfirmDialogOpen(false)
  }

  const handleDeleteAccount = async () => {
    setIsDeleting(true)

    try {
      const response = await fetch('/api/auth/delete-account', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: deleteEmail,
          password: deletePassword,
        }),
      })

      const data = await response.json()

      if (response.ok) {
        toast({
          title: 'Account Deleted',
          description: 'Your account has been successfully deleted',
        })
        setDeleteConfirmDialogOpen(false)
        setDeleteEmail('')
        setDeletePassword('')
      } else {
        toast({
          variant: 'destructive',
          title: 'Error',
          description: data.detail || 'Failed to delete account',
        })
      }
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'An unexpected error occurred',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Box
      sx={{
        height: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        p: 2,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          maxWidth: 500,
          width: '100%',
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <CodeIcon sx={{ fontSize: 40, mr: 1, color: 'primary.main' }} />
            <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
              Terminus IDE
            </Typography>
          </Box>
          <Typography variant="h5" component="h2" sx={{ mb: 1 }}>
            Sign in to your account
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Or{' '}
            <Link to="/register" style={{ color: 'inherit', fontWeight: 'bold' }}>
              create a new account
            </Link>
          </Typography>
        </Box>
        <LoginForm
          deleteAccountButton={
            <Button variant="text" color="error" onClick={handleOpenDeleteDialog} size="small">
              Delete Account
            </Button>
          }
        />
      </Paper>

      {/* Delete Account Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleCloseDeleteDialog}>
        <DialogTitle>Delete Account</DialogTitle>
        <DialogContent>
          <DialogContentText>
            To delete your account, please enter your email and password. This action cannot be
            undone.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            label="Email"
            type="email"
            fullWidth
            variant="outlined"
            value={deleteEmail}
            onChange={(e) => setDeleteEmail(e.target.value)}
            sx={{ mt: 2 }}
          />
          <TextField
            margin="dense"
            label="Password"
            type="password"
            fullWidth
            variant="outlined"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDeleteDialog} color="primary">
            Cancel
          </Button>
          <Button onClick={handleOpenDeleteConfirmDialog} color="error">
            Continue
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmation Dialog */}
      <Dialog open={deleteConfirmDialogOpen} onClose={handleCloseDeleteConfirmDialog}>
        <DialogTitle>Confirm Account Deletion</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you absolutely sure you want to delete your account? This will permanently delete:
            <ul>
              <li>Your user profile</li>
              <li>All your code sessions and files</li>
              <li>All code submissions you've made</li>
              <li>All code reviews you've performed</li>
            </ul>
            This action CANNOT be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDeleteConfirmDialog} color="primary">
            Cancel
          </Button>
          <Button
            onClick={handleDeleteAccount}
            color="error"
            disabled={isDeleting}
            startIcon={isDeleting ? <CircularProgress size={20} color="inherit" /> : null}
          >
            {isDeleting ? 'Deleting...' : 'Yes, Delete My Account'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
