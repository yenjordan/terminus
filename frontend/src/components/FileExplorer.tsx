import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  IconButton,
  TextField,
  Button,
  Collapse,
  Divider,
  Paper,
  Tooltip,
  Menu,
  MenuItem
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ChevronRight as ChevronRightIcon,
  CreateNewFolder as CreateNewFolderIcon,
  NoteAdd as NoteAddIcon,
  Upload as UploadIcon,
  Description as FileIcon,
  Code as CodeIcon,
  TextSnippet as TextIcon,
  Javascript as JsIcon,
  Html as HtmlIcon,
  Css as CssIcon,
  InsertDriveFile as GenericFileIcon,
  CleaningServices as CleanupIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';
import { useAuth } from '../context/AuthContext';

interface CodeFile {
  id: number;
  name: string;
  path: string;
  content: string;
  file_type: string;
  session_id: number;
  size_bytes: number;
  created_at: string;
  updated_at: string;
}

interface FileExplorerProps {
  files: CodeFile[];
  currentFile: CodeFile | null;
  onFileSelect: (file: CodeFile) => void;
  onCreateFile: (name: string, path: string) => void;
  onUploadFile?: (file: File) => void;
  currentSession?: { id: number } | null;
  onFilesUpdated?: () => void;
  onDeleteFile?: (fileId: number) => Promise<boolean>;
}

