import { createContext, useContext, useReducer, ReactNode, useCallback, useEffect } from 'react'
import { AuthState, LoginCredentials, RegisterCredentials, AuthResult, User } from '@/types/auth'

// Use the proxy configuration instead of hardcoded URL
const API_URL = '' // Empty string will use relative URLs with the proxy

// Action types
export const AUTH_ACTIONS = {
  LOGIN_SUCCESS: 'LOGIN_SUCCESS',
  LOGOUT: 'LOGOUT',
  SET_LOADING: 'SET_LOADING',
  SET_USER: 'SET_USER',
} as const

type AuthAction =
  | { type: typeof AUTH_ACTIONS.LOGIN_SUCCESS; payload: { token: string } }
  | { type: typeof AUTH_ACTIONS.LOGOUT }
  | { type: typeof AUTH_ACTIONS.SET_LOADING; payload: boolean }
  | { type: typeof AUTH_ACTIONS.SET_USER; payload: User }

const AuthStateContext = createContext<AuthState | null>(null)
const AuthDispatchContext = createContext<{
  login: (credentials: LoginCredentials) => Promise<AuthResult>
  register: (credentials: RegisterCredentials) => Promise<AuthResult>
  logout: () => void
  fetchUserData: () => Promise<void>
} | null>(null)

const getInitialState = (): AuthState => ({
  isAuthenticated: !!localStorage.getItem('token'),
  token: localStorage.getItem('token'),
  isLoading: false,
  user: null,
})

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case AUTH_ACTIONS.LOGIN_SUCCESS:
      return {
        ...state,
        isAuthenticated: true,
        token: action.payload.token,
        isLoading: false,
      }
    case AUTH_ACTIONS.LOGOUT:
      return {
        ...state,
        isAuthenticated: false,
        token: null,
        user: null,
      }
    case AUTH_ACTIONS.SET_LOADING:
      return {
        ...state,
        isLoading: action.payload,
      }
    case AUTH_ACTIONS.SET_USER:
      return {
        ...state,
        user: action.payload,
      }
    default:
      return state
  }
}

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, dispatch] = useReducer(authReducer, getInitialState())

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    dispatch({ type: AUTH_ACTIONS.LOGOUT })
  }, [])

  const fetchUserData = useCallback(async () => {
    if (!state.token) return

    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${state.token}`,
        },
      })

      if (response.ok) {
        const userData = await response.json()
        dispatch({ type: AUTH_ACTIONS.SET_USER, payload: userData })
      } else {
        // If we can't fetch user data, token might be invalid
        if (response.status === 401) {
          logout()
        }
      }
    } catch (error) {
      console.error('Error fetching user data:', error)
    }
  }, [state.token, logout])

  // Fetch user data on initial load if token exists
  useEffect(() => {
    if (state.isAuthenticated && !state.user) {
      fetchUserData()
    }
  }, [state.isAuthenticated, state.user, fetchUserData])

  const login = useCallback(
    async (credentials: LoginCredentials): Promise<AuthResult> => {
      dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: true })

      try {
        const response = await fetch(`${API_URL}/api/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(credentials),
        })

        // Check if response is ok before trying to parse JSON
        if (!response.ok) {
          let errorMessage = 'Login failed'
          try {
            const errorData = await response.json()
            errorMessage = errorData.detail || errorMessage
          } catch (jsonError) {
            console.error('Error parsing error response:', jsonError)
            // Use status text if JSON parsing fails
            errorMessage = response.statusText || errorMessage
          }

          dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: false })
          return {
            success: false,
            error: errorMessage,
          }
        }

        // Parse the successful response
        let data
        try {
          data = await response.json()
        } catch (jsonError) {
          console.error('Error parsing successful response:', jsonError)
          dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: false })
          return {
            success: false,
            error: 'Invalid response from server',
          }
        }

        localStorage.setItem('token', data.access_token)
        dispatch({
          type: AUTH_ACTIONS.LOGIN_SUCCESS,
          payload: { token: data.access_token },
        })

        // Fetch user data after successful login
        await fetchUserData()

        return { success: true, error: null }
      } catch (error) {
        console.error('Login error:', error)
        dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: false })
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Login failed',
        }
      }
    },
    [fetchUserData]
  )

  const register = useCallback(
    async (credentials: RegisterCredentials): Promise<AuthResult> => {
      dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: true })

      try {
        const { confirmPassword, ...registerData } = credentials
        const response = await fetch(`${API_URL}/api/auth/register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(registerData),
        })

        const data = await response.json()

        if (!response.ok) {
          dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: false })
          return {
            success: false,
            error: data.detail || 'Registration failed',
          }
        }

        // After successful registration, automatically log in
        return login({
          email: registerData.email,
          password: registerData.password,
        })
      } catch (error) {
        dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: false })
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Registration failed',
        }
      }
    },
    [login]
  )

  const value = {
    login,
    register,
    logout,
    fetchUserData,
  }

  return (
    <AuthStateContext.Provider value={state}>
      <AuthDispatchContext.Provider value={value}>{children}</AuthDispatchContext.Provider>
    </AuthStateContext.Provider>
  )
}

export function useAuthState() {
  const context = useContext(AuthStateContext)
  if (!context) {
    throw new Error('useAuthState must be used within an AuthProvider')
  }
  return context
}

export function useAuthDispatch() {
  const context = useContext(AuthDispatchContext)
  if (!context) {
    throw new Error('useAuthDispatch must be used within an AuthProvider')
  }
  return context
}

export function useAuth() {
  return {
    ...useAuthState(),
    ...useAuthDispatch(),
  }
}
