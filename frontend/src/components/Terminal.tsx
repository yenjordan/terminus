import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { useAuth } from '../context/AuthContext';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import '@xterm/xterm/css/xterm.css';
import { useToast } from '@/hooks/use-toast';

interface TerminalProps {
  sessionId?: number;
  onFileChange?: () => void;
  onOutput?: (output: string) => void;
  inputData?: string;
  wsRef?: React.MutableRefObject<WebSocket | null>;
}

export const Terminal: React.FC<TerminalProps> = ({ 
  sessionId, 
  onFileChange, 
  onOutput, 
  inputData, 
  wsRef 
}) => {
  const { token } = useAuth();
  const theme = useTheme();
  const isDarkMode = theme.palette.mode === 'dark';
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const internalWsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const isConnectingRef = useRef<boolean>(false);
  const lastSessionIdRef = useRef<number | undefined>(undefined);
  const MAX_RECONNECT_ATTEMPTS = 10;
  const RECONNECT_DELAY = 3000; // 3 seconds
  const PING_INTERVAL = 30000; // 30 seconds - increased for stability
  const { toast } = useToast();

  // Helper function to handle reconnection
  const reconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      // Don't show error message
      return;
    }
    
    reconnectAttemptsRef.current += 1;
    
    // Attempt to reconnect after a delay
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    reconnectTimeoutRef.current = setTimeout(() => {
      // Don't show reconnecting message
      connectWebSocket();
    }, RECONNECT_DELAY);
  }, []);

  // Memoized connect function to prevent unnecessary reconnections
  const connectWebSocket = useCallback(() => {
    if (isConnectingRef.current || !sessionId || !token) {
      return;
    }

    // If we're already connected to this session, don't reconnect
    if (lastSessionIdRef.current === sessionId && internalWsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    // Close existing connection if we're switching sessions
    if (internalWsRef.current) {
      console.log(`Closing existing WebSocket for session ${lastSessionIdRef.current} to connect to session ${sessionId}`);
      internalWsRef.current.close();
      internalWsRef.current = null;
      setIsConnected(false); // Reset connection state
    }

    // Update the last session ID
    lastSessionIdRef.current = sessionId;
    
    isConnectingRef.current = true;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Get the correct backend URL based on the environment
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = process.env.NODE_ENV === 'development' ? '8000' : window.location.port;
    
    const wsUrl = `${protocol}//${host}:${port}/api/terminal/ws/${sessionId}?token=${token}`;
    console.log(`Connecting to WebSocket: ${wsUrl}`);
    
    try {
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('WebSocket opened, waiting for backend confirmation');
        isConnectingRef.current = false;
        reconnectAttemptsRef.current = 0; // Reset reconnect attempts on successful connection
        
        // Don't show connecting message
        
        // Start sending ping every interval to keep connection alive
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            try {
              ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
            } catch (error) {
              console.error('Failed to send ping:', error);
              // If ping fails, try to reconnect
              if (ws.readyState !== WebSocket.OPEN) {
                reconnect();
              }
            }
          }
        }, PING_INTERVAL);
      };
  
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('WebSocket message received:', message.type);
          handleWebSocketMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };
  
      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        isConnectingRef.current = false;
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Only reconnect if it wasn't a normal close, but don't show messages
        if (event.code !== 1000 && event.code !== 1001) {
          // Only reconnect if we haven't exceeded max attempts
          if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
            reconnect();
          }
        }
      };
  
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        isConnectingRef.current = false;
        // Don't show error message
        
        // Don't reconnect here, let the onclose handler do it
      };
  
      internalWsRef.current = ws;
      
      // Share the WebSocket reference with the parent component
      if (wsRef) {
        wsRef.current = ws;
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      isConnectingRef.current = false;
      // Don't show error message
      
      // Only reconnect if we haven't exceeded max attempts
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnect();
      }
    }
  }, [sessionId, token, reconnect, wsRef]);

  // Initialize terminal immediately when component mounts
  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm.js
    const xterm = new XTerm({
      fontSize: 14,
      fontFamily: '"Fira Code", Menlo, "Ubuntu Mono", monospace',
      cursorBlink: true,
      rows: 24,
      cols: 80,
      cursorStyle: 'block',
      allowTransparency: true
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    
    xterm.loadAddon(fitAddon);
    xterm.loadAddon(webLinksAddon);
    
    xterm.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = xterm;
    fitAddonRef.current = fitAddon;

    // Handle terminal input (user typing)
    xterm.onData((data) => {
      // Send all input directly to the shell session
      sendShellInput(data);
    });

    // Handle terminal resize
    xterm.onResize(({ cols, rows }) => {
      sendShellResize(cols, rows);
    });

    // Handle window resize
    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (internalWsRef.current) {
        internalWsRef.current.close();
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      xterm.dispose();
    };
  }, []); // Only run once when component mounts

  // Connect to WebSocket when sessionId or token changes
  useEffect(() => {
    if (sessionId && token) {
      console.log(`Session ID changed to ${sessionId}, connecting WebSocket`);
      connectWebSocket();
    }
    
    // When session changes, focus the terminal
    if (xtermRef.current) {
      setTimeout(() => {
        if (xtermRef.current) {
          xtermRef.current.focus();
          console.log('Terminal focused after session change');
        }
      }, 500);
    }
  }, [sessionId, token, connectWebSocket]);

  // Focus the terminal when isConnected changes to true
  useEffect(() => {
    if (isConnected && xtermRef.current) {
      setTimeout(() => {
        if (xtermRef.current) {
          xtermRef.current.focus();
          console.log('Terminal focused after connection');
        }
      }, 100);
    }
  }, [isConnected]);

  // Update terminal theme when dark mode changes
  useEffect(() => {
    if (!xtermRef.current) return;
    
    const darkTheme = {
      background: '#1e1e1e',
      foreground: '#ffffff',
      cursor: '#ffffff',
      black: '#000000',
      red: '#ff5555',
      green: '#50fa7b',
      yellow: '#f1fa8c',
      blue: '#bd93f9',
      magenta: '#ff79c6',
      cyan: '#8be9fd',
      white: '#bbbbbb',
      brightBlack: '#44475a',
      brightRed: '#ff5555',
      brightGreen: '#50fa7b',
      brightYellow: '#f1fa8c',
      brightBlue: '#bd93f9',
      brightMagenta: '#ff79c6',
      brightCyan: '#8be9fd',
      brightWhite: '#ffffff',
    };
    
    const lightTheme = {
      background: '#ffffff',
      foreground: '#333333',
      cursor: '#333333',
      black: '#000000',
      red: '#c91b00',
      green: '#00c200',
      yellow: '#c7c400',
      blue: '#0037da',
      magenta: '#c839c5',
      cyan: '#00c5c7',
      white: '#c7c7c7',
      brightBlack: '#767676',
      brightRed: '#e74856',
      brightGreen: '#16c60c',
      brightYellow: '#f9f1a5',
      brightBlue: '#3b78ff',
      brightMagenta: '#b4009e',
      brightCyan: '#61d6d6',
      brightWhite: '#f2f2f2',
    };
    
    // Update the theme without reinitializing
    xtermRef.current.options.theme = isDarkMode ? darkTheme : lightTheme;
    
  }, [isDarkMode]);

  const handleWebSocketMessage = (message: any) => {
    if (!message || !message.type) {
      console.error('Invalid message received:', message);
      return;
    }

    // Early return if xterm is not available
    if (!xtermRef.current) {
      console.log('Terminal not initialized yet, buffering message:', message.type);
      return;
    }

    switch (message.type) {
      case 'shell_output':
        if (message.data) {
          // Process the output to replace the default prompt with our custom prompt
          const processedOutput = processTerminalOutput(message.data);
          
          // Write the processed output to the terminal
          xtermRef.current.write(processedOutput);
          
          // Call the onOutput callback if provided
          if (onOutput) {
            onOutput(processedOutput);
          }
        }
        break;
        
      case 'connected':
        // Backend confirms we're fully connected - update state
        setIsConnected(true);
        // Don't show connection messages
        break;
        
      case 'terminal_result':
      case 'code_execution_result':
        const result = message.result;
        if (result.output) {
          xtermRef.current.write(result.output);
          if (onOutput) {
            onOutput(result.output);
          }
        }
        if (result.error) {
          xtermRef.current.writeln(`\x1b[31m${result.error}\x1b[0m`);
          if (onOutput) {
            onOutput(`Error: ${result.error}`);
          }
        }
        writePrompt();
        break;
        
      case 'file_operation_result':
        const fileResult = message.result;
        if (fileResult.success) {
          xtermRef.current.writeln(`\x1b[32m${fileResult.message}\x1b[0m`);
        } else {
          xtermRef.current.writeln(`\x1b[31mError: ${fileResult.error}\x1b[0m`);
        }
        writePrompt();
        break;
        
      case 'input_data_received':
        xtermRef.current.writeln(`\x1b[33m${message.message}\x1b[0m`);
        writePrompt();
        break;
        
      case 'error':
        // Don't show error messages from the server
        writePrompt();
        break;
        
      case 'pong':
        // Handle ping response - no action needed
        break;
        
      case 'file_sync_complete':
        // File sync completed successfully - just log to console, don't show in terminal
        console.log('File sync completed:', message.message);
        break;
        
      default:
        console.log('Unknown message type:', message.type);
    }
  };

  // Process terminal output to replace default prompt with custom prompt
  const processTerminalOutput = (output: string): string => {
    // Replace any prompt that matches the pattern "user@hostname:path# " with our custom prompt
    let processedOutput = output.replace(/[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+:~#\s/g, "@terminuside:~# ");
    
    return processedOutput;
  };

  const writePrompt = () => {
    if (xtermRef.current && isConnected) {
      // Don't write a prompt for shell mode - the shell handles its own prompt
    }
  };

  const sendShellInput = (data: string) => {
    console.log('sendShellInput called:', { 
      data: data.charCodeAt(0), // Log char code for debugging
      isConnected, 
      wsReadyState: internalWsRef.current?.readyState,
      wsStates: { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 }
    });
    
    if (internalWsRef.current && internalWsRef.current.readyState === WebSocket.OPEN) {
      console.log('Sending shell input:', data.charCodeAt(0));
      internalWsRef.current.send(JSON.stringify({
        type: 'shell_input',
        data: data
      }));
    } else {
      console.error('Cannot send shell input:', { 
        hasWs: !!internalWsRef.current, 
        isConnected, 
        wsReadyState: internalWsRef.current?.readyState,
        readyStateNames: {
          0: 'CONNECTING',
          1: 'OPEN', 
          2: 'CLOSING',
          3: 'CLOSED'
        }
      });
      
      // Try to reconnect if the WebSocket is closed
      if (!internalWsRef.current || internalWsRef.current.readyState === WebSocket.CLOSED) {
        console.log('WebSocket is closed, attempting to reconnect');
        connectWebSocket();
      }
    }
  };

  const sendShellResize = (cols: number, rows: number) => {
    if (internalWsRef.current && internalWsRef.current.readyState === WebSocket.OPEN) {
      internalWsRef.current.send(JSON.stringify({
        type: 'shell_resize',
        cols: cols,
        rows: rows
      }));
    }
  };

  // Execute command function for Run Code button
  const executeCommand = async (command: string, inputData?: string) => {
    if (!internalWsRef.current || !isConnected) {
      console.error('Not connected to terminal server');
      return;
    }

    try {
      // For code execution, send the execute_code message
      internalWsRef.current.send(JSON.stringify({
        type: 'execute_code',
        code: command,
        input_data: inputData
      }));
    } catch (error) {
      console.error('Failed to execute command:', error);
    }
  };

  // Effect to handle input data changes
  useEffect(() => {
    if (inputData && internalWsRef.current && isConnected) {
      // Send input data to the backend when it changes
      internalWsRef.current.send(JSON.stringify({
        type: 'input_data',
        content: inputData
      }));
    }
  }, [inputData, isConnected]);

  // Focus the terminal on click
  const handleTerminalClick = () => {
    if (xtermRef.current) {
      xtermRef.current.focus();
    }
  };

  if (!sessionId) {
    return (
      <Box 
        sx={{ 
          height: '100%', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          bgcolor: 'background.paper'
        }}
      >
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h4" sx={{ mb: 2 }}>💻</Typography>
          <Typography variant="h6" sx={{ mb: 1 }}>No session selected</Typography>
          <Typography variant="body2" color="text.secondary">
            Select a session to start using the terminal.
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Paper 
      elevation={0} 
      sx={{ 
        height: '100%', 
        bgcolor: isDarkMode ? '#1e1e1e' : '#ffffff', 
        borderRadius: 1,
        overflow: 'hidden',
        border: '1px solid',
        borderColor: 'divider'
      }}
      onClick={handleTerminalClick}
    >
      <Box 
        ref={terminalRef} 
        sx={{ 
          height: '100%', 
          width: '100%',
          padding: '8px'
        }}
      />
    </Paper>
  );
};

export default Terminal; 