import { Link } from 'react-router-dom'
import LoginForm from '../features/auth/LoginForm'
import { Box, Paper, Typography } from '@mui/material'
import CodeIcon from '@mui/icons-material/Code'

export default function Login() {
  return (
    <Box sx={{ 
      height: 'calc(100vh - 64px)', 
      display: 'flex', 
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      bgcolor: 'background.default',
      p: 2
    }}>
      <Paper 
        elevation={0} 
        sx={{ 
          maxWidth: 500,
          width: '100%',
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1
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
        <LoginForm />
      </Paper>
    </Box>
  )
}
