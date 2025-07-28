import React, { useCallback } from 'react'
import Editor from '@monaco-editor/react'
import { Box, Paper, useTheme } from '@mui/material'
import { debounce } from 'lodash'

interface CodeFile {
  id: number
  name: string
  path: string
  content: string
  file_type: string
  session_id: number
  size_bytes: number
  created_at: string
  updated_at: string
}

interface CodeEditorProps {
  file: CodeFile
  onContentChange: (content: string) => void
}

export const CodeEditor: React.FC<CodeEditorProps> = ({ file, onContentChange }) => {
  const theme = useTheme()
  const isDarkMode = theme.palette.mode === 'dark'

  // Determine language from file type or extension
  const getLanguage = () => {
    if (file.file_type === 'python') return 'python'
    if (file.file_type === 'javascript') return 'javascript'
    if (file.file_type === 'typescript') return 'typescript'

    // Fallback to extension
    const extension = file.name.split('.').pop()?.toLowerCase()
    switch (extension) {
      case 'py':
        return 'python'
      case 'js':
        return 'javascript'
      case 'ts':
        return 'typescript'
      case 'html':
        return 'html'
      case 'css':
        return 'css'
      case 'json':
        return 'json'
      case 'md':
        return 'markdown'
      default:
        return 'plaintext'
    }
  }

  // Debounce the content change to prevent excessive API calls
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedContentChange = useCallback(
    debounce((value: string) => {
      onContentChange(value)
    }, 500),
    [onContentChange]
  )

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      debouncedContentChange(value)
    }
  }

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <Paper
        elevation={0}
        sx={{
          flexGrow: 1,
          borderRadius: 1,
          overflow: 'hidden',
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Editor
          key={`editor-${file.id}-${file.path}`}
          height="100%"
          language={getLanguage()}
          value={file.content}
          onChange={handleEditorChange}
          theme={isDarkMode ? 'vs-dark' : 'light'}
          options={{
            minimap: {
              enabled: true,
              showSlider: 'always',
              renderCharacters: true,
              maxColumn: 120,
              scale: 1,
            },
            scrollBeyondLastLine: false,
            fontSize: 14,
            wordWrap: 'on',
            automaticLayout: true,
            tabSize: 2,
            renderLineHighlight: 'all',
            fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
            fontLigatures: true,
            scrollbar: {
              verticalScrollbarSize: 12,
              horizontalScrollbarSize: 12,
              alwaysConsumeMouseWheel: false,
              useShadows: true,
            },
            // These options help keep the cursor and view centered
            cursorSurroundingLines: 5,
            cursorSurroundingLinesStyle: 'all',
            smoothScrolling: true,
            mouseWheelScrollSensitivity: 1.5,
          }}
        />
      </Paper>
    </Box>
  )
}

export default CodeEditor
