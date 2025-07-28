import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Button,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Typography,
  Box,
  CircularProgress
} from '@mui/material';
import { KeyboardArrowDown as ArrowDownIcon } from '@mui/icons-material';

interface Session {
  id: number;
  name: string;
  description?: string;
  is_active: boolean;
  last_accessed: string;
  created_at: string;
  updated_at: string;
}

interface SessionManagerProps {
  currentSession: Session | null;
  onSessionChange: (session: Session) => void;
}

export const SessionManager: React.FC<SessionManagerProps> = ({ currentSession, onSessionChange }) => {
  const { token } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newSessionName, setNewSessionName] = useState('');
  const [newSessionDescription, setNewSessionDescription] = useState('');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  
  useEffect(() => {
    if (token) {
      loadSessions();
    }
  }, [token]);

  const loadSessions = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/sessions/', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const sessionsData = await response.json();
        setSessions(sessionsData);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateSession = async () => {
    if (!newSessionName.trim()) return;
    
    try {
      const response = await fetch('/api/sessions/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: newSessionName,
          description: newSessionDescription || undefined,
        }),
      });

      if (response.ok) {
        const newSession = await response.json();
        setSessions(prev => [...prev, newSession]);
        onSessionChange(newSession);
        setShowCreateDialog(false);
        setNewSessionName('');
        setNewSessionDescription('');
      }
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const handleSessionSelect = (session: Session) => {
    onSessionChange(session);
    setAnchorEl(null);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleCreateDialogOpen = () => {
    setShowCreateDialog(true);
    setAnchorEl(null);
  };

  const handleCreateDialogClose = () => {
    setShowCreateDialog(false);
    setNewSessionName('');
    setNewSessionDescription('');
  };

  return (
    <>
      <Button
        variant="outlined"
        onClick={handleMenuOpen}
        endIcon={<ArrowDownIcon />}
        disabled={isLoading}
        sx={{ minWidth: 150 }}
      >
        {isLoading ? (
          <CircularProgress size={16} sx={{ mr: 1 }} />
        ) : (
          currentSession?.name || "Select Session"
        )}
      </Button>
      
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        {sessions.map(session => (
          <MenuItem 
            key={session.id} 
            onClick={() => handleSessionSelect(session)}
            selected={currentSession?.id === session.id}
          >
            {session.name}
          </MenuItem>
        ))}
        <MenuItem onClick={handleCreateDialogOpen}>
          <Typography color="primary">+ New Session</Typography>
        </MenuItem>
      </Menu>

      <Dialog open={showCreateDialog} onClose={handleCreateDialogClose} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Session</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              autoFocus
              margin="dense"
              label="Session Name"
              fullWidth
              variant="outlined"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
            />
            <TextField
              margin="dense"
              label="Description (optional)"
              fullWidth
              variant="outlined"
              value={newSessionDescription}
              onChange={(e) => setNewSessionDescription(e.target.value)}
              multiline
              rows={2}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCreateDialogClose}>Cancel</Button>
          <Button 
            onClick={handleCreateSession} 
            variant="contained" 
            disabled={!newSessionName.trim()}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default SessionManager; 