import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { useAuth } from '../context/AuthContext'
import { Box, Paper, Typography, useTheme } from '@mui/material'
import '@xterm/xterm/css/xterm.css'
import { useToast } from '@/hooks/use-toast'

interface TerminalProps {
  sessionId?: number
  onFileChange?: () => void
  onOutput?: (output: string) => void
  inputData?: string
  wsRef?: React.MutableRefObject<WebSocket | null>
}

export const Terminal: React.FC<TerminalProps> = ({
  sessionId,
  onFileChange,
  onOutput,
  inputData,
  wsRef,
}) => {
  const { token } = useAuth()
  const theme = useTheme()
  const isDarkMode = theme.palette.mode === 'dark'
  const terminalRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const internalWsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const isConnectingRef = useRef<boolean>(false)
  const lastSessionIdRef = useRef<number | undefined>(undefined)
  const focusAttemptsRef = useRef<number>(0)
  const MAX_RECONNECT_ATTEMPTS = 10
  const RECONNECT_DELAY = 3000 // 3 seconds
  const PING_INTERVAL = 30000 // 30 seconds
  const MAX_FOCUS_ATTEMPTS = 10
  const FOCUS_DELAY = 500 // 500ms between focus attempts
  const { toast } = useToast()

  const ensureTerminalFocus = useCallback(() => {
    if (xtermRef.current) {
      xtermRef.current.focus()
      console.log('Terminal focus applied')
    }
  }, [])

  // helper function to handle reconnection
  const reconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      // Don't show error message
      return
    }

    reconnectAttemptsRef.current += 1

    // attempt to reconnect after a delay
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }

    reconnectTimeoutRef.current = setTimeout(() => {
      // don't show reconnecting message
      connectWebSocket()
    }, RECONNECT_DELAY)
  }, [])

  // helper function to focus the terminal with multiple attempts
  const focusTerminal = useCallback(() => {
    if (!xtermRef.current) return

    // reset focus attempts
    focusAttemptsRef.current = 0

    const attemptFocus = () => {
      if (focusAttemptsRef.current >= MAX_FOCUS_ATTEMPTS) return

      if (xtermRef.current) {
        console.log(`Terminal focus attempt ${focusAttemptsRef.current + 1}/${MAX_FOCUS_ATTEMPTS}`)
        xtermRef.current.focus()

        // increment attempt counter
        focusAttemptsRef.current++

        // schedule another attempt
        setTimeout(attemptFocus, FOCUS_DELAY)
      }
    }

    //start attempting to focus
    attemptFocus()
  }, [])

  // memoized connect function to prevent unnecessary reconnections
  const connectWebSocket = useCallback(() => {
    if (!sessionId || !token) {
      console.log('Cannot connect WebSocket: missing sessionId or token')
      return
    }

    console.log(`Attempting to connect WebSocket for session ${sessionId}`)

    // always close existing connection when connecting to a new session
    if (internalWsRef.current) {
      console.log(
        `Closing existing WebSocket for session ${lastSessionIdRef.current} to connect to session ${sessionId}`
      )
      try {
        internalWsRef.current.close()
      } catch (e) {
        console.error('Error closing existing WebSocket:', e)
      }
      internalWsRef.current = null
      setIsConnected(false) // reset connection state
    }

    // update the last session ID
    lastSessionIdRef.current = sessionId

    // get the correct backend URL based on the environment
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    // don't add colon if using default port
    const portPart = process.env.NODE_ENV === 'development' ? ':8000' : ''

    // fix the URL format - remove extra colon
    const wsUrl = `${protocol}//${host}${portPart}/api/terminal/ws/${sessionId}?token=${token}`
    console.log(`Connecting to WebSocket: ${wsUrl}`)

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('WebSocket opened, waiting for backend confirmation')

        // send an initial ping to establish the connection fully
        setTimeout(() => {
          if (ws.readyState === WebSocket.OPEN) {
            try {
              ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
              console.log('Initial ping sent to establish connection')

              // send a second ping to ensure connection is fully established
              setTimeout(() => {
                if (ws.readyState === WebSocket.OPEN) {
                  ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
                  console.log('Follow-up ping sent to verify connection')
                }
              }, 100)

              // focus the terminal after sending initial ping
              if (xtermRef.current) {
                xtermRef.current.focus()
              }
            } catch (error) {
              console.error('Failed to send initial ping:', error)
            }
          }
        }, 100)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleWebSocketMessage(data)
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      ws.onclose = (event) => {
        console.log(`WebSocket closed with code ${event.code}, reason: ${event.reason}`)
        setIsConnected(false)
      }

      ws.onerror = (event) => {
        console.error('WebSocket error:', event)
      }

      internalWsRef.current = ws

      // update external ref if provided
      if (wsRef) {
        wsRef.current = ws
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
    }
  }, [sessionId, token, wsRef])

  // update the terminal initialization to use a simpler focus approach
  useEffect(() => {
    if (terminalRef.current && !xtermRef.current) {
      console.log('Initializing terminal')
      const xterm = new XTerm({
        fontSize: 14,
        fontFamily: '"Fira Code", Menlo, "Ubuntu Mono", monospace',
        cursorBlink: true,
        rows: 24,
        cols: 80,
        cursorStyle: 'block',
        allowTransparency: true,
        convertEol: true, // make sure \n is properly converted to CRLF
        disableStdin: false, // Make sure input is enabled
        theme: isDarkMode
          ? {
              background: '#1e1e1e',
              foreground: '#ffffff',
              cursor: '#ffffff',
            }
          : {
              background: '#ffffff',
              foreground: '#333333',
              cursor: '#333333',
            },
      })

      const fitAddon = new FitAddon()
      xterm.loadAddon(fitAddon)
      xterm.loadAddon(new WebLinksAddon())

      // open the terminal in the container
      xterm.open(terminalRef.current)

      // fit the terminal to the container
      try {
        fitAddon.fit()
      } catch (e) {
        console.error('Failed to fit terminal:', e)
      }

      // store references
      xtermRef.current = xterm
      fitAddonRef.current = fitAddon

      // add handleResize function definition
      const handleResize = () => {
        if (fitAddonRef.current && xtermRef.current) {
          try {
            fitAddonRef.current.fit()

            // send the new terminal size to the backend
            const { cols, rows } = xtermRef.current
            sendShellResize(cols, rows)
          } catch (e) {
            console.error('Failed to resize terminal:', e)
          }
        }
      }

      // handle input
      xterm.onData((data) => {
        sendShellInput(data)
      })

      // handle resize
      const resizeObserver = new ResizeObserver(() => {
        handleResize()
      })
      resizeObserver.observe(terminalRef.current)

      // focus the terminal immediately
      setTimeout(() => {
        if (xtermRef.current) {
          xtermRef.current.focus()
        }
      }, 100)

      // cleanup function
      return () => {
        console.log('Cleaning up terminal')
        resizeObserver.disconnect()
        xterm.dispose()
        xtermRef.current = null
        fitAddonRef.current = null
      }
    }
  }, [terminalRef, isDarkMode])

  // remove the continuous focus monitoring useEffect completely

  // connect WebSocket when sessionId changes
  useEffect(() => {
    if (sessionId) {
      console.log(`Session ID changed to ${sessionId}, connecting WebSocket...`)

      // connect immediately without delay
      connectWebSocket()

      // also focus terminal immediately
      if (xtermRef.current) {
        xtermRef.current.focus()
      }

      // then start the focus attempts for reliability
      setTimeout(() => {
        focusTerminal()
      }, 100)

      // add multiple backup connection attempts in case the first one fails
      const backupTimeouts: NodeJS.Timeout[] = []

      // first backup attempt after 1 second
      const firstBackup = setTimeout(() => {
        if (
          !isConnected &&
          (!internalWsRef.current || internalWsRef.current.readyState !== WebSocket.OPEN)
        ) {
          console.log('First backup connection attempt triggered')
          connectWebSocket()
        }
      }, 1000)
      backupTimeouts.push(firstBackup)

      // second backup attempt after 3 seconds
      const secondBackup = setTimeout(() => {
        if (
          !isConnected &&
          (!internalWsRef.current || internalWsRef.current.readyState !== WebSocket.OPEN)
        ) {
          console.log('Second backup connection attempt triggered')
          connectWebSocket()
        }
      }, 3000)
      backupTimeouts.push(secondBackup)

      // third backup attempt after 6 seconds
      const thirdBackup = setTimeout(() => {
        if (
          !isConnected &&
          (!internalWsRef.current || internalWsRef.current.readyState !== WebSocket.OPEN)
        ) {
          console.log('Third backup connection attempt triggered')
          connectWebSocket()
        }
      }, 6000)
      backupTimeouts.push(thirdBackup)

      return () => {
        // clean up WebSocket when component unmounts or sessionId changes
        if (internalWsRef.current) {
          try {
            internalWsRef.current.close()
          } catch (e) {
            console.error('Error closing WebSocket during cleanup:', e)
          }
          internalWsRef.current = null
        }

        // clear all backup timeouts
        backupTimeouts.forEach((timeout) => clearTimeout(timeout))
      }
    }
  }, [sessionId, connectWebSocket, focusTerminal, isConnected])

  // handle WebSocket messages
  const handleWebSocketMessage = (message: any) => {
    if (!xtermRef.current) return

    switch (message.type) {
      case 'shell_output':
        // handle shell output
        if (xtermRef.current && message.data) {
          // process the output to ensure proper prompt display
          const processedOutput = processTerminalOutput(message.data)

          // write the processed output to the terminal
          xtermRef.current.write(processedOutput)

          // focus the terminal after output
          setTimeout(() => {
            if (xtermRef.current) {
              xtermRef.current.focus()
            }
          }, 100)
        }

        // send output to parent component if callback is provided
        if (onOutput && message.data) {
          onOutput(message.data)
        }
        break

      case 'shell_connected':
        // shell session is connected
        console.log('Shell session connected')
        setIsConnected(true)

        // focus terminal after connection is confirmed
        setTimeout(() => {
          if (xtermRef.current) {
            xtermRef.current.focus()
          }
        }, 100)
        break

      case 'shell_error':
        // handle shell errors
        console.error('Shell error:', message.error)
        if (xtermRef.current) {
          xtermRef.current.write(`\r\nError: ${message.error}\r\n`)
        }
        break

      case 'code_execution_result':
        // handle code execution results
        console.log('Code execution result:', message.status)
        if (message.output && xtermRef.current) {
          xtermRef.current.write(`${message.output}\r\n`)
        }
        break

      case 'file_change':
        // handle file change notifications
        console.log('File change detected:', message.file_path)
        if (onFileChange) {
          onFileChange()
        }
        break

      case 'pong':
        // handle ping response, no action needed
        break

      case 'file_sync_complete':
        // file sync completed successfully, just log to console, don't show in terminal
        console.log('File sync completed:', message.message)
        break

      default:
        console.log('Unknown message type:', message.type)
    }
  }

  // update processTerminalOutput to simplify prompt handling
  const processTerminalOutput = (output: string): string => {
    // replace any prompt pattern with our simplified prompt
    let processedOutput = output
      .replace(/[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+:~#\s/g, 'terminuside:~# ')
      .replace(/@terminuside:~#\s/g, 'terminuside:~# ')

    // filter out problematic initialization commands
    const linesToFilter = [
      'export PS1="@terminuside:~# "',
      'export PS1="terminuside:~# "',
      'clear',
      "echo ''",
      'echo ""',
      "echo -n ''",
    ]

    // only filter these lines if they appear alone on a line
    linesToFilter.forEach((line) => {
      processedOutput = processedOutput.replace(new RegExp(`^${line}\\s*$`, 'gm'), '')
    })

    return processedOutput
  }

  const writePrompt = () => {
    if (xtermRef.current && isConnected) {
      xtermRef.current.write('@terminuside:~# ')
    }
  }

  // add a function to manually write the prompt
  const writeManualPrompt = () => {
    if (xtermRef.current && isConnected) {
      xtermRef.current.write('@terminuside:~# ')

      // focus the terminal after writing the prompt
      setTimeout(() => {
        if (xtermRef.current) {
          xtermRef.current.focus()
        }
      }, 50)
    }
  }

  // update the sendShellInput function to include focus
  const sendShellInput = (data: string) => {
    // focus terminal when sending input
    if (xtermRef.current) {
      xtermRef.current.focus()
    }

    // log the input for debugging
    console.log('sendShellInput called:', {
      data: data.charCodeAt(0), // Log char code for debugging
      char: data,
      isConnected,
      wsReadyState: internalWsRef.current?.readyState,
    })

    if (internalWsRef.current && internalWsRef.current.readyState === WebSocket.OPEN) {
      try {
        internalWsRef.current.send(
          JSON.stringify({
            type: 'shell_input',
            data: data,
          })
        )
      } catch (error) {
        console.error('Failed to send shell input:', error)
      }
    } else {
      console.error('Cannot send shell input: WebSocket not connected')

      // try to reconnect if WebSocket is not open
      if (!internalWsRef.current || internalWsRef.current.readyState !== WebSocket.OPEN) {
        console.log('Attempting to reconnect WebSocket...')
        connectWebSocket()
      }
    }
  }

  const sendShellResize = (cols: number, rows: number) => {
    if (internalWsRef.current && internalWsRef.current.readyState === WebSocket.OPEN) {
      internalWsRef.current.send(
        JSON.stringify({
          type: 'shell_resize',
          cols: cols,
          rows: rows,
        })
      )
    }
  }

  // execute command function for Run Code button
  const executeCommand = async (command: string, inputData?: string) => {
    if (!internalWsRef.current || !isConnected) {
      console.error('Not connected to terminal server')
      return
    }

    try {
      // for code execution, send the execute_code message
      internalWsRef.current.send(
        JSON.stringify({
          type: 'execute_code',
          code: command,
          input_data: inputData,
        })
      )
    } catch (error) {
      console.error('Failed to execute command:', error)
    }
  }

  // effect to handle input data changes
  useEffect(() => {
    if (inputData && internalWsRef.current && isConnected) {
      // Send input data to the backend when it changes
      internalWsRef.current.send(
        JSON.stringify({
          type: 'input_data',
          content: inputData,
        })
      )
    }
  }, [inputData, isConnected])

  // add a click handler to the terminal container to ensure focus
  const handleTerminalClick = useCallback(() => {
    console.log('Terminal container clicked')
    ensureTerminalFocus()
  }, [ensureTerminalFocus])

  if (!sessionId) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'background.paper',
        }}
      >
        <Typography variant="body1" color="text.secondary">
          Select or create a session to use the terminal
        </Typography>
      </Box>
    )
  }

  return (
    <Paper
      elevation={0}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        bgcolor: isDarkMode ? '#1e1e1e' : '#ffffff',
      }}
      onClick={handleTerminalClick}
      onMouseDown={handleTerminalClick}
      onTouchStart={handleTerminalClick}
    >
      <Box
        ref={terminalRef}
        sx={{
          flexGrow: 1,
          p: 1,
          overflow: 'hidden',
          '& .xterm': {
            height: '100%',
          },
          '& .xterm-viewport': {
            // override any background color for transparency
            backgroundColor: 'transparent !important',
          },
        }}
      />
    </Paper>
  )
}

export default Terminal
