import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Box, TextField, Button, Typography, CircularProgress, FormControl, FormLabel, RadioGroup, FormControlLabel, Radio } from '@mui/material'
import { useAuth } from '@/context/AuthContext'
import { useToast } from '@/hooks/use-toast'

export default function RegisterForm() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [role, setRole] = useState<'attempter' | 'reviewer'>('attempter')

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email') as string
    const username = formData.get('username') as string
    const password = formData.get('password') as string
    const confirmPassword = formData.get('confirmPassword') as string

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      setIsLoading(false)
      return
    }

    const result = await register({ email, username, password, confirmPassword, role })

    if (result.success) {
      toast({
        title: 'Registration successful!',
        description: 'Your account has been created.',
      })
      navigate('/dashboard')
    } else {
      setError(result.error || 'An error occurred during registration')
      toast({
        variant: 'destructive',
        title: 'Error',
        description: result.error || 'An error occurred during registration',
      })
    }

    setIsLoading(false)
  }

  const textFieldSx = {
    '& .MuiOutlinedInput-root': {
      '&.Mui-focused fieldset': {
        borderColor: 'rgba(144, 202, 249, 0.6)', // Lighter blue border
      },
      // Remove the background fill color
      '&.Mui-focused': {
        backgroundColor: 'transparent',
      },
      // Ensure background is always transparent
      backgroundColor: 'transparent',
    },
    '& .MuiInputLabel-root.Mui-focused': {
      color: 'rgba(144, 202, 249, 0.8)', // Lighter blue for label
    }
  };

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
        />
      </Box>
      <Box sx={{ mb: 2 }}>
        <TextField
          id="username"
          name="username"
          type="text"
          label="Username"
          placeholder="Choose a username"
          required
          disabled={isLoading}
          fullWidth
          variant="outlined"
          margin="normal"
          autoComplete="username"
          sx={textFieldSx}
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
          autoComplete="new-password"
          sx={textFieldSx}
        />
      </Box>
      <Box sx={{ mb: 2 }}>
        <TextField
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          label="Confirm Password"
          placeholder="Confirm your password"
          required
          disabled={isLoading}
          fullWidth
          variant="outlined"
          margin="normal"
          autoComplete="new-password"
          sx={textFieldSx}
        />
      </Box>
      <Box sx={{ mb: 2 }}>
        <FormControl component="fieldset">
          <FormLabel component="legend">Register as</FormLabel>
          <RadioGroup
            row
            name="role"
            value={role}
            onChange={(e) => setRole(e.target.value as 'attempter' | 'reviewer')}
          >
            <FormControlLabel value="attempter" control={<Radio />} label="Attempter" />
            <FormControlLabel value="reviewer" control={<Radio />} label="Reviewer" />
          </RadioGroup>
        </FormControl>
      </Box>
      {error && (
        <Typography color="error" variant="body2" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
        <Button
          variant="outlined"
          onClick={() => navigate('/login')}
          type="button"
          disabled={isLoading}
        >
          Login
        </Button>
        <Button 
          type="submit" 
          variant="contained" 
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {isLoading ? 'Creating account...' : 'Register'}
        </Button>
      </Box>
    </form>
  )
}
