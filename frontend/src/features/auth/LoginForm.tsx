import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Box, TextField, Button, Typography, CircularProgress } from '@mui/material'
import { useAuth } from '@/context/AuthContext'
import { useToast } from '@/hooks/use-toast'

interface LoginFormProps {
  deleteAccountButton?: React.ReactNode
}

export default function LoginForm({ deleteAccountButton }: LoginFormProps) {
  const navigate = useNavigate()
  const { login } = useAuth()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email') as string
    const password = formData.get('password') as string

    const result = await login({ email, password })

    if (result.success) {
      toast({
        title: 'Welcome back!',
        description: 'You have successfully logged in.',
      })
      navigate('/')
    } else {
      setError(result.error || 'An error occurred during login')
      toast({
        variant: 'destructive',
        title: 'Error',
        description: result.error || 'An error occurred during login',
      })
    }

    setIsLoading(false)
  }

  const textFieldSx = {
    '& .MuiOutlinedInput-root': {
      '&.Mui-focused fieldset': {
        borderColor: 'rgba(144, 202, 249, 0.6)', // Lighter blue border
      },
      // removing any background fill color
      backgroundColor: 'transparent',
      '&.Mui-focused': {
        backgroundColor: 'transparent',
      },
      // removing the filled style
      '&.MuiFilledInput-root': {
        backgroundColor: 'transparent',
        '&:hover': {
          backgroundColor: 'transparent',
        },
        '&.Mui-focused': {
          backgroundColor: 'transparent',
        },
      },
    },
    '& .MuiInputLabel-root.Mui-focused': {
      color: 'rgba(144, 202, 249, 0.8)',
    },
    '& .MuiInputBase-input': {
      backgroundColor: 'transparent',
    },
  }

  return (
    <form onSubmit={onSubmit}>
      <Box sx={{ mb: 2 }}>
        <TextField
          id="email"
          name="email"
          type="email"
          label="Email"
          placeholder="name@example.com"
          required
          disabled={isLoading}
          fullWidth
          variant="outlined"
          margin="normal"
          autoComplete="email"
          autoFocus
          sx={textFieldSx}
          InputProps={{
            sx: { backgroundColor: 'transparent' },
          }}
        />
      </Box>
      <Box sx={{ mb: 2 }}>
        <TextField
          id="password"
          name="password"
          type="password"
          label="Password"
          placeholder="Enter your password"
          required
          disabled={isLoading}
          fullWidth
          variant="outlined"
          margin="normal"
          autoComplete="current-password"
          sx={textFieldSx}
          InputProps={{
            sx: { backgroundColor: 'transparent' },
          }}
        />
      </Box>
      {error && (
        <Typography color="error" variant="body2" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            onClick={() => navigate('/register')}
            type="button"
            disabled={isLoading}
          >
            Register
          </Button>
          {deleteAccountButton}
        </Box>
        <Button
          type="submit"
          variant="contained"
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {isLoading ? 'Logging in...' : 'Login'}
        </Button>
      </Box>
    </form>
  )
}
