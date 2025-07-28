import React from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  AppBar,
  Box,
  CssBaseline,
  Toolbar,
  Typography,
  Button,
  ThemeProvider,
  createTheme,
  IconButton,
  useMediaQuery
} from '@mui/material';
import { 
  Code as CodeIcon, 
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  Login as LoginIcon,
  Logout as LogoutIcon,
  AppRegistration as RegisterIcon
} from '@mui/icons-material';

const RootLayout = () => {
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [darkMode, setDarkMode] = React.useState(true);
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');
  
  React.useEffect(() => {
    setDarkMode(prefersDarkMode);
  }, [prefersDarkMode]);

  const theme = React.useMemo(
    () =>
      createTheme({
        palette: {
          mode: darkMode ? 'dark' : 'light',
          primary: {
            main: '#3f51b5',
          },
          secondary: {
            main: '#f50057',
          },
          background: {
            default: darkMode ? '#121212' : '#f5f5f5',
            paper: darkMode ? '#1e1e1e' : '#ffffff',
          },
        },
        typography: {
          fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
        },
      }),
    [darkMode],
  );

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <AppBar position="static" color="primary" elevation={0}>
          <Toolbar>
            <CodeIcon sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Terminus IDE
            </Typography>
            <IconButton color="inherit" onClick={toggleDarkMode}>
              {darkMode ? <LightModeIcon /> : <DarkModeIcon />}
            </IconButton>
            {isAuthenticated ? (
              <Button color="inherit" onClick={handleLogout} startIcon={<LogoutIcon />}>
                Logout
              </Button>
            ) : (
              <>
                <Button color="inherit" onClick={() => navigate('/login')} startIcon={<LoginIcon />}>
                  Login
                </Button>
                <Button color="inherit" onClick={() => navigate('/register')} startIcon={<RegisterIcon />}>
                  Register
                </Button>
              </>
            )}
          </Toolbar>
        </AppBar>
        <Box component="main" sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default RootLayout;