export const FileExplorer: React.FC<FileExplorerProps> = ({
  files,
  currentFile,
  onFileSelect,
  onCreateFile,
  onUploadFile,
  currentSession,
  onFilesUpdated,
  onDeleteFile
}) => {
  const { token } = useAuth();
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [expandedDirectories, setExpandedDirectories] = useState<Set<string>>(new Set(['/']));
  const [isCleaningUp, setIsCleaningUp] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    file: CodeFile | null;
  } | null>(null);

  useEffect(() => {
    // Automatically expand parent directories of the current file
    if (currentFile) {
      const pathParts = currentFile.path.split('/').filter(p => p);
      if (pathParts.length > 1) {
        let currentPath = '/';
        const newExpanded = new Set(expandedDirectories);
        for (let i = 0; i < pathParts.length - 1; i++) {
          currentPath += pathParts[i] + '/';
          newExpanded.add(currentPath);
        }
        setExpandedDirectories(newExpanded);
      }
    }
  }, [currentFile, expandedDirectories]);

  // Organize files into a directory structure
  const fileTree = React.useMemo(() => {
    const tree: Record<string, CodeFile[]> = {};
    
    // Initialize root directory
    tree['/'] = [];
    
    // Group files by directory
    files.forEach(file => {
      const lastSlashIndex = file.path.lastIndexOf('/');
      const directory = lastSlashIndex === 0 ? '/' : file.path.substring(0, lastSlashIndex + 1);
      
      if (!tree[directory]) {
        tree[directory] = [];
      }
      
      tree[directory].push(file);
    });
    
    return tree;
  }, [files]);

  // Get all unique directories
  const directories = React.useMemo(() => {
    const dirs = new Set<string>();
    dirs.add('/');
    
    files.forEach(file => {
      const pathParts = file.path.split('/').filter(p => p);
      let currentPath = '/';
      
      pathParts.forEach((part, index) => {
        if (index < pathParts.length - 1) {
          currentPath += part + '/';
          dirs.add(currentPath);
        }
      });
    });
    
    return Array.from(dirs).sort();
  }, [files]);

  const toggleDirectory = (directory: string) => {
    const newExpanded = new Set(expandedDirectories);
    if (newExpanded.has(directory)) {
      newExpanded.delete(directory);
    } else {
      newExpanded.add(directory);
    }
    setExpandedDirectories(newExpanded);
  };

  const handleCreateFile = () => {
    if (newFileName.trim()) {
      // Determine the path based on the selected directory
      const selectedDir = Array.from(expandedDirectories).sort((a, b) => b.length - a.length)[0] || '/';
      const path = selectedDir === '/' ? `/${newFileName}` : `${selectedDir}${newFileName}`;
      
      onCreateFile(newFileName, path);
      setNewFileName('');
      setIsCreatingFile(false);
    }
  };

  const handleUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0 && onUploadFile) {
      onUploadFile(e.target.files[0]);
    }
  };

  const handleCleanupFiles = async () => {
    if (!currentSession) return;
    
    try {
      setIsCleaningUp(true);
      
      const response = await fetch(`/api/files/session/${currentSession.id}/cleanup`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (response.ok) {
        console.log('Files cleaned up successfully');
        // Refresh file list
        if (onFilesUpdated) {
          onFilesUpdated();
        }
      } else {
        console.error('Failed to clean up files:', response.statusText);
      }
    } catch (error) {
      console.error('Error cleaning up files:', error);
    } finally {
      setIsCleaningUp(false);
    }
  };

  // Context menu handlers
  const handleContextMenu = (event: React.MouseEvent, file: CodeFile) => {
    event.preventDefault();
    setContextMenu({
      mouseX: event.clientX - 2,
      mouseY: event.clientY - 4,
      file: file
    });
  };

  const handleContextMenuClose = () => {
    setContextMenu(null);
  };

  const handleDeleteFile = async () => {
    if (contextMenu?.file && onDeleteFile) {
      const success = await onDeleteFile(contextMenu.file.id);
      if (success && onFilesUpdated) {
        onFilesUpdated();
      }
    }
    handleContextMenuClose();
  };

  // Get file icon based on file type
  const getFileIcon = (fileName: string) => {
    const extension = fileName.split('.').pop()?.toLowerCase() || '';
    
    switch (extension) {
      case 'py':
        return <CodeIcon color="primary" />;
      case 'js':
      case 'jsx':
        return <JsIcon color="warning" />;
      case 'ts':
      case 'tsx':
        return <CodeIcon color="info" />;
      case 'html':
        return <HtmlIcon color="error" />;
      case 'css':
        return <CssIcon color="secondary" />;
      case 'json':
        return <TextIcon color="success" />;
      case 'md':
        return <TextIcon />;
      default:
        return <GenericFileIcon />;
    }
  };

  return (
    <Paper 
      elevation={0}
      sx={{ 
        height: '100%', 
        bgcolor: 'background.paper', 
        display: 'flex', 
        flexDirection: 'column',
        borderRight: 1,
        borderColor: 'divider'
      }}
    >
      <Box sx={{ p: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>Files</Typography>
        <Box>
          <Tooltip title="New File">
            <IconButton size="small" onClick={() => setIsCreatingFile(true)}>
              <NoteAddIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Upload File">
            <IconButton size="small" onClick={handleUploadClick}>
              <UploadIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
        </Box>
      </Box>
      
      {isCreatingFile && (
        <Box sx={{ p: 1, borderBottom: 1, borderColor: 'divider' }}>
          <TextField
            size="small"
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            placeholder="filename.py"
            variant="outlined"
            fullWidth
            autoFocus
            InputProps={{
              sx: { fontSize: '0.875rem' }
            }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
            <Button 
              size="small" 
              onClick={() => setIsCreatingFile(false)} 
              sx={{ mr: 1 }}
            >
              Cancel
            </Button>
            <Button 
              size="small" 
              variant="contained" 
              onClick={handleCreateFile}
              disabled={!newFileName.trim()}
            >
              Create
            </Button>
          </Box>
        </Box>
      )}
      
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <List dense disablePadding>
          {directories.map(directory => {
            const isExpanded = expandedDirectories.has(directory);
            const directoryFiles = fileTree[directory] || [];
            const dirName = directory === '/' ? 'Root' : directory.split('/').filter(Boolean).pop() || '';
            
            // Skip empty directories
            if (directory !== '/' && directoryFiles.length === 0) return null;
            
            return (
              <React.Fragment key={directory}>
                <ListItemButton 
                  onClick={() => toggleDirectory(directory)}
                  sx={{ 
                    py: 0.5, 
                    pl: directory === '/' ? 1 : 1 + (directory.split('/').length - 1) * 1.5
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 24 }}>
                    {isExpanded ? 
                      <ExpandMoreIcon fontSize="small" /> : 
                      <ChevronRightIcon fontSize="small" />
                    }
                  </ListItemIcon>
                  <ListItemText 
                    primary={dirName} 
                    primaryTypographyProps={{ 
                      variant: 'body2',
                      fontWeight: 'medium'
                    }} 
                  />
                </ListItemButton>
                
                <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                  {directoryFiles.map(file => (
                    <ListItemButton
                      key={file.id}
                      selected={currentFile?.id === file.id}
                      onClick={() => onFileSelect(file)}
                      onContextMenu={(e) => handleContextMenu(e, file)}
                      sx={{ 
                        py: 0.5, 
                        pl: directory === '/' ? 4 : 4 + (directory.split('/').length - 1) * 1.5
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 24 }}>
                        {getFileIcon(file.name)}
                      </ListItemIcon>
                      <ListItemText 
                        primary={file.name} 
                        primaryTypographyProps={{ 
                          variant: 'body2',
                          noWrap: true
                        }}
                      />
                    </ListItemButton>
                  ))}
                </Collapse>
              </React.Fragment>
            );
          })}
        </List>
      </Box>
      
      {/* Context Menu */}
      <Menu
        open={contextMenu !== null}
        onClose={handleContextMenuClose}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu !== null
            ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
            : undefined
        }
      >
        <MenuItem onClick={handleDeleteFile} dense>
          <ListItemIcon>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>
    </Paper>
  );
};

export default FileExplorer; 