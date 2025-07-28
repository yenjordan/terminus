export interface User {
  id: string
  email: string
  role: 'attempter' | 'reviewer' | 'admin' | 'moderator'
  username: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterCredentials extends LoginCredentials {
  username: string
  confirmPassword?: string
  role: 'attempter' | 'reviewer'
}

export interface AuthResponse {
  access_token: string
  token_type: string
}

export interface AuthResult {
  success: boolean
  error: string | null
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}
