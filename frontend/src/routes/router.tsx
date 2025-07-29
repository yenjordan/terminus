import React, { useEffect } from 'react'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import Login from '../pages/Login'
import Register from '../pages/Register'
import IDE from '../pages/IDE'
import RootLayout from '../layouts/RootLayout'
import { useAuth } from '../context/AuthContext'

// create a router with protected routes
const Router: React.FC = () => {
  const { isAuthenticated, user, fetchUserData } = useAuth()

  // fetch user data when authenticated
  useEffect(() => {
    if (isAuthenticated && !user) {
      fetchUserData()
    }
  }, [isAuthenticated, user, fetchUserData])

  const router = createBrowserRouter([
    {
      path: '/',
      element: <RootLayout />,
      children: [
        {
          path: '/',
          element: <Navigate to="/login" />,
        },
        {
          path: '/ide',
          element: isAuthenticated ? <IDE /> : <Navigate to="/login" />,
        },
        {
          path: '/login',
          element: !isAuthenticated ? <Login /> : <Navigate to="/ide" />,
        },
        {
          path: '/register',
          element: !isAuthenticated ? <Register /> : <Navigate to="/ide" />,
        },
        {
          path: '*',
          element: <Navigate to="/login" />,
        },
      ],
    },
  ])

  return <RouterProvider router={router} />
}

export default Router
